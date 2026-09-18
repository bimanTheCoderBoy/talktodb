from datetime import datetime

from pipeline_app.core.config import APIConfig
from pipeline_app.core.json_mapper import JsonMapper
from pipeline_app.db.engine import DatabaseManager
from pipeline_app.db.repository import location_repo
from pipeline_app.etl.engine import StreamingEngine
from pipeline_app.etl.utils import FlowResult
from pipeline_app.schemas import LocationModel

QUERY_TYPE = "LocationObjectv214Type"


async def execute_location_flow(
    db: DatabaseManager,
    api_config: APIConfig,
    imported_at: datetime,
) -> FlowResult:
    mapper = JsonMapper(LocationModel)
    engine = StreamingEngine(api_config, db)

    async def handler(session, page):
        models = mapper.map_batch(page)
        count = await location_repo.save_batch(
            session, models, imported_at=imported_at,
        )
        return {"location": count}

    return await engine.run("location", QUERY_TYPE, handler)