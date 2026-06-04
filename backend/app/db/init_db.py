"""
Database initialisation helpers.

Provides ``create_tables()``, a convenience function for local development
that creates all tables from the SQLAlchemy metadata.  This must NOT be
used in production — run Alembic migrations there instead so that schema
changes are tracked, reversible, and safe to apply on a live database.
"""

import logging

from sqlalchemy.ext.asyncio import AsyncEngine

# Base is imported so its metadata object is reachable here.
# By the time create_tables() is called from main.py's startup hook,
# all model modules have already been imported transitively via the
# API → service → model import chain, so Base.metadata is fully populated.
from app.db.base import Base  # noqa: F401

logger = logging.getLogger(__name__)


async def create_tables(engine: AsyncEngine) -> None:
    """
    Create all database tables derived from the declarative Base.

    NOTE: In production use Alembic migrations instead of calling this directly.
    This function is provided for local development convenience only.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables created (or already exist)")
