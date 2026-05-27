from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Shared declarative base for all SQLAlchemy models."""
    pass


# Import all models here so Alembic autogenerate can discover them.
# Add new models to this import when created.

