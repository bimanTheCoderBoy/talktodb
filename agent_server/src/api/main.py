import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.auth_middleware import AuthMiddleware
from api.routers.sites_cells_router import router as sites_cells_router
from api.routers.project_router import router as project_router
from api.routers.user_config_router import router as user_config_router
from api.routers.audit_rules_router import router as audit_rules_router
from openinference.instrumentation.langchain import LangChainInstrumentor
# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============== Phoenix Tracing ==============
# Auto-instruments all LangChain/LangGraph LLM calls, tool calls, chains
OTEL_EXPORTER_OTLP_ENDPOINT = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
OTEL_EXPORTER_OTLP_PROTOCOL = os.getenv("OTEL_EXPORTER_OTLP_PROTOCOL")

if OTEL_EXPORTER_OTLP_ENDPOINT and OTEL_EXPORTER_OTLP_PROTOCOL:
    
    from phoenix.otel import register
        
    tracer_provider = register(
        project_name="raNora Langgraph Observability",
        endpoint=OTEL_EXPORTER_OTLP_ENDPOINT,
        protocol=OTEL_EXPORTER_OTLP_PROTOCOL,
        auto_instrument=False,
        batch=True

    )
    LangChainInstrumentor().instrument(tracer_provider=tracer_provider)

    logger.info(f"[PHOENIX] Tracing enabled → {OTEL_EXPORTER_OTLP_ENDPOINT}")
else:
    logger.warning(f"[PHOENIX] Tracing not enabled → OTEL_EXPORTER_OTLP_ENDPOINT: {OTEL_EXPORTER_OTLP_ENDPOINT}, OTEL_EXPORTER_OTLP_PROTOCOL: {OTEL_EXPORTER_OTLP_PROTOCOL}")

# ============== Computer skills (eager load) ==============

from computer.config.logger import get_computer_logger
from computer.config.tool import get_file_system_tool_config
from computer.skills.skill_discovery_adapter import FilesystemSkillDiscoveryAdapter
from computer.skills.skill_discovery_service import SkillDiscoveryService
from shared_server_libs.agent_db_access import init_agent_db_access, shutdown_agent_db_access
from shared_server_libs.infra.config import PostgresConnectionSettings, RedisSettings

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


# ============== Application ==============

app = FastAPI(
    title="TEOCO raNora Custom Langgraph Server",
    description="Custom endpoints for authentication and user management and project config for raNora",
    version="0.2.0",
    lifespan=lifespan,
)


# ============== Middleware ==============

app.add_middleware(AuthMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============== Routers ==============

app.include_router(sites_cells_router)
app.include_router(project_router)
app.include_router(user_config_router)
app.include_router(audit_rules_router)


# ============== Health ==============

@app.get("/health")
def health_check():
    """Health check endpoint (no auth required)."""
    return {"status": "healthy"}
