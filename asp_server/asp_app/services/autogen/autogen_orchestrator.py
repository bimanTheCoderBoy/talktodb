"""
Setup-time auto-gen orchestration (v1):
- save_autogen_config persists user-supplied N/threshold/template/seed into
  setup_state["loadCandidateGdl"]["autoGenConfig"]. Mark loadCandidateGdl
  status 'done' so the existing isSetupComplete check passes and the user
  can hit "Run".
- delete_candidate removes one auto-generated site from
  setup_state["allCandidates"] after the user reviewed and rejected it.

Actual DBSCAN + synthesis happens at execution time in plan 02-07's new
sub-step (between BASELINE_COVERAGE and CREATING_CANDIDATES). Setup-time
generation would block on a not-yet-existing BIL.
"""
from typing import Dict, List
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified
from redis import Redis

from asp_app.db.models import ACSSSession
from asp_app.db.schemas.setup import AutoGenConfigRequest
from asp_app.services.autogen.template_loader import (
    get_default_tilt,
    get_tilt_range,
    list_template_names,
)
from asp_app.services.autogen.iid_factory import is_autogen_iid
from asp_app.services.redis_service import RedisService


async def _get_session(db: AsyncSession, session_id: UUID) -> ACSSSession:
    result = await db.execute(select(ACSSSession).where(ACSSSession.id == session_id))
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    return session


async def save_autogen_config(
    db: AsyncSession,
    acss_session_id: UUID,
    config: AutoGenConfigRequest,
    redis_client: Redis,
) -> ACSSSession:
    """
    Validates template_name, persists config, marks loadCandidateGdl.status='done'.
    Note: filePath stays null at setup time — execution-time auto-gen sub-step
    (plan 02-07) writes the synthetic CSV and sets filePath then.
    """
    if config.template_name not in list_template_names():
        raise HTTPException(status_code=400, detail=f"Unknown antenna template: {config.template_name!r}")

    tilt_range = get_tilt_range(config.template_name)
    if config.electrical_tilt_deg is not None:
        t = float(config.electrical_tilt_deg)
        if t < tilt_range["min"] or t > tilt_range["max"]:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"electrical_tilt_deg={t}° is outside the {config.template_name!r} "
                    f"antenna's supported range ({tilt_range['min']}°..{tilt_range['max']}°)."
                ),
            )

    session = await _get_session(db, acss_session_id)
    setup_state = dict(session.setup_state or {})
    load_state = dict(setup_state.get("loadCandidateGdl") or {})
    load_state.update({
        "status": "done",
        "fileName": None,
        "filePath": None,  # populated at execution time
        "autoGenConfig": {
            "n": config.n,
            "threshold_dbm": config.threshold_dbm,
            "template_name": config.template_name,
            "seed": config.seed,
            # None == "let the brain decide per site"; a float == operator override.
            "electrical_tilt_deg": (
                float(config.electrical_tilt_deg)
                if config.electrical_tilt_deg is not None
                else None
            ),
            "enable_population_weighting": bool(config.enable_population_weighting),
            "generated_count": None,  # filled in by execution-time sub-step
        },
    })
    setup_state["loadCandidateGdl"] = load_state
    # Clear any stale candidates from a previous (file-upload) attempt on this session
    setup_state.pop("allCandidates", None)
    session.setup_state = setup_state
    flag_modified(session, "setup_state")
    await db.commit()
    await db.refresh(session)
    await RedisService.publish_log(
        redis_client, f"logs:{acss_session_id}",
        f"Auto-gen config saved: N={config.n} threshold={config.threshold_dbm} template={config.template_name} seed={config.seed}"
    )
    return session


async def delete_candidate(
    db: AsyncSession,
    acss_session_id: UUID,
    site_iid: str,
    redis_client: Redis,
) -> Dict:
    """Remove ONE site from setup_state['allCandidates']. Only allows
    deletion of auto-generated IIDs (refuses to mutate a manually-uploaded
    GDL session)."""
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
        f"Deleted auto-generated site {site_iid}; {len(remaining)} candidates remain"
    )
    return {
        "session_id": session.id,
        "deleted_site_iid": site_iid,
        "remaining_count": len(remaining),
    }
