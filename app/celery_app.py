from celery import Celery
from celery.schedules import crontab

from app.config import settings

celery_app = Celery(
    "ai-news",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.tasks.daily", "app.tasks.pipeline"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)

# ---------------------------------------------------------------------------
# Beat schedule — parse cron expression from settings
# Format: "minute hour day_of_month month_of_year day_of_week"
# ---------------------------------------------------------------------------

def _parse_cron(expr: str) -> crontab:
    parts = expr.strip().split()
    if len(parts) != 5:
        raise ValueError(f"Invalid cron expression: {expr!r}")
    minute, hour, day_of_month, month_of_year, day_of_week = parts
    return crontab(
        minute=minute,
        hour=hour,
        day_of_month=day_of_month,
        month_of_year=month_of_year,
        day_of_week=day_of_week,
    )


celery_app.conf.beat_schedule = {
    "daily-pipeline": {
        "task": "pipeline.daily",
        "schedule": _parse_cron(settings.pipeline_cron_schedule),
    },
}
