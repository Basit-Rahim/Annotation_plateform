from functools import lru_cache
from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEV_SECRET_KEY = "dev-secret-change-me"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env", "../.env"), extra="ignore")

    database_url: str = "postgresql://urdu_annot:urdu_annot@localhost:5432/urdu_annot"
    secret_key: str = DEV_SECRET_KEY
    environment: str = "development"

    admin_email: str = "admin@example.org"
    admin_password: str = "admin"

    audio_drop_dir: Path = Path("./data/incoming")
    audio_storage_dir: Path = Path("./data/audio")

    session_lifetime_minutes: int = 1440
    lease_duration_minutes: int = 120

    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    scheduler_enabled: bool = True

    @model_validator(mode="after")
    def _production_secrets(self) -> "Settings":
        """Refuse to run in production with placeholder or weak secrets."""
        if self.environment != "production":
            return self
        problems: list[str] = []
        if "CHANGE_ME" in self.secret_key or self.secret_key == DEV_SECRET_KEY or len(self.secret_key) < 32:
            problems.append("SECRET_KEY (use `openssl rand -hex 32`)")
        if "CHANGE_ME" in self.admin_password or len(self.admin_password) < 12:
            problems.append("ADMIN_PASSWORD (at least 12 characters)")
        if "CHANGE_ME" in self.database_url:
            problems.append("the database password inside DATABASE_URL")
        if problems:
            raise ValueError("Production .env is not configured: set " + ", ".join(problems))
        return self

    @property
    def sqlalchemy_url(self) -> str:
        """Force the psycopg (v3) driver regardless of how the URL was written."""
        url = self.database_url
        for prefix in ("postgresql+psycopg2://", "postgresql://", "postgres://"):
            if url.startswith(prefix):
                return "postgresql+psycopg://" + url[len(prefix):]
        return url

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
