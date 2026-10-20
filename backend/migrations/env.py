import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool, text
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

import app.models  # noqa: F401  (registers every model on Base.metadata)
from app.config import get_settings
from app.db.base import Base
from app.db.session import asyncpg_connect_args

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

settings = get_settings()
# configparser treats '%' as interpolation -> escape it or passwords containing '%' crash.
config.set_main_option("sqlalchemy.url", settings.database_url.get_secret_value().replace("%", "%%"))
# CRITICAL: import all models so Base.metadata sees them before autogenerate

import app.models  # noqa: F401

target_metadata = Base.metadata
MIGRATION_LOCK_ID = 727274  # arbitrary constant; serialises concurrent `alembic upgrade`


def run_migrations_offline() -> None:
    context.configure(
        url=settings.database_url.get_secret_value(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
    with context.begin_transaction():
        # Safe with multiple replicas / CI jobs: the second runner waits, then no-ops.
        connection.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": MIGRATION_LOCK_ID})
        context.run_migrations()


async def run_async_migrations() -> None:
    # Same URL + same asyncpg args as the application: one code path, one behaviour.
    connectable = create_async_engine(
        settings.database_url.get_secret_value(),
        poolclass=pool.NullPool,
        connect_args=asyncpg_connect_args(settings),
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_async_migrations())
