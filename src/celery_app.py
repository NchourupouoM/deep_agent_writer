import os
from celery import Celery
from dotenv import load_dotenv

load_dotenv()

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# Instanciation de l'application Celery
celery_app = Celery(
    "deepagent_tasks",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["src.tasks"]
)

# Configuration Celery
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    broker_connection_retry_on_startup=True
)

if __name__ == "__main__":
    celery_app.start()