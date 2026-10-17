"""Application settings. All secrets come from environment variables."""

from enum import StrEnum
from functools import lru_cache
from typing import Self

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_PLACEHOLDER_MARKERS = ("change-me", "changeme", "placeholder")


class Env(StrEnum):
    DEVELOPMENT = "development"
    TEST = "test"
    PRODUCTION = "production"


class DataProvider(StrEnum):
    LIVE = "live"
    SIMULATOR = "simulator"


class ConfigError(ValueError):
    """Raised when the configuration is unsafe for the selected environment."""


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="NRIMS_", extra="ignore")

    env: Env = Env.DEVELOPMENT
    data_provider: DataProvider = DataProvider.SIMULATOR
    log_level: str = "INFO"

    database_url: SecretStr = SecretStr(
        "postgresql+asyncpg://nrims:change-me@localhost:5432/nrims"
    )
    valkey_url: SecretStr = SecretStr("redis://localhost:6379/0")
    secret_key: SecretStr = SecretStr("change-me-dev-only-0000000000000000")

    cors_origins: list[str] = Field(default_factory=list)
    readiness_timeout_seconds: float = 10.0

    @model_validator(mode="after")
    def _enforce_production_safety(self) -> Self:
        if self.env is Env.PRODUCTION:
            if self.data_provider is DataProvider.SIMULATOR:
                raise ConfigError("DATA_PROVIDER=simulator is forbidden when ENV=production")
            for name in ("secret_key", "database_url"):
                value = getattr(self, name).get_secret_value().lower()
                if any(marker in value for marker in _PLACEHOLDER_MARKERS):
                    raise ConfigError(f"{name} still contains a placeholder value in production")
            if len(self.secret_key.get_secret_value()) < 32:
                raise ConfigError("secret_key must be at least 32 characters in production")
            if "*" in self.cors_origins:
                raise ConfigError("Wildcard CORS origin is forbidden in production")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()