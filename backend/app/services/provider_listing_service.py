"""
Provider Listing service — all business logic for listing CRUD.
Routes stay thin; this layer owns domain rules and DB access.
"""

import logging
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.provider_listing import ProviderListing
from app.models.user import User
from app.schemas.provider_listing import (
    PaginatedListingResponse,
    ProviderListingCreate,
    ProviderListingResponse,
    ProviderListingUpdate,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _compute_profile_completion(listing: ProviderListing) -> int:
    """
    Return a 0–100 integer representing how complete a listing is.

    Each of the 8 scored fields contributes an equal 12.5 points.
    The result is rounded to the nearest integer.  This function is
    called after every create and update so the stored value stays current.
    Adding or removing scored fields here automatically affects the
    percentage displayed to providers.
    """
    scored_fields = [
        bool(listing.title),
        bool(listing.description),
        bool(listing.service_category),
        bool(listing.city),
        bool(listing.area),
        listing.starting_price is not None,
        listing.pricing_notes is not None,
        listing.experience_years is not None,
    ]
    filled = sum(scored_fields)
    return round(filled / len(scored_fields) * 100)


# ---------------------------------------------------------------------------
# CRUD operations
# ---------------------------------------------------------------------------


async def get_listing_by_id(
    db: AsyncSession, listing_id: uuid.UUID
) -> ProviderListing | None:
    """Return a single ProviderListing by PK, or None if not found."""
    result = await db.execute(
        select(ProviderListing).where(ProviderListing.id == listing_id)
    )
    return result.scalar_one_or_none()


async def get_listings_by_user_id(
    db: AsyncSession, user_id: uuid.UUID
) -> list[ProviderListing]:
    """Return all listings owned by a user, ordered newest first."""
    result = await db.execute(
        select(ProviderListing)
        .where(ProviderListing.user_id == user_id)
        .order_by(ProviderListing.created_at.desc())
    )
    return list(result.scalars().all())


async def create_listing(
    db: AsyncSession,
    payload: ProviderListingCreate,
    current_user: User,
) -> ProviderListingResponse:
    """Create a new provider listing for the authenticated user."""
    if not current_user.is_phone_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Phone number must be verified before creating a listing.",
        )

    listing = ProviderListing(
        user_id=current_user.id,
        **payload.model_dump(),
    )
    listing.profile_completion_percentage = _compute_profile_completion(listing)

    db.add(listing)
    await db.flush()
    await db.refresh(listing)

    logger.info("Provider listing created: %s by user %s", listing.id, current_user.id)
    return ProviderListingResponse.from_orm_with_owner(listing)


async def list_listings(
    db: AsyncSession,
    page: int,
    page_size: int,
    service_category: str | None,
    city: str | None,
    is_active: bool,
) -> PaginatedListingResponse:
    """
    Return a paginated, optionally filtered list of provider listings.

    Filters are additive (AND logic).  City comparison is case-insensitive
    via func.lower so "karachi" and "Karachi" return the same results.
    A separate COUNT query is issued first so the total can be returned
    alongside the page data without a second round-trip to the client.
    """
    base_query = select(ProviderListing).where(ProviderListing.is_active == is_active)

    if service_category:
        base_query = base_query.where(
            ProviderListing.service_category == service_category
        )
    if city:
        # Case-insensitive match; city is stored with .title() capitalisation
        # but defensive lowercasing here avoids mismatches from older data.
        base_query = base_query.where(
            func.lower(ProviderListing.city) == city.lower()
        )

    count_result = await db.execute(
        select(func.count()).select_from(base_query.subquery())
    )
    total = count_result.scalar_one()

    offset = (page - 1) * page_size
    paginated_query = (
        base_query
        .order_by(ProviderListing.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    result = await db.execute(paginated_query)
    listings = result.scalars().all()

    return PaginatedListingResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=[ProviderListingResponse.from_orm_with_owner(l) for l in listings],
    )


async def get_listing_detail(
    db: AsyncSession, listing_id: uuid.UUID
) -> ProviderListingResponse:
    """Fetch a single listing by ID and increment its view counter."""
    listing = await get_listing_by_id(db, listing_id)
    if listing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Provider listing not found.",
        )

    listing.views_count += 1
    await db.flush()

    return ProviderListingResponse.from_orm_with_owner(listing)


async def get_my_listings(
    db: AsyncSession, current_user: User
) -> list[ProviderListingResponse]:
    """Return all listings owned by the authenticated user, newest first."""
    listings = await get_listings_by_user_id(db, current_user.id)
    return [ProviderListingResponse.from_orm_with_owner(l) for l in listings]


async def update_listing(
    db: AsyncSession,
    listing_id: uuid.UUID,
    payload: ProviderListingUpdate,
    current_user: User,
) -> ProviderListingResponse:
    """Update a listing. Only the owner may do this."""
    listing = await get_listing_by_id(db, listing_id)
    if listing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Provider listing not found.",
        )

    # Ownership check: compare UUIDs, not ORM objects, to avoid accidental
    # identity comparisons that could pass even for different users.
    if listing.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to update this listing.",
        )

    # exclude_unset=True applies PATCH semantics: only fields the caller
    # explicitly included in the payload are written to the model.
    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(listing, field, value)

    listing.profile_completion_percentage = _compute_profile_completion(listing)
    listing.updated_at = datetime.now(timezone.utc)

    await db.flush()
    await db.refresh(listing)

    logger.info("Provider listing updated: %s by user %s", listing.id, current_user.id)
    return ProviderListingResponse.from_orm_with_owner(listing)
