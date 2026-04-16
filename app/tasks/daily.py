import logging
from datetime import date

import anyio

from app.celery_app import celery_app
from app.db import get_session
from ai_news_db.repositories import ArticleRepository, PipelineRunRepository, TopicRepository

logger = logging.getLogger(__name__)


async def _dispatch_daily() -> None:
    today = date.today()
    async with get_session() as session:
        topic_repo = TopicRepository(session)
        article_repo = ArticleRepository(session)
        run_repo = PipelineRunRepository(session)

        topics = await topic_repo.list_active()
        logger.info("Daily pipeline — found %d active topics", len(topics))

        for topic in topics:
            already_done = await article_repo.exists_for_topic_on_date(topic.id, today)
            if already_done:
                logger.info("Skipping topic %r — article already exists for %s", topic.slug, today)
                continue

            run = await run_repo.create(topic_id=topic.id)
            await session.commit()

            celery_app.send_task(
                "pipeline.run",
                kwargs={
                    "run_id": run.id,
                    "topic_id": topic.id,
                    "topic_name": topic.name,
                    "topic_slug": topic.slug,
                },
                queue="pipeline",
            )
            logger.info("Dispatched pipeline.run for topic %r (run_id=%d)", topic.slug, run.id)


@celery_app.task(name="pipeline.daily", bind=True, max_retries=1)
def pipeline_daily(self):
    """Entry point triggered by Celery Beat. Iterates all active topics and dispatches pipeline.run for each."""
    try:
        anyio.from_thread.run_sync(lambda: None)  # ensure event loop exists
        anyio.run(_dispatch_daily)
    except Exception as exc:
        logger.exception("pipeline.daily failed: %s", exc)
        raise self.retry(exc=exc, countdown=60)
