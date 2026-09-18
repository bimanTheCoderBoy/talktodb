"""Configuration settings for the download service."""
import os

# Redis Configuration
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/1")

# Application Settings
API_TITLE = "Download Service"
API_VERSION = "1.0.0"
API_DESCRIPTION = "Convert markdown documents to PDF, MD, or CSV using FastAPI, Celery, and Redis"
