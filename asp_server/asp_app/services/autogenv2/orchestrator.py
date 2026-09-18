"""
AutoGen v2 orchestrator — main entry point.

Setup time:
  save_autogen_config  — persist user parameters into setup_state.
  delete_candidate     — remove one auto-generated site after review.

Execution time:
  run_autogen_pipeline — step-by-step location selection after
                         BASELINE_COVERAGE completes:

    Step 1  Extract poor-coverage pixels from baseline BIL raster
    Step 2  Optional population-density weighting
    Step 3  Build composite weights (severity × population)
    Step 4  DBSCAN clustering → top-N centroids
    Step 5  Spacing filter (adaptive baseline relaxation)
    Step 6  Resolve PCI / TAC / RSI from project DB
    Step 7  Per-site azimuth selection (bearing histogram) +
            antenna device / master pattern resolution
    Step 8  Generate GDL XLSX with real coordinates
    Step 9  Persist allCandidates + filePath into setup_state
"""

import asyncio
import logging
import os
from typing import Dict, List
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
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
from asp_app.db.schemas.setup import AutoGenConfigRequest
from asp_app.db.schemas.execution import ExecutionStatusState, ExecutionStepName, ExecutionStatus
from asp_app.services.redis_service import RedisService

from asp_app.services.autogenv2.utils.iid_factory import is_autogen_iid
from asp_app.services.autogenv2.raster.poor_bin_extractor import extract_poor_bins_with_rsrp
from asp_app.services.autogenv2.raster.population_weight import (
    find_population_raster,
    load_population_raster,
    sample_weights_at_pixels,
)
from asp_app.services.autogenv2.clustering.placement_service import (
    apply_spacing_constraints,
    cluster_and_pick_centroids,
)
from asp_app.services.autogenv2.output.gdl_writer import generate_gdl
from asp_app.services.autogenv2.antenna.azimuth import compute_site_azimuths
from asp_app.services.autogenv2.antenna.antenna_resolver import resolve_antennas_for_site
from asp_app.services.autogenv2.antenna.site_params import (
    compute_site_height, compute_site_max_tx, compute_site_mimo,
    compute_site_plmn, pick_collision_free_pcis, pick_collision_free_rsis,
    compute_sector_etilt,
)
from asp_app.services.autogenv2.clustering.placement_service import haversine_km

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════
#  Helpers
# ═══════════════════════════════════════════════════════════════════════

async def _get_session(db: AsyncSession, session_id: UUID) -> ACSSSession:
    result = await db.execute(select(ACSSSession).where(ACSSSession.id == session_id))
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    return session


def _resolve_tech(polygon: dict) -> str:
    raw = (polygon.get("technology") or "LTE").upper()
    if "NR" in raw or "5G" in raw or "FIVEG" in raw:
        return "NR"
    return "LTE"


def _to_unc_path(path: str) -> str:
    """Convert path to UNC format on Windows, keep Linux paths as-is."""
    if not path or not path.strip():
        return path
    normalized = path.strip().replace("\\", "/").strip("/")
    if not normalized:
        return path
    parts = [p for p in normalized.split("/") if p]
    if not parts:
        return path
    if os.name == "nt":
        return "\\\\" + "\\".join(parts)
    return "/" + "/".join(parts)


def _resolve_baseline_bil_folder(project_name: str, session_id: UUID, array_type: str) -> str:
    config = get_coverage_api_config()
    raw = join_paths(
        config.coverage_root_output_retrieval_location,
        project_name,
        str(session_id),
        StepName.BASELINE_COVERAGE.value,
        array_type,
    )
    return _to_unc_path(raw)


async def _fetch_pci_rsi_for_site(project_name, lat, lon, radius_km, technology, selected_band=""):
    """10 km PCI+RSI scan via a fresh NullPool engine (Celery-safe).

    Returns (used_pcis: set, used_rsis: set) where PCIs are cross-band
    and RSIs are filtered to the selected band only.
    """
    from asp_app.services.cells_service import CellsService

    db_config = get_database_config()
    project_db_url = db_config.get_database_url(project_name.lower())
    engine = create_async_engine(project_db_url, poolclass=NullPool)
    sm = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)
    try:
        async with sm() as project_db:
            return await CellsService.get_nearby_pci_rsi(
                project_db, lat, lon, radius_km, technology, selected_band,
            )
    finally:
        await engine.dispose()


