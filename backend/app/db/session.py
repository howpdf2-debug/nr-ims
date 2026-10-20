from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.config import Settings, get_settings


def asyncpg_connect_args(settings: Settings) -> dict:
    """Single source of truth for asyncpg arguments (used by app AND alembic)."""
    return {
        # Explicit: never let asyncpg negotiate TLS against the plain-text compose DB.
        "ssl": "require" if settings.database_ssl else False,
        "timeout": settings.db_connect_timeout_seconds,  # fail in 10s, not 60s
        "command_timeout": settings.db_command_timeout_seconds,
        "server_settings": {"application_name": "nr-ims-backend"},
    }


def build_engine(settings: Settings) -> AsyncEngine:
    return create_async_engine(
        settings.database_url.get_secret_value(),
        pool_pre_ping=True,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_recycle=1800,
        pool_timeout=30,
        connect_args=asyncpg_connect_args(settings),
    )


def build_sessionmaker(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


# Module-level handles are for CLI scripts (seed_*.py). The web app builds its own
# engine in create_app() and stores it on app.state (see app.deps.get_db).
settings = get_settings()
engine = build_engine(settings)
async_session_maker = build_sessionmaker(engine)


async def ping_database(engine: AsyncEngine) -> None:
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
