from celery import Celery
from app.config import settings

celery_app = Celery("ai78qa", broker=settings.redis_url, backend=settings.redis_url)
celery_app.conf.update(task_serializer="json", accept_content=["json"], result_serializer="json", task_track_started=True, task_acks_late=True, worker_prefetch_multiplier=1, task_soft_time_limit=900, task_time_limit=960)

@celery_app.task(name="training.explore", bind=True, autoretry_for=(ConnectionError,), retry_backoff=True, max_retries=2)
def explore_training_session(self, session_id: str):
    # Browser implementation is deliberately separate from the web/API request process.
    return {"session_id": session_id, "status": "queued_for_browser_worker", "message": "Browser worker adapter not configured yet."}
