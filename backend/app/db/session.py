"""
Database engine and session factory.

The async engine and session maker are module-level singletons — they are
created once at import time and reused for the lifetime of the process.
``get_db`` is the FastAPI dependency that hands a fresh session to each request.
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings

# pool_pre_ping=True issues a lightweight "SELECT 1" before handing a
# connection to a request, recovering from connections that went stale
# while sitting idle in the pool (common after database restarts).
# pool_size + max_overflow cap total concurrent DB connections at 30,
# which is appropriate for a single-instance deployment.
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

# expire_on_commit=False keeps ORM objects usable after a commit without
# triggering an extra SELECT to refresh them.  This matters for async code
# where lazy loading would raise an error outside an active session context.
# autoflush=False prevents SQLAlchemy from flushing pending changes before
# every query, giving service-layer code explicit control over flush timing.
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that provides a single async session per HTTP request.

    Commits on clean exit, rolls back on any exception, and always closes
    the session in the finally block to return the connection to the pool.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
