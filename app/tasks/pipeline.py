import logging

import anyio
import httpx
from slugify import slugify

from app.celery_app import celery_app
from app.config import settings
from app.db import get_session
from ai_news_db.models import ArticleStatus
from ai_news_db.repositories import ArticleRepository, PipelineRunRepository

logger = logging.getLogger(__name__)


async def _run_pipeline(run_id: int, topic_id: int, topic_name: str, topic_slug: str) -> None:
    async with get_session() as session:
        run_repo = PipelineRunRepository(session)
        article_repo = ArticleRepository(session)

        run = await run_repo.get(run_id)
        if run is None:
            logger.error("PipelineRun %d not found", run_id)
            return

        # Mark as running if not already (manual trigger sets it before dispatching)
        if run.celery_task_id is None:
            run = await run_repo.mark_running(run, celery_task_id="unknown")

        try:
            # Call agent-orchestrator
            logger.info("Calling orchestrator for topic %r (run_id=%d)", topic_slug, run_id)
            async with httpx.AsyncClient(timeout=settings.orchestrator_timeout) as client:
                response = await client.post(
                    f"{settings.orchestrator_url}/orchestrate",
                    json={"topic": topic_name, "topic_slug": topic_slug},
                )
                response.raise_for_status()
                result = response.json()

            # Persist article draft
            title = result.get("title", f"{topic_name} — {__import__('datetime').date.today()}")
            article = await article_repo.create(
                topic_id=topic_id,
                title=title,
                slug=_unique_slug(title),
                summary=result.get("summary"),
                content=result.get("content"),
                status=ArticleStatus.DRAFT,
            )
            await session.commit()
            logger.info("Article %d saved as draft (run_id=%d)", article.id, run_id)

            # Notify publisher-service
            async with httpx.AsyncClient(timeout=30) as client:
                await client.post(
                    f"{settings.publisher_url}/publish",
                    json={"article_id": article.id},
                )

            await run_repo.mark_success(run)
            await session.commit()

        except Exception as exc:
            logger.exception("pipeline.run failed for run_id=%d: %s", run_id, exc)
            await run_repo.mark_failed(run, error_message=str(exc))
            await session.commit()
            raise


def _unique_slug(title: str) -> str:
    from datetime import date
    return f"{slugify(title)}-{date.today().isoformat()}"


@celery_app.task(name="pipeline.run", bind=True, max_retries=2, default_retry_delay=120)
def pipeline_run(self, run_id: int, topic_id: int, topic_name: str, topic_slug: str):
    """Execute the full agent pipeline for a single topic."""
    try:
        anyio.run(_run_pipeline, run_id, topic_id, topic_name, topic_slug)
    except Exception as exc:
        logger.exception("pipeline.run task error (run_id=%d): %s", run_id, exc)
        raise self.retry(exc=exc)
