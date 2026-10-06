from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://qlda:qlda@db:5432/qlda"
    jwt_secret: str = "change-me"
    jwt_access_minutes: int = 15
    jwt_refresh_days: int = 7
    cookie_secure: bool = True
    s3_bucket: str = "qlda-documents"
    s3_endpoint_url: str | None = None
    aws_region: str = "ap-southeast-1"
    ses_sender: str = "no-reply@example.test"
    cors_origins: str = "http://localhost:5173"
    app_timezone: str = "Asia/Ho_Chi_Minh"
    alert_run_hours: str = "6,13"
    ai_provider: str = "none"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
