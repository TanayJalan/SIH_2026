"""Application configuration loaded from environment variables."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_DEV_SECRET = "dev-only-change-me-before-deploying"


class Settings(BaseSettings):
    """Runtime settings for the API.

    Environment variables use upper-case names (for example ``DATABASE_URL``).
    A repository-root ``.env`` file is loaded automatically for local runs.
    """

    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "AICTE Approval Workflow"
    app_version: str = "0.1.0"
    environment: Literal["development", "test", "production"] = "development"
    debug: bool = False
    demo_mode: bool = False
    secret_key: SecretStr = SecretStr(_DEV_SECRET)
    access_token_expire_minutes: int = Field(default=480, ge=1)
    jwt_algorithm: str = "HS256"

    database_url: str = "postgresql+psycopg://aicte:aicte_dev_password@localhost:5432/aicte"
    cors_origins: str = "http://localhost:5173,http://localhost:3000"
    log_level: str = "INFO"

    frontend_url: str = "http://localhost:5173"
    storage_dir: Path = Path("/storage")

    smtp_host: str = "localhost"
    smtp_port: int = Field(default=1025, ge=1, le=65535)
    smtp_from: str = "no-reply@aicte.local"
    notifications_enabled: bool = True
    """Send EMAIL/SMS channels. Disable in tests or offline demos."""

    alert_scan_enabled: bool = True
    """Run the in-process alert scan job on a fixed interval."""
    alert_scan_interval_minutes: int = Field(default=15, ge=1, le=60)
    """Minutes between deadline, SLA, deficiency and document scans."""

    compliance_monitor_enabled: bool = True
    """Run the nightly APScheduler compliance re-evaluation job."""
    compliance_monitor_hour: int = Field(default=2, ge=0, le=23)
    """Battery-local hour the nightly compliance job runs at."""

    seed_admin_email: str = "admin@example.edu"
    seed_admin_password: SecretStr = SecretStr("ChangeMe123!")
    seed_admin_name: str = "Demo Super Admin"
    seed_demo_password: SecretStr = SecretStr("ChangeMe123!")

    @field_validator("log_level")
    @classmethod
    def _normalise_log_level(cls, value: str) -> str:
        level = value.upper()
        if level not in {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"}:
            raise ValueError("log_level must be a standard logging level")
        return level

    @model_validator(mode="after")
    def _reject_unsafe_production_defaults(self) -> "Settings":
        if self.environment == "production" and self.secret_key.get_secret_value() == _DEV_SECRET:
            raise ValueError("SECRET_KEY must be changed in production")
        if self.environment == "production" and self.demo_mode:
            raise ValueError("DEMO_MODE must be false in production")
        return self

    @property
    def cors_origin_list(self) -> list[str]:
        """Return configured CORS origins as a normalised list."""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide settings instance."""
    return Settings()
