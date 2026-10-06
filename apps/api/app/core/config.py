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
    # Browser-reachable S3 address used in presigned URLs (MinIO runs behind another hostname
    # inside Docker). Falls back to `s3_endpoint_url`.
    s3_public_endpoint_url: str | None = None
    s3_access_key: str | None = None
    s3_secret_key: str | None = None
    max_upload_bytes: int = 100 * 1024 * 1024  # SPEC section 9: 100 MB
    upload_url_ttl_seconds: int = 600
    download_url_ttl_seconds: int = 300
    aws_region: str = "ap-southeast-1"
    ses_sender: str = "no-reply@example.test"
    mail_backend: str = "smtp"  # smtp (mailpit in dev) | ses | memory (tests)
    smtp_host: str = "localhost"
    smtp_port: int = 1025
    # Re-run the alert engine in the background after writes that can change an alert (SPEC 7).
    alert_refresh_on_write: bool = True
    app_base_url: str = "http://localhost:5173"
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
