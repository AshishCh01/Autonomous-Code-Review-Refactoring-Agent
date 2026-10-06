from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    github_app_id: str = ""
    github_private_key_path: str = ""
    github_webhook_secret: str = ""
    llm_api_key: str = ""
    database_url: str = "postgresql+psycopg://quorum:quorum@localhost:5432/quorum"
    redis_url: str = "redis://localhost:6379/0"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

settings = Settings()
