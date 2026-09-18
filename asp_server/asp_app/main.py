# import os
# os.environ["PROJ_LIB"] = os.path.join(
#     os.path.dirname(os.path.dirname(os.__file__)),
#     "Lib", "site-packages", "rasterio", "proj_data",
# )

import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
load_dotenv()

from asp_app.config.acss_config import get_acss_config, get_cors_config
from asp_app.api.sesssion_router import router as session_router
from asp_app.api.redis_router import router as redis_router
from asp_app.api.setup_router import router as setup_router
from asp_app.api.execution_router import router as execution_router
from asp_app.db.redis import get_redis_client
from asp_app.api.middleware.auth_middleware import AuthMiddleware

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.
    Handles startup and shutdown events.
    """
    # Startup
    print("=" * 50)
    print("ACSS Backend starting up...")
    config = get_acss_config()
    print(f"Application: {config.app_name} v{config.app_version}")
    print(f"Debug mode: {config.debug}")
    print(f"Server: http://{config.host}:{config.port}")
    print("=" * 50)
    
    yield
    
    # Shutdown
    redis_client = get_redis_client()
    await redis_client.aclose()
    await redis_client.connection_pool.disconnect()
    print("ACSS Backend shutting down...")


# Initialize FastAPI application
config = get_acss_config()

app = FastAPI(
    title=config.app_name,
    version=config.app_version,
    description="""ACSS Backend API""",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)


# Configure CORS
cors_config = get_cors_config()

app.add_middleware(AuthMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_config.allow_origins,
    allow_credentials=cors_config.allow_credentials,
    allow_methods=cors_config.allow_methods,
    allow_headers=cors_config.allow_headers,
)

# Include routers
app.include_router(session_router, prefix="/api/v1")
app.include_router(redis_router, prefix="/api/v1")
app.include_router(setup_router, prefix="/api/v1")
app.include_router(execution_router, prefix="/api/v1")

@app.get("/", tags=["Root"])
async def root():
    """Root endpoint - API health check."""
    return {
        "status": "healthy",
        "app": config.app_name,
        "version": config.app_version,
        "docs": "/docs",
        "redoc": "/redoc"
    }


@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint for monitoring."""
    return {
        "status": "healthy",
        "service": "acss-backend"
    }


if __name__ == "__main__":
    config = get_acss_config()
    uvicorn.run(
        "asp_app.main:app",
        host=config.host,
        port=config.port,
        reload=config.debug
    )
