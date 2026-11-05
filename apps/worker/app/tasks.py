from celery import Celery
from app.browser_discovery import run_exploration
import os

redis_url = os.getenv("REDIS_URL", "redis://redis:6379/0")
celery_app = Celery("ai78qa-worker", broker=redis_url, backend=redis_url)
celery_app.conf.update(task_serializer="json", accept_content=["json"], result_serializer="json", task_track_started=True, task_acks_late=True, worker_prefetch_multiplier=1, task_soft_time_limit=900, task_time_limit=960)

@celery_app.task(name="training.explore")
def explore_training_session(session_id: str):
    return run_exploration(session_id)
