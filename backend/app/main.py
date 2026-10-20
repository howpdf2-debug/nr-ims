from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api.health import router as health_router
from app.api.v1 import (
    actions, alarms, audit, auth, dashboard, devices, discovery, links, reports, stations, topology, users,
)
from app.cache import build_cache
from app.config import Settings, get_settings
from app.db.session import build_engine, build_sessionmaker
from app.logging_config import configure_logging

_V1 = (auth, devices, alarms, dashboard, actions, stations, links, topology, audit, discovery, users, reports)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        yield
        await app.state.cache.aclose()
        await app.state.engine.dispose()

    docs = settings.docs_enabled
    app = FastAPI(
        title="NR-IMS", lifespan=lifespan,
        docs_url="/docs" if docs else None, redoc_url=None, openapi_url="/openapi.json" if docs else None,
    )
    app.state.settings = settings
    app.state.engine = build_engine(settings)  # one engine per app (was: two)
    app.state.sessionmaker = build_sessionmaker(app.state.engine)
    app.state.cache = build_cache(settings)

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("Cache-Control", "no-store")
        return response

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
    )

    app.include_router(health_router)
    for module in _V1:
        app.include_router(module.router, prefix="/api/v1")
    return app
