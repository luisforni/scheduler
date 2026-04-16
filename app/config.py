from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Celery
    celery_broker_url: str = "redis://redis:6379/1"
    celery_result_backend: str = "redis://redis:6379/2"

    # Database
    database_url: str = "postgresql+asyncpg://ai_news_user:changeme@db:5432/ai_news"

    # Pipeline cron — default: daily at 09:00 UTC
    pipeline_cron_schedule: str = "0 9 * * *"

    # Agent orchestrator
    orchestrator_url: str = "http://agent-orchestrator:8100"
    orchestrator_timeout: int = 300  # seconds

    # Publisher
    publisher_url: str = "http://publisher-service:8001"


settings = Settings()