async def _fetch_pattern_by_etilt(project_name, band, target_etilt, antenna_device, technology):
    """Pattern lookup by closest eTilt + same antenna device via fresh engine."""
    from asp_app.services.cells_service import CellsService

    db_config = get_database_config()
    project_db_url = db_config.get_database_url(project_name.lower())
    engine = create_async_engine(project_db_url, poolclass=NullPool)
    sm = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)
    try:
        async with sm() as project_db:
            return await CellsService.get_pattern_by_etilt(
                project_db, band, target_etilt, antenna_device, technology,
            )
    finally:
        await engine.dispose()


async def _fetch_fresh_baseline(
    project_name: str,
    boundary_coords: List[List[float]],
    selected_band: str,
    technology: str,
) -> List[Dict]:
    """Call CellsService.get_baseline_cells_for_band via a fresh NullPool engine.

    Returns a list of site dicts with fully enriched cell data (antenna_device,
    master_pattern, antenna_height, mechanical_tilt, max_tx_power).
    """
    from asp_app.services.cells_service import CellsService

    db_config = get_database_config()
    project_db_url = db_config.get_database_url(project_name.lower())
    engine = create_async_engine(project_db_url, poolclass=NullPool)
    sm = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)
    try:
        async with sm() as project_db:
            return await CellsService.get_baseline_cells_for_band(
                project_db, boundary_coords, selected_band, technology,
            )
    finally:
        await engine.dispose()


def _should_skip(load_state: dict) -> bool:
    if not load_state.get("filePath"):
        return False
    config = load_state.get("autoGenConfig") or {}
    current_seed = int(config.get("seed", 0))
    materialized_seed = config.get("materialized_seed")
    if materialized_seed is None:
        return True
    return int(materialized_seed) == current_seed


# ═══════════════════════════════════════════════════════════════════════
#  Setup-time API
# ═══════════════════════════════════════════════════════════════════════

async def save_autogen_config(
    db: AsyncSession,
    acss_session_id: UUID,
    config: AutoGenConfigRequest,
    redis_client: Redis,
) -> ACSSSession:
    """Persist user's auto-gen parameters. No GDL is generated at setup time."""

    session = await _get_session(db, acss_session_id)
    setup_state = dict(session.setup_state or {})

    polygon = setup_state.get("polygon") or {}
    tech = _resolve_tech(polygon)
    selected_band = polygon.get("selectedBand") or ""

    load_state = dict(setup_state.get("loadCandidateGdl") or {})
    load_state.update({
        "status": "done",
        "fileName": None,
        "filePath": None,
        "autoGenConfig": {
            "n": config.n,
            "threshold_dbm": config.threshold_dbm,
            "seed": config.seed,
            "enable_population_weighting": bool(config.enable_population_weighting),
            "generated_count": None,
            "technology": tech,
            "selected_band": selected_band,
        },
    })
    setup_state["loadCandidateGdl"] = load_state
    setup_state.pop("allCandidates", None)
    session.setup_state = setup_state
    flag_modified(session, "setup_state")
    await db.commit()
    await db.refresh(session)

    await RedisService.publish_log(
        redis_client, f"logs:{acss_session_id}",
        f"Auto-gen config saved (v2): N={config.n} threshold={config.threshold_dbm} "
        f"seed={config.seed} band={selected_band} tech={tech}",
    )
    return session


