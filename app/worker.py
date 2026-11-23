from celery import Celery
from celery.schedules import crontab
from app.config import settings

celery_app = Celery(
    "url_monitor",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
)

# الجدولة التلقائية للـ Beat Container
celery_app.conf.beat_schedule = {
    "recheck-recent-urls-every-minute": {
        "task": "app.tasks.periodic_health_sweep",
        "schedule": 60.0,  # كل 60 ثانية
    },
    "cleanup-old-jobs-daily": {
        "task": "app.tasks.cleanup_old_jobs",
        "schedule": crontab(hour=0, minute=0),  # يومياً منتصف الليل
    },
}