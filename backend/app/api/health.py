"""
Health check routes.

Two endpoints are provided for different monitoring layers:
  GET /health     — simple liveness probe (no DB dependency).
  GET /health/db  — deep ping that includes a DB connectivity check.

Load balancers and container orchestrators can use ``/health`` for fast
liveness checks.  Use ``/health/db`` for readiness checks that require
the database to be reachable before traffic is routed to the instance.
"""

from datetime import datetime, timezone

from fastapi import APIRouter
from sqlalchemy import text

from app.core.config import settings
from app.core.dependencies import DBSession

router = APIRouter(tags=["Health"])


@router.get("/health", summary="Basic liveness check")
async def health() -> dict:
    """Return application name, version, and current UTC timestamp."""
    return {
        "status": "ok",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/health/db", summary="Database connectivity check")
async def health_db(db: DBSession) -> dict:
    """Ping the database and report connectivity status."""
    try:
        await db.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception as exc:
        db_status = f"error: {exc}"

    return {
        "status": "ok" if db_status == "ok" else "degraded",
        "database": db_status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