async def delete_candidate(
    db: AsyncSession,
    acss_session_id: UUID,
    site_iid: str,
    redis_client: Redis,
) -> Dict:
    """Remove one auto-generated site from setup_state['allCandidates']."""
    session = await _get_session(db, acss_session_id)
    setup_state = dict(session.setup_state or {})
    candidates: List[Dict] = list(setup_state.get("allCandidates") or [])

    if not is_autogen_iid(site_iid):
        raise HTTPException(
            status_code=400,
            detail=f"Refusing to delete non-auto-generated site {site_iid!r}; "
                   "only AUTO_-prefixed sites can be removed via this endpoint",
        )

    matching = [s for s in candidates if s.get("site_iid") == site_iid]
    if not matching:
        raise HTTPException(status_code=404, detail=f"Site {site_iid!r} not found")

    remaining = [s for s in candidates if s.get("site_iid") != site_iid]
    setup_state["allCandidates"] = remaining
    session.setup_state = setup_state
    flag_modified(session, "setup_state")
    await db.commit()
    await db.refresh(session)

    await RedisService.publish_log(
        redis_client, f"logs:{acss_session_id}",
        f"Deleted auto-generated site {site_iid}; {len(remaining)} candidates remain",
    )
    return {
        "session_id": session.id,
        "deleted_site_iid": site_iid,
        "remaining_count": len(remaining),
    }


async def _publish_autogen_progress(
    db: AsyncSession, session: ACSSSession, redis_client: Redis, job_id: str, progress: int
):
    """Publish autoGenCandidates progress to the execution state SSE stream."""
    if not job_id:
        return
    state = ExecutionStatusState(**(session.execution_status_state or {}))
    step = state.autoGenCandidates
    step.status = ExecutionStatus.RUNNING
    step.progress = progress
    session.execution_status_state = state.model_dump(mode="json")
    flag_modified(session, "execution_status_state")
    await db.commit()
    await RedisService.publish_execution_state(redis_client, job_id, session.execution_status_state)


# ═══════════════════════════════════════════════════════════════════════
#  Execution-time pipeline  (called after BASELINE_COVERAGE)
# ═══════════════════════════════════════════════════════════════════════

