"""
SQLAlchemy declarative base.

All ORM models must inherit from ``Base`` (imported from this module).
``Base`` alone does not import any model files — doing so would create
circular imports because every model file imports ``Base`` from here.

Model discovery (populating ``Base.metadata``) happens through two separate
mechanisms, depending on the context:

  Runtime (application startup)
  ─────────────────────────────
  ``main.py`` imports all API routers, which transitively import service
  modules, which import model modules.  By the time the startup hook calls
  ``create_tables()``, every model has already been registered with
  ``Base.metadata`` as a side-effect of those imports.

  Alembic (schema migrations)
  ───────────────────────────
  Alembic's ``env.py`` must explicitly import each model module (or a
  dedicated ``app/models/__init__.py`` that re-exports them all) before
  calling ``run_migrations_online/offline()``.  Without those imports,
  ``autogenerate`` will not detect any tables.
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Shared declarative base for all SQLAlchemy models."""
    pass
