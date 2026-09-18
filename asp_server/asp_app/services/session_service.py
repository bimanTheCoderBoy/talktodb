from uuid import UUID
from sqlalchemy import select
from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from asp_app.db.models import ACSSSession, SessionStatus
from asp_app.db.schemas.session import ACSSSessionCreate, ACSSSessionResponse
import json

from redis import Redis

from asp_app.services.project_service import ProjectService
from asp_app.services.redis_service import RedisService

class SessionService:

    @staticmethod
    async def create_or_get_session(
        db: AsyncSession,
        session_data: ACSSSessionCreate,
        redis_client: Redis,
    ) -> ACSSSession:
        key=f"logs:{session_data.acss_session_id}"
        try:
            # Check if session exists
            result = await db.execute(select(ACSSSession).where(ACSSSession.id == session_data.acss_session_id))
            acss_session = result.scalar_one_or_none()
            if acss_session:
                if acss_session.user_id != session_data.user_id:
                    raise HTTPException(status_code=403, detail="Forbidden....You are not authorized to access this session!")
                await RedisService.publish_log(redis_client, key, "Session already exists returning existing session")

                return acss_session
            else:
                project_cords = await ProjectService.get_outer_polygon_from_kml(
                    session_data.project_name
                )
                await RedisService.publish_log(redis_client, key, "Got the Project Coords.. creating session")
                # Initialize setup_state with loadProject as done
                initial_setup_state = {
                    "loadProject": {"status": "done"},
                    "polygon": {
                        "status": "pending",
                        "coords": None,
                        "boundaryRadius": 5.0,
                        "boundaryCoords": None,
                        "vertices": 0,
                        "timestamp": None,
                    },
                    "loadCandidateGdl": {
                        "status": "pending",
                        "fileName": None,
                        "filePath": None,
                    },
                    "defineGoal": {
                        "status": "pending",
                        "goalType": "increase_rsrp",
                        "parameters": {},
                    },
                }

                acss_session = ACSSSession(
                    id=session_data.acss_session_id,
                    project_name=session_data.project_name,
                    user_id=session_data.user_id,
                    project_cords=project_cords,
                    status=SessionStatus.PENDING,
                    current_step=None,
                    setup_state=initial_setup_state,
                )
            
                db.add(acss_session)
                await db.commit()
                await db.refresh(acss_session)  
                await RedisService.publish_log(redis_client, key, "Session created successfully returning new session")
                
                return acss_session

        except IntegrityError:
            await db.rollback()
            raise HTTPException(
                status_code=409,
                detail="Session with this ID already exists",
            )

        except Exception as e:
            await db.rollback()
            raise HTTPException(
                status_code=500,
                detail=f"Failed to create session: {str(e)}",
            )

    @staticmethod
    async def update_session_job_id(db: AsyncSession, session_id: UUID, job_id: str, redis_client: Redis) -> dict:
        try:
            result = await db.execute(select(ACSSSession).where(ACSSSession.id == session_id))
            session = result.scalar_one_or_none()
            if session:
                session.job_id = job_id
                flag_modified(session, "job_id")
                await db.commit()
                await db.refresh(session)
                await RedisService.publish_log(redis_client, f"logs:{session_id}", f"Started execution successfully with job id : {job_id}")
                return {"message": "Session job id updated succes   sfully", "session_id": session_id, "job_id": job_id}
            else:
                raise HTTPException(status_code=404, detail="Session not found")
        except Exception as e:
            await db.rollback()
            raise HTTPException(status_code=500, detail=f"Failed to update session job id: {str(e)}")
    