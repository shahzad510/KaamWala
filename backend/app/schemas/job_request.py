"""
Job request Pydantic schemas.

``JobRequestCreate`` and ``JobRequestUpdate`` are the only entry points for
customer-supplied data.  System-managed fields (``job_status``,
``assigned_provider_id``, all counters) are deliberately absent to prevent
clients from manipulating platform state directly.

Budget cross-field validation (max >= min) is enforced at schema level via
``@model_validator`` so the service layer never receives an incoherent range.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.job_request import JobStatus, Urgency
from app.models.provider_listing import ServiceCategory


# ---------------------------------------------------------------------------
# Nested customer summary (embedded in job response)
# ---------------------------------------------------------------------------


class JobCustomerSummary(BaseModel):
    """
    Minimal customer info embedded in every job response.

    Phone is currently always returned.  When the contact-unlock system is
    implemented, visibility will be gated behind a provider payment/credit,
    and this class will need a conditional masking mechanism similar to
    ``ListingOwnerSummary``.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str | None
    phone: str | None


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class JobRequestCreate(BaseModel):
    """Fields a customer submits when posting a new job request."""

    title: str = Field(
        ...,
        min_length=5,
        max_length=150,
        examples=["Need electrician for wiring repair"],
    )
    description: str | None = Field(
        None,
        max_length=2000,
        examples=["Kitchen circuit breaker keeps tripping. Need urgent inspection."],
    )
    service_category: ServiceCategory = Field(
        ...,
        examples=[ServiceCategory.electrician],
    )
    city: str = Field(
        ...,
        min_length=2,
        max_length=100,
        examples=["Karachi"],
    )
    area: str | None = Field(
        None,
        max_length=150,
        examples=["DHA Phase 6"],
    )
    budget_min: int | None = Field(
        None,
        ge=0,
        examples=[500],
        description="Minimum acceptable budget in PKR",
    )
    budget_max: int | None = Field(
        None,
        ge=0,
        examples=[2000],
        description="Maximum acceptable budget in PKR",
    )
    urgency: Urgency = Field(
        ...,
        examples=[Urgency.high],
    )
    preferred_visit_date: datetime | None = Field(
        None,
        examples=["2026-06-05T10:00:00Z"],
    )

    @field_validator("title")
    @classmethod
    def strip_title(cls, v: str) -> str:
        return v.strip()

    @field_validator("city")
    @classmethod
    def strip_city(cls, v: str) -> str:
        return v.strip().title()

    @model_validator(mode="after")
    def validate_budget_range(self) -> "JobRequestCreate":
        if (
            self.budget_min is not None
            and self.budget_max is not None
            and self.budget_max < self.budget_min
        ):
            raise ValueError("budget_max must be greater than or equal to budget_min.")
        return self


class JobRequestUpdate(BaseModel):
    """All fields optional — only provided fields are written (PATCH semantics)."""

    title: str | None = Field(None, min_length=5, max_length=150)
    description: str | None = Field(None, max_length=2000)
    service_category: ServiceCategory | None = None
    city: str | None = Field(None, min_length=2, max_length=100)
    area: str | None = Field(None, max_length=150)
    budget_min: int | None = Field(None, ge=0)
    budget_max: int | None = Field(None, ge=0)
    urgency: Urgency | None = None
    preferred_visit_date: datetime | None = None

    @field_validator("title")
    @classmethod
    def strip_title(cls, v: str | None) -> str | None:
        return v.strip() if v else v

    @field_validator("city")
    @classmethod
    def strip_city(cls, v: str | None) -> str | None:
        return v.strip().title() if v else v

    @model_validator(mode="after")
    def validate_budget_range(self) -> "JobRequestUpdate":
        if (
            self.budget_min is not None
            and self.budget_max is not None
            and self.budget_max < self.budget_min
        ):
            raise ValueError("budget_max must be greater than or equal to budget_min.")
        return self


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class JobRequestResponse(BaseModel):
    """Full job request representation returned to API consumers."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    customer_id: uuid.UUID

    title: str
    description: str | None
    service_category: ServiceCategory
    city: str
    area: str | None
    budget_min: int | None
    budget_max: int | None
    urgency: Urgency
    job_status: JobStatus
    preferred_visit_date: datetime | None
    assigned_provider_id: uuid.UUID | None

    # System counters (read-only)
    contact_unlocked_count: int
    views_count: int
    referral_count: int
    trust_boost_score: int
    is_featured: bool

    created_at: datetime
    updated_at: datetime

    # Embedded customer info
    customer: JobCustomerSummary | None = None

    @classmethod
    def from_orm_with_customer(cls, job: object) -> "JobRequestResponse":
        """Build response and embed the customer summary."""
        from app.models.job_request import JobRequest

        job_obj: JobRequest = job  # type: ignore[assignment]
        obj = cls.model_validate(job_obj)

        if job_obj.customer is not None:
            obj.customer = JobCustomerSummary(
                id=job_obj.customer.id,
                name=job_obj.customer.name,
                phone=job_obj.customer.phone,
            )
        return obj


# ---------------------------------------------------------------------------
# Pagination wrapper
# ---------------------------------------------------------------------------


class PaginatedJobRequestResponse(BaseModel):
    """
    Paginated envelope for job browse/list responses.

    ``total`` reflects the full result count before pagination so clients
    can calculate page counts without issuing a separate count request.
    """

    total: int
    page: int
    page_size: int
    items: list[JobRequestResponse]
