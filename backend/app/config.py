"""Application settings. All secrets come from environment variables.

Precedence (pydantic-settings): init kwargs > real environment variables > .env file > defaults.
Every variable MUST carry the ``NRIMS_`` prefix, e.g. ``NRIMS_DATABASE_URL``.
An un-prefixed ``DATABASE_URL`` is silently ignored by design - the container
therefore fails fast (see ``_reject_loopback_in_container``) instead of quietly
falling back to ``localhost`` and hanging.
"""

from enum import StrEnum
from functools import lru_cache
from typing import Self

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url

_PLACEHOLDER_MARKERS = ("change-me", "changeme", "placeholder")
_LOOPBACK = {"localhost", "127.0.0.1", "::1", "0.0.0.0"}  # noqa: S104


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
    # Set to true by the Dockerfile. Enables fail-fast checks for loopback hosts.
    in_container: bool = False

    database_url: SecretStr = SecretStr(
        "postgresql+asyncpg://nrims:change-me@localhost:5432/nrims"
    )
    valkey_url: SecretStr = SecretStr("redis://localhost:6379/0")
    secret_key: SecretStr = SecretStr("change-me-dev-only-0000000000000000")

    # Database tuning
    database_ssl: bool = False  # True -> asyncpg ssl="require"
    db_connect_timeout_seconds: float = 10.0
    db_command_timeout_seconds: float = 60.0
    db_pool_size: int = 10
    db_max_overflow: int = 10

    # Auth
    access_token_expire_minutes: int = 480
    login_max_attempts: int = 5
    login_lockout_seconds: int = 900

    # HTTP
    cors_origins: list[str] = Field(default_factory=list)
    docs_enabled: bool = True
    readiness_timeout_seconds: float = 10.0

    # Seeding (never used in production)
    seed_admin_password: SecretStr | None = None

    # ── helpers ────────────────────────────────────────────────
    @property
    def database_host(self) -> str:
        return make_url(self.database_url.get_secret_value()).host or ""

    @property
    def redacted_database_url(self) -> str:
        return make_url(self.database_url.get_secret_value()).render_as_string(hide_password=True)

    @model_validator(mode="after")
    def _reject_loopback_in_container(self) -> Self:
        """Inside Docker, 'localhost' is the container itself - never the DB."""
        if self.in_container:
            if self.database_host in _LOOPBACK:
                raise ConfigError(
                    f"NRIMS_DATABASE_URL points at '{self.database_host}' inside a container "
                    "(probably the compose file sets DATABASE_URL without the NRIMS_ prefix, "
                    "or a stale .env is being read). Use the compose service name, e.g. @db:5432."
                )
            valkey_host = make_url(self.valkey_url.get_secret_value()).host or ""
            if valkey_host in _LOOPBACK:
                raise ConfigError(
                    f"NRIMS_VALKEY_URL points at '{valkey_host}' inside a container; "
                    "use the compose service name, e.g. redis://valkey:6379/0"
                )
        return self

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
            if self.docs_enabled:
                raise ConfigError("NRIMS_DOCS_ENABLED must be false in production")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
