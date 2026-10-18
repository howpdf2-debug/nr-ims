from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# --- सभी राउटर्स के इम्पोर्ट्स ---
from app.api.health import router as health_router
from app.api.v1.auth import router as auth_router
from app.api.v1.devices import router as devices_router
from app.api.v1.alarms import router as alarms_router
from app.api.v1.dashboard import router as dashboard_router
from app.api.v1.actions import router as actions_router  # <-- नया
from app.api.v1.stations import router as stations_router
from app.api.v1.links import router as links_router
from app.api.v1.topology import router as topology_router

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
        allow_headers=["*"]
    )
    
    # --- राउटर्स को ऐप में जोड़ना ---
    app.include_router(health_router)
    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(devices_router, prefix="/api/v1")
    app.include_router(alarms_router, prefix="/api/v1")
    app.include_router(dashboard_router, prefix="/api/v1")
    app.include_router(actions_router, prefix="/api/v1")  # <-- रजिस्टर हो गया
    app.include_router(stations_router, prefix="/api/v1")
    app.include_router(links_router, prefix="/api/v1")
    app.include_router(topology_router, prefix="/api/v1")
    
    return app