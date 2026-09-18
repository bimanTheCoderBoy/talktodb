from typing import List
from api.db.database import user_db_session
from api.db.models import UserProjectConfig
from sqlalchemy import select

async def get_outer_polygon_from_user_db(user_email: str, project_name: str) -> List[List[float]]:
    """
    Get the outer polygon from the user db.
    """
    async with user_db_session() as session:
        cords = await session.execute(select(UserProjectConfig.cords).where(UserProjectConfig.email == user_email, UserProjectConfig.project_name == project_name))
        cords = cords.scalar()
        return cords