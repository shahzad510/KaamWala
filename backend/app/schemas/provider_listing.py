import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.provider_listing import ServiceCategory


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class ProviderListingCreate(BaseModel):
    title: str = Field(
        ...,
        min_length=5,
        max_length=120,
        examples=["Expert Electrician — Karachi"],
    )
    description: str | None = Field(
        None,
        max_length=2000,
        examples=["10 years of residential and commercial wiring experience."],
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
        examples=["Gulshan-e-Iqbal"],
    )
    starting_price: int | None = Field(
        None,
        ge=0,
        examples=[500],
        description="Indicative starting price in PKR",
    )
    pricing_notes: str | None = Field(
        None,
        max_length=255,
        examples=["Negotiable", "Per visit charges", "Inspection charges separate"],
    )
    experience_years: int | None = Field(
        None,
        ge=0,
        le=60,
        examples=[5],
    )
    phone_visible: bool = Field(True)
    can_receive_referrals: bool = Field(True)

    @field_validator("title")
    @classmethod
    def strip_title(cls, v: str) -> str:
        return v.strip()

    @field_validator("city")
    @classmethod
    def strip_city(cls, v: str) -> str:
        return v.strip().title()


class ProviderListingUpdate(BaseModel):
    """All fields optional — only provided fields are updated (PATCH semantics)."""

    title: str | None = Field(None, min_length=5, max_length=120)
    description: str | None = Field(None, max_length=2000)
    service_category: ServiceCategory | None = None
    city: str | None = Field(None, min_length=2, max_length=100)
    area: str | None = Field(None, max_length=150)
    starting_price: int | None = Field(None, ge=0)
    pricing_notes: str | None = Field(None, max_length=255)
    experience_years: int | None = Field(None, ge=0, le=60)
    phone_visible: bool | None = None
    can_receive_referrals: bool | None = None
    is_active: bool | None = None

    @field_validator("title")
    @classmethod
    def strip_title(cls, v: str | None) -> str | None:
        return v.strip() if v else v

    @field_validator("city")
    @classmethod
    def strip_city(cls, v: str | None) -> str | None:
        return v.strip().title() if v else v


# ---------------------------------------------------------------------------
# Nested owner summary (embedded in listing response)
# ---------------------------------------------------------------------------


class ListingOwnerSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str | None
    phone: str | None  # conditionally exposed based on phone_visible


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class ProviderListingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID

    title: str
    description: str | None
    service_category: ServiceCategory
    city: str
    area: str | None
    starting_price: int | None
    pricing_notes: str | None
    experience_years: int | None

    phone_visible: bool
    can_receive_referrals: bool

    # System counters (read-only)
    completed_jobs_count: int
    referral_count: int
    trust_score: int
    profile_completion_percentage: int
    free_unlock_credits: int
    views_count: int

    is_verified: bool
    is_active: bool

    created_at: datetime
    updated_at: datetime

    # Embedded owner info
    owner: ListingOwnerSummary | None = None

    @classmethod
    def from_orm_with_owner(
        cls, listing: object
    ) -> "ProviderListingResponse":
        """Build response, conditionally masking owner phone per phone_visible flag."""
        from app.models.provider_listing import ProviderListing

        listing_obj: ProviderListing = listing  # type: ignore[assignment]
        obj = cls.model_validate(listing_obj)

        if listing_obj.user is not None:
            phone = (
                listing_obj.user.phone if listing_obj.phone_visible else None
            )
            obj.owner = ListingOwnerSummary(
                id=listing_obj.user.id,
                name=listing_obj.user.name,
                phone=phone,
            )
        return obj


# ---------------------------------------------------------------------------
# Pagination wrapper
# ---------------------------------------------------------------------------


class PaginatedListingResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[ProviderListingResponse]
