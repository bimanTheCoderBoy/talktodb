import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from openinference.instrumentation.langchain import LangChainInstrumentor

from api.auth_middleware import AuthMiddleware
from computer.config.logger import get_computer_logger
from computer.config.tool import get_file_system_tool_config
from computer.skills.skill_discovery_adapter import FilesystemSkillDiscoveryAdapter
from computer.skills.skill_discovery_service import SkillDiscoveryService
from shared_server_libs.agent_db_access import init_agent_db_access, shutdown_agent_db_access
from shared_server_libs.infra.config import PostgresConnectionSettings, RedisSettings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

OTEL_EXPORTER_OTLP_ENDPOINT = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
OTEL_EXPORTER_OTLP_PROTOCOL = os.getenv("OTEL_EXPORTER_OTLP_PROTOCOL")

if OTEL_EXPORTER_OTLP_ENDPOINT and OTEL_EXPORTER_OTLP_PROTOCOL:
    from phoenix.otel import register

    tracer_provider = register(
        project_name="talkToDB LangGraph",
        endpoint=OTEL_EXPORTER_OTLP_ENDPOINT,
        protocol=OTEL_EXPORTER_OTLP_PROTOCOL,
        auto_instrument=False,
        batch=True,
    )
    LangChainInstrumentor().instrument(tracer_provider=tracer_provider)
    logger.info("[PHOENIX] Tracing enabled → %s", OTEL_EXPORTER_OTLP_ENDPOINT)
else:
    logger.warning(
        "[PHOENIX] Tracing disabled (OTEL_EXPORTER_OTLP_ENDPOINT=%s, OTEL_EXPORTER_OTLP_PROTOCOL=%s)",
        OTEL_EXPORTER_OTLP_ENDPOINT,
        OTEL_EXPORTER_OTLP_PROTOCOL,
    )

computer_skills_logger = get_computer_logger("computer.skills.startup")
SKILLS_ROOT = Path(get_file_system_tool_config.base_dir) / "computer" / "skills"


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        init_agent_db_access(
            PostgresConnectionSettings.from_env(),
            RedisSettings.from_env(),
        )
        SkillDiscoveryService(FilesystemSkillDiscoveryAdapter(), SKILLS_ROOT).init()
    except RuntimeError as e:
        computer_skills_logger.error("[SKILLS] Startup skill discovery failed: %s", e, exc_info=True)
        raise
    yield
    await shutdown_agent_db_access()


app = FastAPI(
    title="talkToDB LangGraph Server",
    description="LangGraph computer graph with Keycloak JWT auth middleware",
    version="0.3.0",
    lifespan=lifespan,
)

app.add_middleware(AuthMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health_check():
    """Health check endpoint (no auth required)."""
    return {"status": "healthy"}
