from fastapi import FastAPI
from dotenv import load_dotenv
from contextlib import asynccontextmanager
import os
import uvicorn
from .config.server_config import get_server_config
from .core.exception_handler import exception_handler
from .apis.v1.retrieval_router import retrieval_router
from fastapi.middleware.cors import CORSMiddleware
from .core.logger import CustomLogger
from .core.lancedb_client import LanceDBClient
from .adapters.embedding_adapter import EmbeddingAdapter
from .adapters.reranker_adapter import RerankerAdapter
load_dotenv()

server_config = get_server_config()


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Starting up...")
    CustomLogger.initialize()
    await LanceDBClient.initialize()
    EmbeddingAdapter.initialize()
    RerankerAdapter.initialize()
    yield
    print("Shutting down...")


app = FastAPI(
    title=server_config.name,
    description=server_config.description,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {"message": "Hello, World!"}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "rag-retrieval-server"}

app.include_router(retrieval_router, prefix="/api/v1")
app.add_exception_handler(Exception, exception_handler)



if __name__ == "__main__":
    uvicorn.run("retrieval_app.server:app", host=server_config.host, port=server_config.port, reload=server_config.debug)