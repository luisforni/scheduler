FROM python:3.11-slim AS base

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY ../db-service /db-service
RUN pip install --no-cache-dir /db-service

COPY pyproject.toml .
RUN pip install --no-cache-dir -e ".[dev]"

COPY . .

# ---------------------------------------------------------------------------
# Default: run both Beat (scheduler) and worker in one container for dev.
# In production, split into two separate services.
# ---------------------------------------------------------------------------
CMD ["celery", "-A", "app.celery_app", "worker", "--beat", \
     "--loglevel=info", "--queues=pipeline,publish", "--scheduler=celery.beat.PersistentScheduler"]

FROM base AS production
CMD ["celery", "-A", "app.celery_app", "worker", "--beat", \
     "--loglevel=info", "--queues=pipeline,publish", "--scheduler=celery.beat.PersistentScheduler"]
