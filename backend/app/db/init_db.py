import logging

from sqlalchemy.ext.asyncio import AsyncEngine

from app.db.base import Base  # noqa: F401 – ensures all models are imported

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
