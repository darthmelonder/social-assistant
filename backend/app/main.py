from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings


@asynccontextmanager
async def _lifespan(app: FastAPI):
    from arq import create_pool
    from app.workers.arq_settings import _redis_from_env

    app.state.redis = await create_pool(_redis_from_env())
    yield
    await app.state.redis.aclose()


def create_app() -> FastAPI:
    settings = get_settings()

    _app = FastAPI(
        title="Social Assistant API",
        version="0.1.0",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        lifespan=_lifespan,
    )

    _app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    from app.connectors import setup_connectors
    setup_connectors()

    from app.api.routes.auth import router as auth_router
    from app.api.routes.connections import router as connections_router
    from app.api.routes.drafts import router as drafts_router
    from app.api.routes.events import router as events_router
    from app.api.routes.profile import router as profile_router
    from app.api.routes.threads import router as threads_router
    _app.include_router(auth_router)
    _app.include_router(connections_router)
    _app.include_router(threads_router)
    _app.include_router(drafts_router)
    _app.include_router(profile_router)
    _app.include_router(events_router)

    @_app.get("/health", tags=["meta"])
    async def health_check() -> dict:
        return {"status": "ok", "version": "0.1.0"}

    return _app


app = create_app()
