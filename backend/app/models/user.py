from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    Index,
    Integer,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.job_request import JobRequest
    from app.models.provider_listing import ProviderListing


class UserType(str, enum.Enum):
    customer = "customer"
    provider = "provider"
    both = "both"


class User(Base):
    __tablename__ = "users"

    __table_args__ = (
        # Named unique index — easier to reference in Alembic migrations.
        # Column-level unique=True is intentionally omitted to avoid a duplicate index.
        Index("ix_users_phone", "phone", unique=True),
        Index("ix_users_created_at", "created_at"),
    )

    # PK index is created automatically by PostgreSQL; index=True would duplicate it.
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # unique=True omitted — the named index in __table_args__ covers this.
    phone: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    user_type: Mapped[UserType] = mapped_column(
        Enum(UserType, name="usertype"),
        nullable=False,
        default=UserType.customer,
        server_default=UserType.customer.value,
    )

    is_phone_verified: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )

    free_contacts_remaining: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=3,
        server_default="3",
    )

    has_used_pay_later: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )

    outstanding_debt: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=0,
        server_default="0",
        comment="Outstanding debt in PKR paisa (smallest unit)",
    )

    debt_incurred_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # -----------------------------------------------------------------------
    # Relationships
    # -----------------------------------------------------------------------

    # One-to-many: a user may own multiple provider listings.
    # noload: never auto-fetch listings when a User is loaded.
    # Auth middleware fetches User on every request; pulling listings there
    # would be wasteful. Load explicitly only in listing-specific endpoints.
    provider_listings: Mapped[list[ProviderListing]] = relationship(
        "ProviderListing",
        back_populates="user",
        lazy="noload",
    )

    # One-to-many: a user (as customer) may post multiple job requests.
    # noload: same rationale as provider_listings — never load on auth paths.
    job_requests: Mapped[list[JobRequest]] = relationship(
        "JobRequest",
        foreign_keys="JobRequest.customer_id",
        back_populates="customer",
        lazy="noload",
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} phone={self.phone} type={self.user_type}>"
