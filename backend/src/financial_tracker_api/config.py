"""Application settings loaded from environment."""

from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[3]

_WEAK_SECRETS = frozenset(
    {
        "dev-only-change-me",
        "change-me-in-production",
        "replace-me",
        "secret",
        "changeme",
    }
)


class Settings(BaseSettings):
    """Runtime configuration for the API."""

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        env_nested_delimiter="__",
    )

    app_name: str = "Financial Tracker API"
    environment: str = "development"  # development | production
    secret_key: str = "dev-only-change-me"
    access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 7
    database_url: str = f"sqlite:///{REPO_ROOT / 'data' / 'app.db'}"
    data_dir: Path = REPO_ROOT / "data"
    receipts_dir: Path | None = None
    cors_origins: str = "http://localhost:5173,http://localhost:3000"
    hst_rate: float = 0.13
    max_upload_bytes: int = 12 * 1024 * 1024
    enable_docs: bool | None = None  # None → auto from environment

    @field_validator("secret_key")
    @classmethod
    def _reject_weak_secret_in_production(cls, value: str, info) -> str:  # noqa: ANN001
        # Validated again after full model load using environment field.
        return value

    def docs_enabled(self) -> bool:
        if self.enable_docs is not None:
            return self.enable_docs
        return self.environment != "production"

    def assert_secure(self) -> None:
        """Refuse to boot with weak secrets outside development."""
        if self.environment == "production" and self.secret_key.strip().lower() in _WEAK_SECRETS:
            raise RuntimeError(
                "SECRET_KEY is a known default. Set a strong SECRET_KEY before "
                "running with ENVIRONMENT=production."
            )
        if self.environment == "production" and len(self.secret_key) < 32:
            raise RuntimeError("SECRET_KEY must be at least 32 characters in production.")


@lru_cache
def get_settings() -> Settings:
    """Return cached settings instance."""
    settings = Settings()
    if settings.receipts_dir is None:
        settings.receipts_dir = settings.data_dir / "receipts"
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.receipts_dir.mkdir(parents=True, exist_ok=True)
    settings.assert_secure()
    return settings
