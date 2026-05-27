import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import auth, health
from app.core.config import settings
from app.db.init_db import create_tables
from app.db.session import engine

logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)
logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description="KaamWala AI — backend API (Week 1-2 MVP: Core Auth & Contact Flow)",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    # ---------------------------------------------------------------------------
    # Middleware
    # ---------------------------------------------------------------------------
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Restrict to specific origins in production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ---------------------------------------------------------------------------
    # Routers
    # ---------------------------------------------------------------------------
    app.include_router(health.router)
    app.include_router(auth.router, prefix="/api/v1")

    # ---------------------------------------------------------------------------
    # Startup / shutdown lifecycle
    # ---------------------------------------------------------------------------
    @app.on_event("startup")
    async def on_startup() -> None:
        logger.info("Starting up %s v%s ...", settings.APP_NAME, settings.APP_VERSION)
        await create_tables(engine)
        logger.info("Startup complete.")

    @app.on_event("shutdown")
    async def on_shutdown() -> None:
        logger.info("Shutting down — disposing database engine.")
        await engine.dispose()

    return app


app = create_app()
