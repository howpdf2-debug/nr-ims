from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.health import router as health_router
from app.api.v1.auth import router as auth_router
from app.api.v1.devices import router as devices_router
from app.api.v1.alarms import router as alarms_router
from app.api.v1.dashboard import router as dashboard_router
from app.api.v1.actions import router as actions_router
from app.api.v1.stations import router as stations_router
from app.api.v1.links import router as links_router
from app.api.v1.topology import router as topology_router
from app.api.v1.audit import router as audit_router
from app.api.v1.discovery import router as discovery_router
from app.api.v1.users import router as users_router

from app.config import get_settings
from app.db.session import build_engine
from app.cache import build_cache


def create_app() -> FastAPI:
    settings = get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        yield
        await app.state.cache.aclose()
        await app.state.engine.dispose()

    app = FastAPI(title="NR-IMS", lifespan=lifespan)
    app.state.engine = build_engine(settings)
    app.state.cache = build_cache(settings)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health_router)
    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(devices_router, prefix="/api/v1")
    app.include_router(alarms_router, prefix="/api/v1")
    app.include_router(dashboard_router, prefix="/api/v1")
    app.include_router(actions_router, prefix="/api/v1")
    app.include_router(stations_router, prefix="/api/v1")
    app.include_router(links_router, prefix="/api/v1")
    app.include_router(topology_router, prefix="/api/v1")
    app.include_router(audit_router, prefix="/api/v1")
    app.include_router(discovery_router, prefix="/api/v1")
    app.include_router(users_router, prefix="/api/v1")

    return app


# ── Module-level app instance for uvicorn ────────────────────
# Enables: uvicorn app.main:app (no --factory flag needed)
# Also used by tests via: from app.main import app
app = create_app()