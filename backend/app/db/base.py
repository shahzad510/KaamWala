from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Shared declarative base for all SQLAlchemy models."""
    pass


# Keep all model imports here in alphabetical order.
# This file is the single source of truth for Alembic autogenerate discovery.
# Add every new model to this list when created.

