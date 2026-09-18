import logging
from datetime import datetime
from typing import List, Optional

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException

from api.db.models import UserProjectConfig
from api.schemas.user_config import UserProjectConfigCreate
from security.encryption.iid_hash_utils import HASHING_ENABLED

logger = logging.getLogger(__name__)


class UserConfigService:
    """Service for user_project_config table operations."""

    # ------------------------------------------------------------------
    # POST (upsert)
    # ------------------------------------------------------------------

    @staticmethod
    async def upsert(
        db: AsyncSession,
        data: UserProjectConfigCreate,
    ) -> UserProjectConfig:
        """
        Create or update a user_project_config row.

        Uses the composite PK (email, project_name) to decide
        whether to INSERT or UPDATE.
        """
        try:
            result = await db.execute(
                select(UserProjectConfig).where(
                    UserProjectConfig.email == data.email,
                    UserProjectConfig.project_name == data.project_name,
                )
            )
            existing = result.scalar_one_or_none()

            if existing:
                existing.cords = data.cords or []
                existing.cell_iids = data.cell_iids or []
                existing.updated_at = datetime.now()
                await db.flush()
                await db.refresh(existing)
                return existing

            row = UserProjectConfig(
                email=data.email,
                project_name=data.project_name,
                cords=data.cords or [],
                cell_iids=data.cell_iids or [],
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )
            db.add(row)
            await db.flush()
            await db.refresh(row)
            return row

        except HTTPException:
            raise
        except Exception as e:
            logger.exception("Error upserting user_project_config")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to save user project config: {str(e)}",
            )

    # ------------------------------------------------------------------
    # GET
    # ------------------------------------------------------------------

    @staticmethod
    async def get(
        db: AsyncSession,
        email: str,
        project_name: str,
    ) -> Optional[UserProjectConfig]:
        """
        Fetch a single user_project_config row by (email, project_name).
        Returns None if not found.
        """
        try:
            result = await db.execute(
                select(UserProjectConfig).where(
                    UserProjectConfig.email == email,
                    UserProjectConfig.project_name == project_name,
                )
            )
            return result.scalar_one_or_none()
        except Exception as e:
            logger.exception("Error fetching user_project_config")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to fetch user project config: {str(e)}",
            )
    @staticmethod
    async def get_cells_in_polygon(cords: List[List[float]], db: AsyncSession) -> List[int]:
        """
        Get the cells in the polygon.
        """
        try:
            coords_str = ",".join([f"{lon} {lat}" for lon, lat in cords])
            polygon = f"(({coords_str}))"

            QUERY = f"""
            SELECT iid
            FROM cell_lte
            WHERE location_iid IN (
                SELECT iid
                FROM location
                WHERE ST_Within(
                    geom::geometry,
                    ST_GeomFromText('POLYGON{polygon}', 4326)
                )
            )
            UNION
            SELECT iid
            FROM cell_nr
            WHERE location_iid IN (
                SELECT iid
                FROM location
                WHERE ST_Within(
                    geom::geometry,
                    ST_GeomFromText('POLYGON{polygon}', 4326)
                )
            );
            """

            result = await db.execute(text(QUERY))
            hashed_iids = result.scalars().all()

            # Reverse-map hashed IIDs to originals so user_project_config stores raw values
            if HASHING_ENABLED and hashed_iids:
                map_result = await db.execute(
                    text("SELECT hash, original FROM iid_mapping WHERE hash = ANY(:hashes)"),
                    {"hashes": list(hashed_iids)},
                )
                rmap = {r.hash: r.original for r in map_result}
                return [rmap.get(h, h) for h in hashed_iids]

            return hashed_iids
        except Exception as e:
            logger.exception("Error getting cells in polygon")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to get cells in polygon: {str(e)}",
            )