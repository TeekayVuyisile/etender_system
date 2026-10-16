from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """App configuration.

    Each field is read from an environment variable with the same name
    (case-insensitive), falling back to the .env file, then to the default below.
    Example: setting APP_NAME=Foo in .env overrides app_name.
    """

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Tender Insight Hub"
    environment: str = "development"
    # Frontend origins allowed to call this API from a browser (Vite runs on port 5173)
    cors_origins: list[str] = ["http://localhost:5173"]


settings = Settings()
