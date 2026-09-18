from __future__ import annotations

import logging

from sqlalchemy import text

from shared_server_libs.infra.user_session_registry import UserSessionRegistry

logger = logging.getLogger(__name__)

_SCOPE_SQL = text(
    """
    SELECT cell_iids FROM user_project_config
    WHERE email = :email AND project_name = :project
    """
)


class UserProjectScopeRepository:
    """Reads scoped cell IIDs from the user database (no project RLS)."""

    @staticmethod
    def _normalize_project(project_name: str) -> str:
        return project_name.lower().strip()

    @staticmethod
    def _normalize_email(email: str) -> str:
        return email.strip().lower()

    async def get_cell_iids(self, project_name: str, email: str) -> list[str]:
        project = self._normalize_project(project_name)
        normalized_email = self._normalize_email(email)
        sessionmaker = await UserSessionRegistry.get_sessionmaker()

        async with sessionmaker() as session:
            try:
                result = await session.execute(
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
