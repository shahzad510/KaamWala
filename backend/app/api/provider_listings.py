from typing import Annotated

from fastapi import APIRouter, Query, status

from app.core.dependencies import CurrentUser, DBSession
from app.models.provider_listing import ServiceCategory
from app.schemas.provider_listing import (
    PaginatedListingResponse,
    ProviderListingCreate,
    ProviderListingResponse,
    ProviderListingUpdate,
)
from app.services import provider_listing_service
from uuid import UUID

router = APIRouter(prefix="/provider-listings", tags=["Provider Listings"])


@router.post(
    "",
    response_model=ProviderListingResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a provider listing",
)
async def create_listing(
    payload: ProviderListingCreate,
    db: DBSession,
    current_user: CurrentUser,
) -> ProviderListingResponse:
    """
    Create a new provider listing for the authenticated user.
    A user may own multiple listings. Phone must be verified first.
    """
    return await provider_listing_service.create_listing(db, payload, current_user)


@router.get(
    "/me",
    response_model=list[ProviderListingResponse],
    status_code=status.HTTP_200_OK,
    summary="Get all provider listings owned by the current user",
)
async def get_my_listings(
    db: DBSession,
    current_user: CurrentUser,
) -> list[ProviderListingResponse]:
    """Return all listings owned by the authenticated user, newest first. Empty list if none."""
    return await provider_listing_service.get_my_listings(db, current_user)


@router.get(
    "",
    response_model=PaginatedListingResponse,
    status_code=status.HTTP_200_OK,
    summary="List all active provider listings",
)
async def list_listings(
    db: DBSession,
    page: Annotated[int, Query(ge=1, description="Page number (1-indexed)")] = 1,
    page_size: Annotated[
        int, Query(ge=1, le=100, description="Results per page (max 100)")
    ] = 20,
    service_category: Annotated[
        ServiceCategory | None, Query(description="Filter by service category")
    ] = None,
    city: Annotated[
        str | None, Query(max_length=100, description="Filter by city (case-insensitive)")
    ] = None,
) -> PaginatedListingResponse:
    """Paginated public listing of all active providers with optional filters."""
    return await provider_listing_service.list_listings(
        db,
        page=page,
        page_size=page_size,
        service_category=service_category,
        city=city,
        is_active=True,
    )


@router.get(
    "/{listing_id}",
    response_model=ProviderListingResponse,
    status_code=status.HTTP_200_OK,
    summary="Get a single provider listing by ID",
)
async def get_listing(
    listing_id: UUID,
    db: DBSession,
) -> ProviderListingResponse:
    """
    Fetch a single active provider listing by its UUID.
    View counter is incremented on every call.
    """
    return await provider_listing_service.get_listing_detail(db, listing_id)


@router.put(
    "/{listing_id}",
    response_model=ProviderListingResponse,
    status_code=status.HTTP_200_OK,
    summary="Update a provider listing (owner only)",
)
async def update_listing(
    listing_id: UUID,
    payload: ProviderListingUpdate,
    db: DBSession,
    current_user: CurrentUser,
) -> ProviderListingResponse:
    """
    Update any subset of listing fields.
    Only the owner may modify their listing. Returns 403 for other users.
    """
    return await provider_listing_service.update_listing(
        db, listing_id, payload, current_user
    )
