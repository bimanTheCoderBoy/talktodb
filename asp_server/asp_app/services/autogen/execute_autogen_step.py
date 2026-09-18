"""
Execution-time auto-gen sub-step. Runs AFTER BASELINE_COVERAGE produces
a BIL and BEFORE CREATING_CANDIDATES tries to load a GDL file.

Pipeline (one call):
  1. Locate baseline BIL folder via existing path convention.
  2. Read polygon coords and cellsInPolygon from setup_state.
  3. extract_poor_bins(bil, polygon, threshold) → list of (lat, lon).
  4. cluster_and_pick_centroids(poor_bins, n, eps_km, min_samples, seed).
  5. apply_spacing_constraints(centroids, baseline_sites).
  6. detect_dominant_azimuth_grid(cellsInPolygon).
  7. build_pci_freelist + nearest_baseline_tac + polygon_max_rsi (DB).
  8. synthesize_candidates(...).
  9. write_synthetic_gdl_csv(...).
 10. Update setup_state: allCandidates = sites, loadCandidateGdl.filePath = csv_path,
     loadCandidateGdl.fileName = basename, autoGenConfig.generated_count = len(sites),
     autoGenConfig.baseline_raster_path = bil_folder,
     autoGenConfig.materialized_seed = seed (used by idempotency check next run).
 11. flag_modified(session, "setup_state") + commit.

Returns the updated session.

Idempotency rules:
- If autoGenConfig is None → no-op (manual GDL upload session).
- If filePath is set AND autoGenConfig.materialized_seed == autoGenConfig.seed
  → no-op (already generated for this seed; user did not click Regenerate).
- If filePath is set BUT seed has changed (Regenerate-with-different-seed)
  → re-run synthesis. Old CSV file is left on disk (orphan; cleaned up by
  whatever already cleans GDL_STORAGE_DIR), filePath is overwritten.

Failure modes (each raises HTTPException 400 with a Redis log):
- BIL folder not found
- 0 poor bins (threshold too lenient, suggest user lower it)
- 0 viable centroids after spacing constraints (too cramped, suggest lower N or relax constraints)
"""
import asyncio
import logging
import os
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy.pool import NullPool

from redis import Redis

from asp_app.config.acss_config import (
    get_coverage_api_config,
    get_database_config,
    join_paths,
)
from asp_app.db.models import ACSSSession, StepName
from asp_app.services.redis_service import RedisService
from asp_app.services.autogen.poor_bin_extractor import (
    extract_poor_bins,
    extract_poor_bins_with_rsrp,
)
from asp_app.services.autogen import power_planner, rf_brain
from asp_app.services.autogen.placement_service import (
    apply_spacing_constraints,
    cluster_and_pick_centroids,
    compute_smart_tilt,
    haversine_km,
)
from asp_app.services.autogen.azimuth_detector import (
    compute_smart_azimuths_per_site,
    detect_dominant_azimuth_grid,
)
from asp_app.services.autogen.network_attribute_resolver import (
    build_pci_freelist, nearest_baseline_tac, polygon_max_rsi,
)
from asp_app.services.autogen.candidate_synthesizer import synthesize_candidates
from asp_app.services.autogen.population_weight import (
    find_population_raster,
    load_population_raster,
    sample_weights_at_pixels,
)
from asp_app.services.autogen.synthetic_gdl_writer import (
    compute_smart_height,
    write_synthetic_gdl_csv,
)
from asp_app.services.autogen.template_loader import (
    get_default_tilt,
    get_template,
    get_tilt_range,
)
from asp_app.services.autogen import tilt_mapping


# Beam-pattern UIDs are of the form ``<ANTENNA>\<band>_<tilt_x10>`` —
# e.g. ``ERICSSON_AIR3237_B78K_P\07_100``. We only need the band segment
# at this layer; the tilt mapping module owns everything past it.
import re as _re
_BAND_RE = _re.compile(r"\\(?P<band>[0-9]+)_[0-9]+$")


