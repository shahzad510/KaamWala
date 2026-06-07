"""
Job interest model.

A ``JobInterest`` represents a provider's expressed desire to work on a
specific open job.  It is the bridge between a ``JobRequest`` (demand) and
a ``ProviderListing`` (supply) before any formal assignment takes place.

Business invariants enforced by the service layer:
  - Only one interest record may exist per (job_id, provider_listing_id) pair
    — enforced by the database-level unique constraint and by the service.
  - Interest may only be expressed on ``open`` jobs.
  - The provider listing must belong to the authenticated caller.
  - Interest records are cascade-deleted when either the parent job or the
    parent listing is deleted (ON DELETE CASCADE on both FKs).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.job_request import JobRequest
    from app.models.provider_listing import ProviderListing


class JobInterest(Base):
    """
    A provider listing's expression of interest in an open job request.

    Relationships:
      - ``job``              — many-to-one back to ``JobRequest.interests``
      - ``provider_listing`` — many-to-one back to ``ProviderListing.interests``
        (loaded eagerly via selectin so the listing and its user are available
        in every response without an extra round-trip)
    """

    __tablename__ = "job_interests"

    __table_args__ = (
        # Database-level uniqueness guard — prevents duplicate rows even under
        # concurrent inserts that both pass the service-layer duplicate check.
        UniqueConstraint(
            "job_id",
            "provider_listing_id",
            name="uq_job_interests_job_listing",
        ),
        Index("ix_job_interests_job_id", "job_id"),
        Index("ix_job_interests_provider_listing_id", "provider_listing_id"),
        Index("ix_job_interests_created_at", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("job_requests.id", ondelete="CASCADE"),
        nullable=False,
    )

    provider_listing_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("provider_listings.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Optional pitch from the provider — visible only to the job's customer.
    message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Provider's indicative quote for this specific job (PKR).
    # Distinct from ProviderListing.starting_price, which is the general rate.
    quoted_price: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Provider's quoted price for this job in PKR",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
    )

    # -----------------------------------------------------------------------
    # Relationships
    # -----------------------------------------------------------------------

    # Many-to-one back to JobRequest.interests.
    # noload: the job is not needed when fetching interests — we already know
    # the job_id from the URL.  Load only when explicitly needed.
    job: Mapped[JobRequest] = relationship(
        "JobRequest",
        back_populates="interests",
        lazy="noload",
    )

    # Many-to-one back to ProviderListing.interests.
    # selectin: the listing (and, transitively, its user) must be embedded in
    # every interest response, so we load it eagerly alongside each interest.
    provider_listing: Mapped[ProviderListing] = relationship(
        "ProviderListing",
        back_populates="interests",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return (
            f"<JobInterest id={self.id} "
            f"job_id={self.job_id} "
            f"listing_id={self.provider_listing_id}>"
        )
