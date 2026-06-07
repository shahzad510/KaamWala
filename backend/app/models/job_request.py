"""
Job request model.

A ``JobRequest`` represents a customer's demand for a service.  It is the
counterpart to ``ProviderListing`` on the supply side.  Providers browse
open jobs and decide whether to respond; the contact-unlock system (future
phase) gates access to the customer's phone number behind a payment.

``JobStatus`` drives the lifecycle: open → assigned → completed.
Cancellation is a terminal state that can be reached from any non-terminal
status by the customer.
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

# ServiceCategory is shared vocabulary — import rather than redefine.
from app.models.provider_listing import ServiceCategory  # noqa: E402

if TYPE_CHECKING:
    from app.models.job_interest import JobInterest
    from app.models.user import User


class Urgency(str, enum.Enum):
    """
    Customer's self-reported urgency for the job.

    Used for browse filtering and, in future phases, for surfacing
    high-urgency jobs more prominently to nearby providers.
    """

    low = "low"
    medium = "medium"
    high = "high"
    emergency = "emergency"


class JobStatus(str, enum.Enum):
    """
    Lifecycle state machine for a job request.

    Allowed transitions:
      open → assigned  (when a provider is linked, future phase)
      open / assigned → cancelled  (customer closes the job)
      assigned → completed  (provider confirms, future phase)

    ``cancelled`` and ``completed`` are terminal — no further transitions
    are permitted.  The service layer enforces this via ``_TERMINAL_STATUSES``.
    """

    open = "open"
    assigned = "assigned"
    completed = "completed"
    cancelled = "cancelled"


class JobRequest(Base):
    """
    A customer's request for a skilled-trade service.

    Lifecycle and ownership rules enforced by the service layer:
      - Only the posting customer may update or close a job.
      - Updates are rejected once the job reaches a terminal status.
      - ``contact_unlocked_count`` is incremented by the unlock flow, not
        by direct API writes.
      - ``assigned_provider_id`` is populated by the assignment flow
        (future phase); its FK uses SET NULL so provider deletion does
        not cascade-delete the job record.
    """

    __tablename__ = "job_requests"

    __table_args__ = (
        # Named indexes for all common filter / sort columns.
        Index("ix_job_requests_customer_id", "customer_id"),
        Index("ix_job_requests_service_category", "service_category"),
        Index("ix_job_requests_city", "city"),
        Index("ix_job_requests_job_status", "job_status"),
        Index("ix_job_requests_urgency", "urgency"),
        Index("ix_job_requests_created_at", "created_at"),
        Index("ix_job_requests_assigned_provider_id", "assigned_provider_id"),
    )

    # PK — PostgreSQL creates the primary-key index automatically.
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # FK to the customer who created this job.
    # index=True omitted — covered by ix_job_requests_customer_id above.
    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    title: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # index omitted — covered by ix_job_requests_service_category.
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

    budget_min: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Minimum acceptable budget in PKR",
    )

    budget_max: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Maximum acceptable budget in PKR",
    )

    # index omitted — covered by ix_job_requests_urgency.
    urgency: Mapped[Urgency] = mapped_column(
        Enum(Urgency, name="urgency"),
        nullable=False,
        default=Urgency.medium,
        server_default=Urgency.medium.value,
    )

    # index omitted — covered by ix_job_requests_job_status.
    job_status: Mapped[JobStatus] = mapped_column(
        Enum(JobStatus, name="jobstatus"),
        nullable=False,
        default=JobStatus.open,
        server_default=JobStatus.open.value,
    )

    preferred_visit_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Populated when a provider is assigned (future phase).
    # index omitted — covered by ix_job_requests_assigned_provider_id.
    # SET NULL so that deleting a provider user does not cascade-delete jobs.
    assigned_provider_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # -----------------------------------------------------------------------
    # System-managed counters — never written directly by API clients
    # -----------------------------------------------------------------------

    contact_unlocked_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
        comment="Number of providers who have unlocked this job's contact",
    )

    views_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    # -----------------------------------------------------------------------
    # Future-scaling fields — columns only, no business logic yet
    # -----------------------------------------------------------------------

    referral_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
        comment="Number of referrals this job has received (future phase)",
    )

    trust_boost_score: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
        comment="Trust boost applied to job visibility (future phase)",
    )

    is_featured: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
        comment="Featured jobs surface at the top of browse results (future phase)",
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

    # Many-to-one back to User.job_requests.
    # selectin: load the customer alongside the job — needed in every response.
    customer: Mapped[User] = relationship(
        "User",
        foreign_keys=[customer_id],
        back_populates="job_requests",
        lazy="selectin",
    )

    # One-to-many: a job can have many interested provider listings.
    # noload: interests are only needed on the dedicated interest endpoints,
    # not on every job fetch.  Load explicitly there.
    interests: Mapped[list[JobInterest]] = relationship(
        "JobInterest",
        back_populates="job",
        lazy="noload",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return (
            f"<JobRequest id={self.id} "
            f"customer_id={self.customer_id} "
            f"status={self.job_status}>"
        )
