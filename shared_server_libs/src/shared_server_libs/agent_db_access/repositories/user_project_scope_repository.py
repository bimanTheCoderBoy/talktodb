from __future__ import annotations

import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

_SCOPE_SQL = text(
    """
    SELECT cell_iids FROM user_project_config
    WHERE LOWER(email) = LOWER(:email) AND LOWER(project_name) = LOWER(:project)
    """
)


class UserProjectScopeRepository:
    """Reads scoped cell IIDs from the ranora_config database (no project RLS)."""

    def __init__(self, ranora_config_session: AsyncSession) -> None:
        self._ranora_config_session = ranora_config_session

    @staticmethod
    def _normalize_project(project_name: str) -> str:
        return project_name.lower().strip()

    @staticmethod
    def _normalize_email(email: str) -> str:
        return email.strip().lower()

    async def get_cell_iids(self, project_name: str, email: str) -> list[str]:
        project = self._normalize_project(project_name)
        normalized_email = self._normalize_email(email)

        try:
            result = await self._ranora_config_session.execute(
                _SCOPE_SQL,
                {"email": normalized_email, "project": project},
            )
            cell_iids = result.scalar_one_or_none()
            if cell_iids is None:
                return []
            return list(cell_iids)
        except Exception:
            logger.exception(
                "Error loading cell_iids for email=%s project=%s",
                normalized_email,
                project,
            )
            return []
