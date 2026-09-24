from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ApiSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = Field(default="development", validation_alias="APP_ENV")
    log_level: str = Field(default="INFO", validation_alias="LOG_LEVEL")
    redis_url: str | None = Field(default=None, validation_alias="REDIS_URL")
    worker_heartbeat_seconds: int = Field(
        default=10, ge=1, le=300, validation_alias="WORKER_HEARTBEAT_SECONDS"
    )
    worker_stale_after_seconds: int = Field(
        default=60, ge=10, le=3600, validation_alias="WORKER_STALE_AFTER_SECONDS"
    )
    database_url: str = Field(
        default="postgresql+psycopg://shopfilter:shopfilter@localhost:5432/shopfilter",
        validation_alias="DATABASE_URL",
    )
    minio_endpoint: str = Field(default="localhost:9000", validation_alias="MINIO_ENDPOINT")
    minio_access_key: str = Field(default="shopfilter", validation_alias="MINIO_ACCESS_KEY")
    minio_secret_key: str = Field(default="shopfilter-dev-only", validation_alias="MINIO_SECRET_KEY")
    minio_secure: bool = Field(default=False, validation_alias="MINIO_SECURE")
    minio_bucket: str = Field(
        default="shopfilter-artifacts", validation_alias="MINIO_BUCKET"
    )
    session_duration_hours: int = Field(
        default=12, ge=1, le=720, validation_alias="SESSION_DURATION_HOURS"
    )
    session_cookie_secure: bool = Field(
        default=False, validation_alias="SESSION_COOKIE_SECURE"
    )
    public_web_url: str = Field(
        default="http://localhost:3000", validation_alias="PUBLIC_WEB_URL"
    )
    email_verification_expiry_minutes: int = Field(
        default=60, ge=5, le=10080, validation_alias="EMAIL_VERIFICATION_EXPIRY_MINUTES"
    )
    email_verification_email_directory: str | None = Field(
        default=None, validation_alias="EMAIL_VERIFICATION_EMAIL_DIRECTORY"
    )
    password_reset_expiry_minutes: int = Field(
        default=30, ge=5, le=1440, validation_alias="PASSWORD_RESET_EXPIRY_MINUTES"
    )
    password_reset_email_directory: str | None = Field(
        default=None, validation_alias="PASSWORD_RESET_EMAIL_DIRECTORY"
    )
    smtp_host: str | None = Field(default=None, validation_alias="SMTP_HOST")
    smtp_port: int = Field(default=1025, ge=1, le=65535, validation_alias="SMTP_PORT")
    smtp_from_email: str = Field(
        default="no-reply@shopfilter.local", validation_alias="SMTP_FROM_EMAIL"
    )
    smtp_use_starttls: bool = Field(
        default=False, validation_alias="SMTP_USE_STARTTLS"
    )
    smtp_username: str | None = Field(default=None, validation_alias="SMTP_USERNAME")
    smtp_password: str | None = Field(default=None, validation_alias="SMTP_PASSWORD")


@lru_cache
def get_settings() -> ApiSettings:
    return ApiSettings()