async def run_autogen_pipeline(
    db: AsyncSession,
    session: ACSSSession,
    redis_client: Redis,
    project_name: str,
    job_id: str = None,
) -> ACSSSession:
    """Step-by-step location selection → GDL generation.

    Raises HTTPException(400) at the end for dev re-execution.
    """
    session_id = session.id
    setup_state = dict(session.setup_state or {})
    load_state = dict(setup_state.get("loadCandidateGdl") or {})
    config = load_state.get("autoGenConfig")

    if not config:
        return session
    if _should_skip(load_state):
        await RedisService.publish_log(
            redis_client, f"logs:{session_id}",
            f"AutoGen v2: skipping (already materialised for seed={config.get('seed')})"
        )
        return session

    polygon_state = setup_state.get("polygon", {})
    polygon_coords = polygon_state.get("coords") or []
    boundary_coords = polygon_state.get("boundaryCoords") or polygon_coords
    array_type = polygon_state.get("arrayType", "LTE_Best_RSRP")
    tech = config.get("technology", "LTE")
    selected_band = config.get("selected_band", "")

    # Fresh-fetch baseline cells from project DB (with band filter + full antenna data)
    baseline_sites = await _fetch_fresh_baseline(
        project_name, boundary_coords, selected_band, tech,
    )

    if baseline_sites:
        sample_cell = {}
        for s in baseline_sites:
            if s.get("cells"):
                sample_cell = s["cells"][0]
                break
        logger.info(
            "AutoGen v2: fresh baseline — %d sites, band=%s, sample=%s",
            len(baseline_sites), selected_band, sample_cell,
        )
    target_n = int(config["n"])
    seed = int(config.get("seed", 0))

    # ── Step 1: Extract poor-coverage pixels ─────────────────────────
    await _publish_autogen_progress(db, session, redis_client, job_id, 5)
    bil_folder = _resolve_baseline_bil_folder(project_name, session_id, array_type)
    await RedisService.publish_log(
        redis_client, f"logs:{session_id}",
        f"[Step 1/9] Extracting poor bins from BIL "
        f"(threshold={config['threshold_dbm']} dBm)"
    )
    if not os.path.isdir(bil_folder):
        raise HTTPException(status_code=400, detail=f"Baseline BIL folder not found: {bil_folder}")

    threshold_dbm = float(config["threshold_dbm"])
    poor_triples = await asyncio.to_thread(
        extract_poor_bins_with_rsrp, bil_folder, polygon_coords, threshold_dbm
    )
    poor_bins = [(lat, lon) for (lat, lon, _) in poor_triples]
    pixel_rsrp = [rsrp for (_, _, rsrp) in poor_triples]
    pixel_severity = [max(0.0, threshold_dbm - r) for r in pixel_rsrp]

    await RedisService.publish_log(
        redis_client, f"logs:{session_id}",
        f"[Step 1/9] {len(poor_bins)} poor bins flagged "
        f"(severity {min(pixel_severity, default=0):.1f}…{max(pixel_severity, default=0):.1f} dB)"
    )
    if not poor_bins:
        raise HTTPException(
            status_code=400,
            detail="No poor-coverage pixels found below threshold. "
                   "Try a less aggressive threshold (closer to 0)."
        )

    # ── Step 2: Population weighting (optional) ──────────────────────
    await _publish_autogen_progress(db, session, redis_client, job_id, 15)
    enable_pop = bool(config.get("enable_population_weighting", True))
    pop_path = find_population_raster(project_name) if enable_pop else None
    pixel_weights = None

    if not enable_pop:
        await RedisService.publish_log(
            redis_client, f"logs:{session_id}",
            "[Step 2/9] Population weighting disabled — uniform weighting"
        )
    elif pop_path:
        pop_bundle = await asyncio.to_thread(load_population_raster, pop_path)
        pixel_weights = await asyncio.to_thread(
            sample_weights_at_pixels, pop_bundle, poor_bins,
        )
        total_pop = float(sum(pixel_weights))
        n_with_pop = sum(1 for w in pixel_weights if w > 0)
        await RedisService.publish_log(
            redis_client, f"logs:{session_id}",
            f"[Step 2/9] Population weighting enabled "
            f"(raster: {os.path.basename(pop_path)}; "
            f"pop={total_pop:.0f} across {n_with_pop}/{len(poor_bins)} pixels)"
        )
        if total_pop <= 0.0:
            pixel_weights = None
            await RedisService.publish_log(
                redis_client, f"logs:{session_id}",
                "[Step 2/9] All pixels map to 0 population — falling back to uniform"
            )
    else:
        await RedisService.publish_log(
            redis_client, f"logs:{session_id}",
            f"[Step 2/9] No population raster found — uniform weighting"
        )

    # ── Step 3: Composite weights ────────────────────────────────────
    composite_weights = [
        sev * (max(1.0, float(pixel_weights[i])) if pixel_weights is not None else 1.0)
        for i, sev in enumerate(pixel_severity)
    ]
    await RedisService.publish_log(
        redis_client, f"logs:{session_id}",
        f"[Step 3/9] Composite weights computed (severity × population)"
    )

    # ── Step 4: DBSCAN clustering ────────────────────────────────────
    centroids = await asyncio.to_thread(
        cluster_and_pick_centroids, poor_bins,
        target_n, 1.0, 10, seed, composite_weights,
    )
    cluster_sizes = [c.get("cluster_size", 0) for c in centroids]
    await RedisService.publish_log(
        redis_client, f"logs:{session_id}",
        f"[Step 4/9] DBSCAN → {len(centroids)} clusters "
        f"(target {target_n}); sizes={cluster_sizes}"
    )

    # ── Step 5: Spacing filter ───────────────────────────────────────
    await _publish_autogen_progress(db, session, redis_client, job_id, 40)
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
        f"[Step 5/9] Spacing (≥0.5km inter-candidate, "
        f"≥{chosen_baseline_km * 1000:.0f}m baseline"
        f"{' — relaxed' if relaxed else ''}) "
        f"→ {len(accepted)}/{pre_spacing} kept (dropped {dropped})"
    )
    centroids = accepted
    if not centroids:
        raise HTTPException(
            status_code=400,
            detail="No viable centroids after spacing filter. "
                   "Try lowering the threshold or expanding the polygon."
        )

    # ── Step 6: (PCI + RSI now resolved per-site in Step 7) ─────────
    await RedisService.publish_log(
        redis_client, f"logs:{session_id}",
        f"[Step 6/9] PCI + RSI resolved per-site via 10km DB scan in Step 7"
    )

    # ── Step 7: Azimuth, Antenna, Height, Power, MIMO, PCI, RSI ─────
    await _publish_autogen_progress(db, session, redis_client, job_id, 50)
    catchment_radius_km = 1.5
    actual_n = min(target_n, len(centroids))
    is_nr = tech == "NR"
    all_assigned_pcis: set = set()
    all_assigned_rsis: set = set()

    for site_idx, centroid in enumerate(centroids[:actual_n]):
        clat, clon = centroid["lat"], centroid["lon"]

        # Gather poor pixels within catchment
        nearby_poor = []
        nearby_weights = []
        for i, p in enumerate(poor_bins):
            if haversine_km(clat, clon, p[0], p[1]) <= catchment_radius_km:
                nearby_poor.append(p)
                nearby_weights.append(composite_weights[i])

        # Compute smart azimuths from bearing histogram
        site_azimuths = compute_site_azimuths(
            clat, clon, nearby_poor,
            weights=nearby_weights if nearby_weights else None,
            n_sectors=3,
            min_sep_deg=65,
        )
        centroid["azimuths"] = site_azimuths

        # Resolve antenna + MIMO + beamset + TAC + ref_signal per sector
        antenna_info = resolve_antennas_for_site(
            clat, clon, site_azimuths, selected_band, baseline_sites,
            max_distance_km=5.0, azimuth_tolerance=30.0,
        )
        centroid["antenna_info"] = antenna_info

        # Compute height, Max TX, MIMO, PLMN from nearby baseline
        site_height = compute_site_height(clat, clon, baseline_sites)
        site_max_tx = compute_site_max_tx(clat, clon, selected_band, baseline_sites)
        mimo_tx, mimo_rx = compute_site_mimo(clat, clon, selected_band, baseline_sites)
        site_plmn = compute_site_plmn(clat, clon, baseline_sites)
        centroid["height_m"] = site_height
        centroid["max_tx_power"] = site_max_tx
        centroid["mimo_tx"] = mimo_tx
        centroid["mimo_rx"] = mimo_rx
        centroid["plmn"] = site_plmn

        # Per-site 10km DB scan for collision-free PCI + RSI
        db_used_pcis, db_used_rsis = await _fetch_pci_rsi_for_site(
            project_name, clat, clon, 10.0, tech, selected_band,
        )
        site_pcis = pick_collision_free_pcis(
            3, tech, db_used_pcis, already_assigned=all_assigned_pcis,
        )
        centroid["pcis"] = site_pcis
        all_assigned_pcis.update(site_pcis)

        site_rsis = pick_collision_free_rsis(
            3, tech, db_used_rsis, already_assigned=all_assigned_rsis,
        )
        all_assigned_rsis.update(site_rsis)
        centroid["rsis"] = site_rsis

        # Per-sector geometry-derived eTilt + DB pattern lookup
        for sec_i, sec in enumerate(antenna_info):
            sec_az = site_azimuths[sec_i] if sec_i < len(site_azimuths) else 0.0
            sec_etilt = compute_sector_etilt(
                clat, clon, sec_az, site_height, nearby_poor,
                weights=nearby_weights if nearby_weights else None,
            )
            sec_device = sec.get("antenna_device") or ""
            pattern, matched_et = await _fetch_pattern_by_etilt(
                project_name, selected_band, sec_etilt, sec_device, tech,
            )
            sec["electrical_tilt"] = sec_etilt
            sec["logical_pattern"] = pattern
            sec["matched_etilt"] = matched_et

        # Per-site Redis logs — one header + one line per sector
        is_default_az = site_azimuths == [0, 120, 240]
        az_str = ", ".join(f"{a:.0f}°" for a in site_azimuths)

        await RedisService.publish_log(
            redis_client, f"logs:{session_id}",
            f"[Step 7/9] ── Site {site_idx + 1}/{actual_n} "
            f"({clat:.5f}, {clon:.5f}) ──"
        )
        await RedisService.publish_log(
            redis_client, f"logs:{session_id}",
            f"  Azimuths: [{az_str}]{'  ⚠ equispaced fallback' if is_default_az else ''}"
        )
        await RedisService.publish_log(
            redis_client, f"logs:{session_id}",
            f"  Height: {site_height:.1f}m | MaxTx: {site_max_tx:.1f}dBm | "
            f"MIMO tx={mimo_tx} rx={mimo_rx} | PLMN={site_plmn or '—'}"
        )
        await RedisService.publish_log(
            redis_client, f"logs:{session_id}",
            f"  PCI: {site_pcis} (from {len(db_used_pcis)} used in 10km) | "
            f"RSI: {site_rsis} (from {len(db_used_rsis)} used same-band in 10km) | "
            f"nearby_poor={len(nearby_poor)}"
        )
        for sec_i, sec in enumerate(antenna_info):
            sec_az = site_azimuths[sec_i] if sec_i < len(site_azimuths) else "?"
            sec_pci = site_pcis[sec_i] if sec_i < len(site_pcis) else "?"
            sec_rsi = site_rsis[sec_i] if sec_i < len(site_rsis) else "?"
            sec_tac = sec.get("tac")
            tac_disp = str(sec_tac) if sec_tac is not None else "—"
            ant_dev = sec.get("antenna_device") or "(default)"
            sec_etilt = sec.get("electrical_tilt")
            sec_pattern = sec.get("logical_pattern")
            sec_met = sec.get("matched_etilt")
            etilt_disp = f"{sec_etilt:.1f}°" if sec_etilt is not None else "—"
            pat_disp = sec_pattern or "—"
            met_disp = f"(db={sec_met:.1f}°)" if sec_met is not None else ""
            ref_ppre = sec.get("ref_signal_ppre")
            ppre_disp = f"{ref_ppre}" if ref_ppre is not None else "—"
            beam_disp = ""
            if is_nr:
                bs = sec.get("beamset_iid")
                beam_disp = f" | beam={bs or '—'}"

            await RedisService.publish_log(
                redis_client, f"logs:{session_id}",
                f"    Sector {sec_i + 1}: az={sec_az}° | eTilt={etilt_disp}→pat={pat_disp} {met_disp} | "
                f"PCI={sec_pci} | RSI={sec_rsi} | TAC={tac_disp} | ant={ant_dev}{beam_disp}"
                + (f" | refPPRE={ppre_disp}" if not is_nr else "")
            )

    await RedisService.publish_log(
        redis_client, f"logs:{session_id}",
        f"[Step 7/9] RF params resolved for {actual_n} sites "
        f"(catchment={catchment_radius_km}km)"
    )

    # ── Step 8: Generate GDL XLSX ────────────────────────────────────
    await _publish_autogen_progress(db, session, redis_client, job_id, 80)
    gdl_path, all_sites = await asyncio.to_thread(
        generate_gdl, actual_n, tech, selected_band,
        str(session_id), seed, project_name, None,
        centroids, pixel_weights is not None,
    )
    await RedisService.publish_log(
        redis_client, f"logs:{session_id}",
        f"[Step 8/9] GDL written — {len(all_sites)} sites → {os.path.basename(gdl_path)}"
    )
    
    # DEV ONLY: raise so re-execution restarts at this step.
    # raise HTTPException(
    #     status_code=400,
    #     detail=f"[DEV] AutoGen v2 pipeline complete — {len(all_sites)} sites placed. "
    #            f"Remove this error once downstream steps are ready."
    # )
    # ── Step 9: Persist into setup_state ─────────────────────────────
    await _publish_autogen_progress(db, session, redis_client, job_id, 95)
    load_state.update({
        "fileName": os.path.basename(gdl_path),
        "filePath": gdl_path,
        "autoGenConfig": {
            **config,
            "generated_count": len(all_sites),
            "baseline_raster_path": bil_folder,
            "materialized_seed": seed,
        },
    })
    setup_state["loadCandidateGdl"] = load_state
    setup_state["allCandidates"] = all_sites
    session.setup_state = setup_state
    flag_modified(session, "setup_state")
    await db.commit()
    await db.refresh(session)

    await RedisService.publish_log(
        redis_client, f"logs:{session_id}",
        f"[Step 9/9] Pipeline complete — {len(all_sites)} candidate sites placed"
    )

    return session

