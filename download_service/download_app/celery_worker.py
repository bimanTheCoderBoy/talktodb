"""Celery worker entry point for the download service."""
from download_app.tasks.celery_tasks import celery_app

if __name__ == "__main__":
    celery_app.start()
