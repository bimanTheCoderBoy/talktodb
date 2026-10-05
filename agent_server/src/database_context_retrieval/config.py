import os

RAG_RETRIEVAL_SERVICE_URL = os.getenv("RAG_RETRIEVAL_SERVICE_URL", "http://localhost:8010")
RAG_SERVICE_TIMEOUT = float(os.getenv("RAG_SERVICE_TIMEOUT", "30"))
CATALOG_RETRIEVAL_PATH = "/api/v1/catalog-retrieval/"
CATALOG_CONTEXT_MAX_TABLES = int(os.getenv("CATALOG_CONTEXT_MAX_TABLES", "5"))
