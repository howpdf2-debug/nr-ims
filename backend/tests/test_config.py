import pytest

from app.config import Settings


def test_unprefixed_database_url_is_ignored(monkeypatch):
    monkeypatch.delenv("NRIMS_DATABASE_URL", raising=False)
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@db:5432/x")
    assert Settings(_env_file=None).database_host == "localhost"  # the original bug, pinned


def test_prefixed_env_wins_over_dotenv(monkeypatch, tmp_path):
    f = tmp_path / ".env"
    f.write_text("NRIMS_DATABASE_URL=postgresql+asyncpg://u:p@dotenv-host:5432/x\n")
    monkeypatch.setenv("NRIMS_DATABASE_URL", "postgresql+asyncpg://u:p@db:5432/x")
    assert Settings(_env_file=str(f)).database_host == "db"


def test_container_rejects_localhost_db(monkeypatch):
    monkeypatch.delenv("NRIMS_DATABASE_URL", raising=False)
    monkeypatch.setenv("NRIMS_IN_CONTAINER", "true")
    with pytest.raises(ValueError, match="inside a container"):
        Settings(_env_file=None)


def test_container_accepts_service_names(monkeypatch):
    monkeypatch.setenv("NRIMS_IN_CONTAINER", "true")
    monkeypatch.setenv("NRIMS_DATABASE_URL", "postgresql+asyncpg://u:p@db:5432/x")
    monkeypatch.setenv("NRIMS_VALKEY_URL", "redis://:p@valkey:6379/0")
    assert Settings(_env_file=None).database_host == "db"


def test_redacted_url_hides_password(monkeypatch):
    monkeypatch.setenv("NRIMS_DATABASE_URL", "postgresql+asyncpg://u:topsecret@db:5432/x")
    assert "topsecret" not in Settings(_env_file=None).redacted_database_url


def test_production_rejects_docs_and_placeholders(monkeypatch):
    monkeypatch.delenv("NRIMS_DATABASE_URL", raising=False)
    monkeypatch.setenv("NRIMS_ENV", "production")
    monkeypatch.setenv("NRIMS_DATA_PROVIDER", "live")
    with pytest.raises(ValueError, match="placeholder"):
        Settings(_env_file=None)
