from fastapi import APIRouter, HTTPException, Depends, Body, Header, Query, Request
from typing import List, Optional
from uuid import UUID

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from asp_app.db.models import ACSSSession
from asp_app.db.schemas.session import ACSSSessionResponse, ACSSSessionCreate
from asp_app.services.session_service import SessionService
from asp_app.db.database import get_db_session
from asp_app.db.redis import get_redis_client
from redis import Redis

router = APIRouter(
    prefix="/session",
    tags=["Session"]
)



@router.post("/create_or_get", response_model=ACSSSessionResponse)
async def create_or_get_session(
    session_data: ACSSSessionCreate,
    request: Request,
    db: AsyncSession = Depends(get_db_session),
    redis_client: Redis = Depends(get_redis_client)
):
    user_id = request.state.user.get("identity", None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    session_data.user_id = user_id
    return await SessionService.create_or_get_session(db, session_data, redis_client)


@router.get("/list", response_model=List[ACSSSessionResponse])
async def list_sessions(
    request: Request,
    x_project_name: str = Header(..., description="Project name to filter sessions"),
    limit: int = Query(20, ge=1, le=100, description="Max sessions to return"),
    db: AsyncSession = Depends(get_db_session),
):
    """List all ASP sessions for a project, most recent first."""

    user_id = request.state.user.get("identity", None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    result = await db.execute(
        select(ACSSSession)
        .where(ACSSSession.project_name == x_project_name)
        .where(ACSSSession.user_id == user_id)
        .order_by(desc(ACSSSession.created_at))
        .limit(limit)
    )

    sessions = result.scalars().all()

    return sessions 

@router.delete("/{session_id}")
async def delete_session(
    session_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db_session),
):
    """Delete an ASP session by ID."""
    user_id = request.state.user.get("identity", None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    result = await db.execute(
        select(ACSSSession).where(ACSSSession.id == session_id).where(ACSSSession.user_id == user_id)
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    await db.delete(session)
    await db.commit()
    return {"detail": "Session deleted"}
