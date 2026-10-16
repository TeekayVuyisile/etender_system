from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """App configuration.

    Each field is read from an environment variable with the same name
    (case-insensitive), falling back to the .env file, then to the default below.
    """

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Tender Insight Hub"
    environment: str = "development"
    # Frontend origins allowed to call this API from a browser (Vite runs on port 5173)
    cors_origins: list[str] = ["http://localhost:5173"]

    database_url: str = "sqlite:///./local.db"

    mongodb_url: str = "mongodb://localhost:27017"
    mongodb_db_name: str = "tender_insight_hub"

    jwt_secret_key: str = "dev-only-insecure-secret-change-me-in-env"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    groq_api_key: str | None = None
    groq_model: str = "openai/gpt-oss-120b"
    groq_base_url: str = "https://api.groq.com/openai/v1"

    # Automatic tender sync. Enable it here to run inside the API process, or run
    # `python -m app.cli scheduler` as a separate worker.
    sync_schedule_enabled: bool = False
    sync_interval_hours: float = 6
    sync_days: int = 3

    # "Try the demo": one-click demo teams with sample data, deleted after demo_ttl_hours.
    demo_mode_enabled: bool = False
    demo_ttl_hours: float = 24

    @field_validator("database_url")
    @classmethod
    def use_psycopg_driver(cls, value: str) -> str:
        # Neon gives "postgresql://..." URLs; SQLAlchemy needs to be told to use psycopg 3.
        if value.startswith("postgresql://"):
            return value.replace("postgresql://", "postgresql+psycopg://", 1)
        return value


settings = Settings()
