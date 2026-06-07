"""
FastAPI application factory.

``create_app()`` assembles the application: middleware, routers, and
startup/shutdown lifecycle hooks.  The module-level ``app`` instance is
what ASGI servers (uvicorn, gunicorn+uvicorn) target via ``app.main:app``.

Startup hook calls ``create_tables()`` for convenience in local development.
In production this should be a no-op because Alembic migrations handle
schema changes before the process starts.
"""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import auth, health, job_requests, provider_listings
from app.core.config import settings
from app.db.init_db import create_tables
from app.db.session import engine

logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)
logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    """
    Build and configure the FastAPI application instance.

    Using a factory function (rather than a bare module-level ``app``) makes
    the app testable: test suites can call ``create_app()`` with a different
    settings override without polluting the module-level state.
    """
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description="KaamWala AI — backend API (Phase 2B: Auth + Provider Listings + Job Requests + Provider Interest System)",
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
    app.include_router(provider_listings.router, prefix="/api/v1")
    app.include_router(job_requests.router, prefix="/api/v1")

    # ---------------------------------------------------------------------------
    # Startup / shutdown lifecycle
    # ---------------------------------------------------------------------------
    @app.on_event("startup")
    async def on_startup() -> None:
        logger.info("Starting up %s v%s ...", settings.APP_NAME, settings.APP_VERSION)
        # create_tables is a dev convenience — in production Alembic has
        # already applied migrations before this hook runs, so this is a no-op.
        await create_tables(engine)
        logger.info("Startup complete.")

    @app.on_event("shutdown")
    async def on_shutdown() -> None:
        # Gracefully close all pooled connections before the process exits.
        logger.info("Shutting down — disposing database engine.")
        await engine.dispose()

    return app


app = create_app()
