"""
Job interest Pydantic schemas.

``JobInterestCreate`` is the only entry point for provider-supplied data.
The response schemas embed a safe provider summary that deliberately omits
the provider's phone number — phone visibility is gated behind the
contact-unlock flow (Phase 4) and must not be exposed here.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.provider_listing import ServiceCategory


# ---------------------------------------------------------------------------
# Nested provider summary (embedded in interest response)
# ---------------------------------------------------------------------------


class InterestedProviderSummary(BaseModel):
    """
    Safe provider profile embedded in every interest response.

    Fields are limited to publicly visible listing data.  The provider's
    phone number is intentionally absent — it remains gated behind the
    contact-unlock system (Phase 4).
    """

    model_config = ConfigDict(from_attributes=True)

    listing_id: uuid.UUID
    user_id: uuid.UUID
    name: str | None           # From User.name; may be None if not set
    title: str
    city: str
    service_category: ServiceCategory
    experience_years: int | None
    profile_completion_percentage: int


# ---------------------------------------------------------------------------
# Request schema
# ---------------------------------------------------------------------------


class JobInterestCreate(BaseModel):
    """
    Fields a provider submits when expressing interest in a job.

    ``provider_listing_id`` identifies which of the caller's listings is
    being put forward.  A single user may own multiple listings (e.g. an
    electrician and an AC technician profile); they choose which profile
    to present for each job.
    """

    provider_listing_id: uuid.UUID = Field(
        ...,
        description="ID of the caller's listing to associate with this interest",
    )
    message: str | None = Field(
        None,
        max_length=1000,
        examples=["I have 8 years of experience with this type of wiring. Available tomorrow."],
        description="Optional pitch or introduction from the provider",
    )
    quoted_price: int | None = Field(
        None,
        ge=0,
        examples=[1800],
        description="Provider's indicative price for this specific job in PKR",
    )


# ---------------------------------------------------------------------------
# Response schema
# ---------------------------------------------------------------------------


class JobInterestResponse(BaseModel):
    """Full interest record returned to the job's customer."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    job_id: uuid.UUID
    provider_listing_id: uuid.UUID
    message: str | None
    quoted_price: int | None
    created_at: datetime

    # Embedded provider listing summary — populated by from_orm_with_provider.
    provider: InterestedProviderSummary | None = None

    @classmethod
    def from_orm_with_provider(cls, interest: object) -> "JobInterestResponse":
        """Build response and embed the provider listing summary."""
        from app.models.job_interest import JobInterest

        interest_obj: JobInterest = interest  # type: ignore[assignment]
        obj = cls.model_validate(interest_obj)

        listing = interest_obj.provider_listing
        if listing is not None:
            obj.provider = InterestedProviderSummary(
                listing_id=listing.id,
                user_id=listing.user_id,
                name=listing.user.name if listing.user is not None else None,
                title=listing.title,
                city=listing.city,
                service_category=listing.service_category,
                experience_years=listing.experience_years,
                profile_completion_percentage=listing.profile_completion_percentage,
            )
        return obj
