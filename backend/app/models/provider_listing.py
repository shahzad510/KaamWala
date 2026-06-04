"""
Provider listing model.

A ``ProviderListing`` is a public-facing profile card that a provider
publishes to advertise their services.  One user may own many listings
(e.g. an electrician who also offers AC repair under a separate listing).

``ServiceCategory`` is defined here and intentionally reused by
``job_request.py`` to keep the category vocabulary consistent across
the supply and demand sides without duplication.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.user import User


class ServiceCategory(str, enum.Enum):
    """
    Canonical list of service trades supported on the platform.

    Used by both provider listings (supply) and job requests (demand) so
    that the two sides can be matched by category.  Add new values here
    and run a migration to extend the PostgreSQL enum type.
    """

    electrician = "electrician"
    plumber = "plumber"
    carpenter = "carpenter"
    painter = "painter"
    cleaner = "cleaner"
    ac_technician = "ac_technician"
    welder = "welder"
    mason = "mason"
    driver = "driver"
    guard = "guard"
    gardener = "gardener"
    cook = "cook"
    tailor = "tailor"
    mechanic = "mechanic"
    other = "other"


class ProviderListing(Base):
    """
    A provider's public service advertisement.

    System-managed counters (``completed_jobs_count``, ``referral_count``,
    ``trust_score``, ``views_count``) are incremented by platform events and
    must never be accepted from API client input.

    ``profile_completion_percentage`` is recomputed on every create/update
    by the service layer, not by the client.
    """

    __tablename__ = "provider_listings"

    __table_args__ = (
        # One user may own many listings — no uniqueness constraint on user_id.
        # A plain btree index is added instead (via index=True on the column)
        # to keep FK-join and per-user queries fast.
        Index("ix_provider_listings_service_category", "service_category"),
        Index("ix_provider_listings_city", "city"),
        Index("ix_provider_listings_is_active", "is_active"),
        Index("ix_provider_listings_created_at", "created_at"),
    )

    # PK index is implicit in PostgreSQL; index=True would create a duplicate.
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # UniqueConstraint removed — multiple listings per user are now allowed.
    # index=True reinstated so FK joins and per-user queries remain O(log n).
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    title: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # index=True omitted — covered by the named Index in __table_args__.
    service_category: Mapped[ServiceCategory] = mapped_column(
        Enum(ServiceCategory, name="servicecategory"),
        nullable=False,
    )

    city: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    area: Mapped[str | None] = mapped_column(
        String(150),
        nullable=True,
    )

    # Replaces the old PriceRange enum. Free-form indicative price in PKR.
    starting_price: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Indicative starting price in PKR",
    )

    pricing_notes: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment='e.g. "Negotiable", "Per visit charges", "Inspection charges separate"',
    )

    experience_years: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    phone_visible: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )

    # -----------------------------------------------------------------------
    # System-managed counters — never written directly by API clients
    # -----------------------------------------------------------------------

    completed_jobs_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    referral_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    trust_score: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
        comment="Computed trust score (0–100)",
    )

    profile_completion_percentage: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
        comment="Auto-computed on writes (0–100)",
    )

    # Credits awarded to this provider through referrals or promotions.
    # Consumed by the contact-unlock feature in a future phase.
    free_unlock_credits: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    # Providers can opt out of the referral network; setting this False
    # hides the listing from referral-driven discovery surfaces.
    can_receive_referrals: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )

    # Set to True by admins after manual verification (ID, trade certificate,
    # etc.).  Verified listings receive a badge and ranking boost.
    is_verified: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )

    views_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
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

    # Many-to-one back to User.provider_listings.
    # selectin: load the owner alongside the listing — needed in every response.
    user: Mapped[User] = relationship(
        "User",
        back_populates="provider_listings",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return (
            f"<ProviderListing id={self.id} "
            f"user_id={self.user_id} "
            f"category={self.service_category}>"
        )