def _band_from_template(name: str) -> str:
    """Return the two-digit band code embedded in a beam-pattern UID, or
    ``""`` when the name does not follow the UID scheme (caller treats
    that as "no band → no snapping")."""
    if not name:
        return ""
    m = _BAND_RE.search(name)
    return m.group("band") if m else ""

logger = logging.getLogger(__name__)


def _resolve_baseline_bil_folder(project_name: str, session_id: UUID, array_type: str) -> str:
    """
    Mirrors execution_service._get_baseline_path / line ~349 logic:
      coverage_root_output_retrieval_location / project / session_id / BASELINE_COVERAGE / array_type
    """
    config = get_coverage_api_config()
    return join_paths(
        config.coverage_root_output_retrieval_location,
        project_name,
        str(session_id),
        StepName.BASELINE_COVERAGE.value,
        array_type,
    )


async def _resolve_network_attributes_via_rls(
    project_name: str,
    polygon_coords,
    baseline_sites,
    candidate_lat: float,
    candidate_lon: float,
):
    """
    The auto-gen sub-step runs inside a Celery worker, where each task does
    `asyncio.run(execute())` — a fresh event loop per task. We must NOT reuse
    the process-wide ``EngineRegistry`` cache here: its pool holds asyncpg
    connections whose transports are bound to a previous task's (now-dead)
    loop, and SQLAlchemy's `pool_pre_ping` raises
    ``RuntimeError: got Future attached to a different loop`` on the next use.

    Build a fresh ``NullPool`` engine bound to THIS task's loop and dispose
    at the end — mirrors the pattern ``tasks/execution_tasks.py`` already uses
    for the user-DB engine. RLS scoping is bypassed here intentionally
    because the worker has no x-user-email context.
    """
    db_config = get_database_config()
    project_db_url = db_config.get_database_url(project_name.lower())
    engine = create_async_engine(project_db_url, poolclass=NullPool)
    sessionmaker = async_sessionmaker(
        bind=engine, expire_on_commit=False, class_=AsyncSession
    )
    try:
        async with sessionmaker() as project_db:
            pci = await build_pci_freelist(project_db, polygon_coords)
            tac = await nearest_baseline_tac(
                project_db, candidate_lat, candidate_lon, baseline_sites
            )
            rsi = await polygon_max_rsi(project_db, polygon_coords)
        return pci, tac, rsi
    finally:
        await engine.dispose()


def _should_skip(load_state: dict) -> bool:
    """Idempotency check.

    Skip iff filePath is set AND the seed already materialised matches the
    seed currently configured. Different seed → re-run (Regenerate path).
    """
    if not load_state.get("filePath"):
        return False
    config = load_state.get("autoGenConfig") or {}
    current_seed = int(config.get("seed", 0))
    materialized_seed = config.get("materialized_seed")
    if materialized_seed is None:
        # filePath set but seed never recorded → treat as up-to-date (legacy upload path)
        return True
    return int(materialized_seed) == current_seed


async def run_autogen_step(
    db: AsyncSession,
    session: ACSSSession,
    redis_client: Redis,
    project_name: str,
) -> ACSSSession:
    """
    Idempotent (seed-aware): re-runs only when seed differs from the seed
    materialised by a prior run of this step.
    """
    session_id = session.id
    setup_state = dict(session.setup_state or {})
    load_state = dict(setup_state.get("loadCandidateGdl") or {})
    config = load_state.get("autoGenConfig")

    if not config:
        # Manual GDL upload session — nothing to do.
        return session
    if _should_skip(load_state):
        # Already generated for this exact (session, seed); idempotent skip.
        await RedisService.publish_log(
            redis_client, f"logs:{session_id}",
            f"Auto-gen: skipping (already materialised for seed={config.get('seed')})"
        )
        return session

    polygon_state = setup_state.get("polygon", {})
    polygon_coords = polygon_state.get("coords") or []
    array_type = polygon_state.get("arrayType", "LTE_Best_RSRP")
    baseline_sites = polygon_state.get("baselineCells") or []

    bil_folder = _resolve_baseline_bil_folder(project_name, session_id, array_type)
    await RedisService.publish_log(
        redis_client, f"logs:{session_id}",
        f"Auto-gen: extracting poor bins from {bil_folder} (threshold={config['threshold_dbm']} dBm, seed={config.get('seed', 0)})"
    )

    if not os.path.isdir(bil_folder):
        raise HTTPException(status_code=400, detail=f"Baseline BIL folder not found: {bil_folder}")

    # Step 3: poor-bin extraction (CPU/IO heavy → thread). We pull RSRP
    # values alongside the (lat, lon) pairs so downstream smart-params can
    # weight by **gap severity** — a pixel at -125 dBm matters more than
    # one at -111 dBm and the azimuth/tilt picker should bias toward it.
    threshold_dbm = float(config["threshold_dbm"])
    poor_triples = await asyncio.to_thread(
        extract_poor_bins_with_rsrp, bil_folder, polygon_coords, threshold_dbm
    )
    poor_bins = [(lat, lon) for (lat, lon, _) in poor_triples]
    pixel_rsrp = [rsrp for (_, _, rsrp) in poor_triples]
    # Severity = how deep the gap is in dB below threshold. Always > 0 for
    # a poor pixel; deeper holes get more weight. Used as the **always-on**
    # base weight; population multiplies in when the raster is loaded.
    pixel_severity = [max(0.0, threshold_dbm - r) for r in pixel_rsrp]
    await RedisService.publish_log(
        redis_client, f"logs:{session_id}",
        f"Auto-gen: {len(poor_bins)} poor bins flagged "
        f"(severity range: {min(pixel_severity, default=0):.1f}…{max(pixel_severity, default=0):.1f} dB below threshold)"
    )
    if not poor_bins:
        raise HTTPException(
            status_code=400,
            detail="No poor-coverage pixels found below threshold. Try a less aggressive threshold (closer to 0)."
        )

    # Step 3b: Optional population weighting. If a per-project raster lives
    # at <population_rasters_dir>/<project_lower>/<file>.tif, sample it at
    # every poor pixel and use the result as a weight in clustering and
    # downstream smart-param calculations. Auto-disabled when no raster is
    # present — pipeline behaves exactly as before. The user can also
    # explicitly disable weighting via the AutoGenPanel checkbox even when
    # a raster IS present (e.g. to compare population-aware vs uniform
    # placement on the same polygon).
    enable_pop = bool(config.get("enable_population_weighting", True))
    pop_path = find_population_raster(project_name) if enable_pop else None
    pixel_weights = None
    if not enable_pop:
        await RedisService.publish_log(
            redis_client, f"logs:{session_id}",
            "Auto-gen: population weighting disabled by user — using uniform weighting"
        )
    if pop_path:
        pop_bundle = await asyncio.to_thread(load_population_raster, pop_path)
        pixel_weights = await asyncio.to_thread(
            sample_weights_at_pixels, pop_bundle, poor_bins,
        )
        total_pop = float(sum(pixel_weights))
        n_with_pop = sum(1 for w in pixel_weights if w > 0)
        await RedisService.publish_log(
            redis_client, f"logs:{session_id}",
            f"Auto-gen: population weighting enabled "
            f"(raster: {os.path.basename(pop_path)}; "
            f"total pop in poor area = {total_pop:.0f} across "
            f"{n_with_pop}/{len(poor_bins)} pixels with people)"
        )
        if total_pop <= 0.0:
            # Polygon fell entirely on zero-population cells — disable
            # weighting for the rest of this run rather than producing
            # all-zero clusters.
            pixel_weights = None
            await RedisService.publish_log(
                redis_client, f"logs:{session_id}",
                "Auto-gen: every poor pixel maps to 0 population — falling back to uniform weighting"
            )
    else:
        await RedisService.publish_log(
            redis_client, f"logs:{session_id}",
            f"Auto-gen: no population raster at population_rasters/{project_name.lower()}/ "
            f"— using uniform weighting"
        )

    # Composite score = gap_severity × (population OR 1). Always severity-
    # aware; population multiplies in when present. The same vector drives
    # azimuth bearing-histogram, tilt percentile, and DBSCAN ranking — so
    # every smart-param consumes a consistent "where does it actually hurt"
    # signal. Falling back to severity-only when no population data is
    # strictly better than today's uniform/population view.
    composite_weights = [
        sev * (max(1.0, float(pixel_weights[i])) if pixel_weights is not None else 1.0)
        for i, sev in enumerate(pixel_severity)
    ]

    # Step 4: DBSCAN — ranked by the composite (severity × population) score
    # so the top-N clusters are the ones that *hurt the most people the most*,
    # not just the most densely populated coverage holes.
    target_n = int(config["n"])
    centroids = await asyncio.to_thread(
        cluster_and_pick_centroids, poor_bins,
        target_n, 1.0, 10, int(config.get("seed", 0)),
        composite_weights,
    )
    cluster_sizes = [c.get("cluster_size", 0) for c in centroids]
    await RedisService.publish_log(
        redis_client, f"logs:{session_id}",
        f"Auto-gen: DBSCAN produced {len(centroids)} clusters (top-{target_n} by size); "
        f"cluster_sizes={cluster_sizes}"
    )

    # Step 5: spacing — adaptive relaxation. The 800m-from-baseline rule is
    # ideal for greenfield rural placement but eliminates most candidates in
    # dense urban polygons (where every poor-coverage hotspot tends to sit
    # near an existing site edge). We relax that threshold in steps until we
    # reach the requested N or hit a 100m floor — candidate-to-candidate
    # spacing stays at the meaningful 500m. Each relaxation step is logged.
    pre_spacing = len(centroids)
    relaxation_ladder_km = [0.8, 0.5, 0.3, 0.1]
    accepted: list = []
    chosen_baseline_km = relaxation_ladder_km[0]
    for baseline_km in relaxation_ladder_km:
        accepted = apply_spacing_constraints(
            centroids, baseline_sites,
            min_candidate_spacing_km=0.5,
            min_from_baseline_km=baseline_km,
        )
        chosen_baseline_km = baseline_km
        if len(accepted) >= target_n:
            break
    dropped = pre_spacing - len(accepted)
    relaxed = chosen_baseline_km < relaxation_ladder_km[0]
    await RedisService.publish_log(
        redis_client, f"logs:{session_id}",
        f"Auto-gen: spacing filter (≥500m candidate, ≥{chosen_baseline_km*1000:.0f}m baseline"
        f"{' — relaxed from 800m to reach target N' if relaxed else ''}) "
        f"kept {len(accepted)}/{pre_spacing} clusters (dropped {dropped})"
    )
    centroids = accepted
    if not centroids:
        raise HTTPException(
            status_code=400,
            detail="No viable centroids even after relaxing baseline spacing to 100m. "
                   "Polygon may be too small, too few poor bins, or DBSCAN found no "
                   "dense regions. Try lowering the RSRP threshold or expanding the polygon."
        )

    # Step 6: azimuth grid
    azimuth_grid = detect_dominant_azimuth_grid(baseline_sites)

    # Step 7: PCI/TAC/RSI from project DB
    first_centroid = centroids[0]
    pci_freelist, tac, base_rsi = await _resolve_network_attributes_via_rls(
        project_name, polygon_coords, baseline_sites,
        first_centroid["lat"], first_centroid["lon"],
    )

    # Step 8: synthesize
    template_name = config["template_name"]
    template_defaults = get_template(template_name)
    sites = synthesize_candidates(
        centroids=centroids,
        baseline_sites=baseline_sites,
        azimuth_grid=azimuth_grid,
        pci_freelist=pci_freelist,
        base_rsi=int(base_rsi),
        nearest_tac=int(tac),
        template_defaults=template_defaults,
        template_name=template_name,
        session_id=str(session_id),
        seed=int(config.get("seed", 0)),
    )

    # Step 8b: enrich each site via the **RF brain** — one coherent
    # decision per site for height, tilt, azimuths, Max TX, PPRE.
    # All four parameters cascade from a single aggression level derived
    # from the operator's goal, so the plan reads as "the brain set this
    # site to AGGRESSIVE, hence taller + lower-tilt + louder", not as
    # four independent heuristics that happen to share a polygon.
    # ``setup_service.define_goal`` writes ``goalType`` (camelCase) into
    # ``setup_state["defineGoal"]``. Older code paths wrote ``goal_type``
    # or ``type``; we accept all three so the brain reads the goal
    # regardless of which version of the wizard saved it.
    define_goal = (setup_state.get("defineGoal") or {})
    goal_type = (
        define_goal.get("goalType")
        or define_goal.get("goal_type")
        or define_goal.get("type")
        or ""
    )
    goal_params = define_goal.get("parameters") or {}

    tilt_range = get_tilt_range(template_name)
    template_default_tilt = float(get_default_tilt(template_name))
    electrical_tilt_override = config.get("electrical_tilt_deg")
    band_code = _band_from_template(template_name)
    available_tilts = tilt_mapping.get_available_tilts(band_code) if band_code else []
    mapping_active = bool(available_tilts)

    aggression = rf_brain.derive_aggression(goal_type, goal_params)
    catchment_radius_km = 1.5
    for site in sites:
        # Poor pixels within this site's catchment radius, paired with
        # COMPOSITE (severity × population) weights so every brain
        # decision biases toward dense + deep gaps.
        nearby_poor = []
        nearby_weights = []
        for i, p in enumerate(poor_bins):
            if haversine_km(site["latitude"], site["longitude"], p[0], p[1]) <= catchment_radius_km:
                nearby_poor.append(p)
                nearby_weights.append(composite_weights[i])
        wt_arg = nearby_weights if nearby_weights else None

        params = rf_brain.decide_site_params(
            site_lat=site["latitude"],
            site_lon=site["longitude"],
            poor_bins_nearby=nearby_poor,
            poor_weights_nearby=wt_arg,
            baseline_sites=baseline_sites,
            goal_type=goal_type,
            goal_params=goal_params,
            template_defaults=template_defaults,
            band_code=band_code,
            available_tilts=available_tilts,
            tilt_range=tilt_range,
            template_default_tilt=template_default_tilt,
            electrical_tilt_override=electrical_tilt_override,
        )

        # Stamp the per-site values onto the cells. The writer reads:
        #   cell["azimuth"]                 → Property: Physical Antenna: Azimuth (deg)
        #   cell["_electrical_tilt_deg"]    → Property: Logical Antenna: Electrical Tilt (deg)
        #   cell["_height_m"]               → Property: Physical Antenna: Height - Inventory (m)
        #   cell["_max_tx_dbm"]             → Cell: LTE: Max TX Power (dBm)
        #   cell["_resolved_template_name"] → Antenna Device + Master Pattern 1 + Pattern
        # NB: PPRE is intentionally NOT stamped — the brain leaves it at
        # the template default (PPRE doesn't move the RSRP goal; bumping
        # it just risks pilot pollution without any coverage gain).
        n_azs = len(params.azimuths_deg) or 1
        for s_idx, c in enumerate(site["cells"]):
            c["azimuth"] = float(params.azimuths_deg[s_idx % n_azs])
            c["_electrical_tilt_deg"] = params.tilt_deg
            c["_height_m"] = params.height_m
            c["_max_tx_dbm"] = params.max_tx_dbm
            if params.tilt_resolved_uid:
                c["_resolved_template_name"] = params.tilt_resolved_uid

        # Site-level summary for the CandidateTable / GDL preview. Lets the
        # frontend render the smart per-site values without having to dig
        # into individual cells. covers_population is populated only when
        # population weighting is active for this run; covers_poor_bins
        # remains the pixel count (preserves existing display contract).
        site["azimuths"] = list(params.azimuths_deg)
        site["electrical_tilt_deg"] = float(params.tilt_deg)
        site["height_m"] = float(params.height_m)
        site["max_tx_dbm"] = float(params.max_tx_dbm)
        site["template_name"] = template_name
        # The brain's aggression level: one number explaining all four
        # parameter choices — the UI / debug logs surface this verbatim.
        site["aggression"] = int(params.aggression)
        site["aggression_label"] = params.aggression.name.lower()
        if params.tilt_resolved_uid:
            site["resolved_template_name"] = params.tilt_resolved_uid
        site["population_weighted"] = pixel_weights is not None
        if pixel_weights is not None:
            # Centroid total_weight (= people in cluster) was attached by
            # cluster_and_pick_centroids when weights were supplied.
            tw = next((c.get("total_weight") for c in centroids
                       if c.get("lat") == site["latitude"] and c.get("lon") == site["longitude"]),
                      None)
            if tw is not None:
                site["covers_population"] = int(round(float(tw)))

    # Hold one site's params handy for the log line; their aggression is
    # constant across the run (depends only on the session-level goal).
    brain_summary = rf_brain.describe_aggression(aggression)

    tilt_log = (
        "user override " + str(electrical_tilt_override)
        if electrical_tilt_override is not None
        else "brain score-weighted geometry"
    )
    if mapping_active:
        tilt_log += (
            f" (snapped to band {band_code} mapping: "
            f"{len(available_tilts)} tilts available)"
        )
    else:
        tilt_log += " (no tilt-mapping uploaded — continuous clamp)"
    weight_basis = "severity×population" if pixel_weights is not None else "severity-only"
    await RedisService.publish_log(
        redis_client, f"logs:{session_id}",
        f"Auto-gen: RF brain → {brain_summary}; "
        f"tilt={tilt_log}; "
        f"azimuths=5°-binned bearing-histogram (≥65° apart, weighted by {weight_basis}); "
        f"power=median(baseline)+aggression-bias, clamped 23..46 dBm"
    )

    # Step 9: write XLSX (also blocking — to_thread). The brain stamps a
    # per-site ``_height_m`` on every cell so the function-level height
    # fallback is dead in practice — pass the template default just so the
    # writer has a non-None value if a future code path emits a cell
    # without the field.
    fallback_height = float(
        template_defaults.get("Property: Physical Antenna: Height - Inventory (m)", 15.0)
    )
    csv_path = await asyncio.to_thread(
        write_synthetic_gdl_csv,
        sites, baseline_sites, template_defaults,
        template_name, str(session_id),
        None,                              # storage_dir (use default)
        electrical_tilt_override,          # function-level fallback if cell tilt missing
        fallback_height,                   # function-level fallback if cell height missing
        project_name,                      # populates State / Address 1 / Town
    )

    # Step 10: persist (record materialized_seed for idempotency check on next run)
    load_state.update({
        "fileName": os.path.basename(csv_path),
        "filePath": csv_path,
        "autoGenConfig": {
            **config,
            "generated_count": len(sites),
            "baseline_raster_path": bil_folder,
            "materialized_seed": int(config.get("seed", 0)),
        },
    })
    setup_state["loadCandidateGdl"] = load_state
    setup_state["allCandidates"] = sites
    session.setup_state = setup_state
    flag_modified(session, "setup_state")
    await db.commit()
    await db.refresh(session)

    await RedisService.publish_log(
        redis_client, f"logs:{session_id}",
        f"Auto-gen complete: {len(sites)} candidate sites synthesized; CSV at {csv_path}"
    )
    return session
