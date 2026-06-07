"""
Job request routes.

CRUD and lifecycle endpoints for JobRequest resources:
  POST   /job-requests                       — post a new job (auth required)
  GET    /job-requests/me                    — list caller's own jobs (auth)
  GET    /job-requests                       — public paginated browse (open jobs only)
  GET    /job-requests/{job_id}              — public single job detail
  PUT    /job-requests/{job_id}              — update own job (owner only)
  POST   /job-requests/{job_id}/close        — cancel a job (owner only)
  POST   /job-requests/{job_id}/interest     — provider expresses interest (auth)
  GET    /job-requests/{job_id}/interests    — customer views interested providers (auth, owner only)
  DELETE /job-requests/{job_id}/interest     — provider withdraws interest (auth)

``/me`` is declared before ``/{job_id}`` to prevent FastAPI from treating
the literal string "me" as a UUID path parameter.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, status

from app.core.dependencies import CurrentUser, DBSession
from app.models.job_request import Urgency
from app.models.provider_listing import ServiceCategory
from app.schemas.job_interest import JobInterestCreate, JobInterestResponse
from app.schemas.job_request import (
    JobRequestCreate,
    JobRequestResponse,
    JobRequestUpdate,
    PaginatedJobRequestResponse,
)
from app.services import job_interest_service, job_request_service

router = APIRouter(prefix="/job-requests", tags=["Job Requests"])


@router.post(
    "",
    response_model=JobRequestResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Post a new job request",
)
async def create_job(
    payload: JobRequestCreate,
    db: DBSession,
    current_user: CurrentUser,
) -> JobRequestResponse:
    """
    Create a job request as the authenticated customer.
    Phone must be verified. Returns the created job with embedded customer info.
    """
    return await job_request_service.create_job(db, payload, current_user)


@router.get(
    "/me",
    response_model=list[JobRequestResponse],
    status_code=status.HTTP_200_OK,
    summary="Get all job requests posted by the current user",
)
async def get_my_jobs(
    db: DBSession,
    current_user: CurrentUser,
) -> list[JobRequestResponse]:
    """Return all job requests owned by the authenticated user, newest first."""
    return await job_request_service.get_my_jobs(db, current_user)


@router.get(
    "",
    response_model=PaginatedJobRequestResponse,
    status_code=status.HTTP_200_OK,
    summary="Browse open job requests (public)",
)
async def browse_jobs(
    db: DBSession,
    page: Annotated[int, Query(ge=1, description="Page number (1-indexed)")] = 1,
    page_size: Annotated[
        int, Query(ge=1, le=100, description="Results per page (max 100)")
    ] = 20,
    city: Annotated[
        str | None,
        Query(max_length=100, description="Filter by city (case-insensitive)"),
    ] = None,
    service_category: Annotated[
        ServiceCategory | None,
        Query(description="Filter by service category"),
    ] = None,
    urgency: Annotated[
        Urgency | None,
        Query(description="Filter by urgency level"),
    ] = None,
) -> PaginatedJobRequestResponse:
    """
    Paginated public feed of open job requests.
    Only jobs with status=open are returned. Supports city, category, and urgency filters.
    """
    return await job_request_service.browse_jobs(
        db,
        page=page,
        page_size=page_size,
        city=city,
        service_category=service_category,
        urgency=urgency,
    )


@router.get(
    "/{job_id}",
    response_model=JobRequestResponse,
    status_code=status.HTTP_200_OK,
    summary="Get a single job request by ID (public)",
)
async def get_job(
    job_id: UUID,
    db: DBSession,
) -> JobRequestResponse:
    """
    Fetch any job request by UUID. View counter is incremented on each call.
    No authentication required.
    """
    return await job_request_service.get_job_by_id(db, job_id)


@router.put(
    "/{job_id}",
    response_model=JobRequestResponse,
    status_code=status.HTTP_200_OK,
    summary="Update a job request (owner only)",
)
async def update_job(
    job_id: UUID,
    payload: JobRequestUpdate,
    db: DBSession,
    current_user: CurrentUser,
) -> JobRequestResponse:
    """
    Update any subset of editable job fields (PATCH semantics via PUT).
    Only the posting customer may update. Returns 403 for other users.
    Returns 409 if the job is already cancelled or completed.
    """
    return await job_request_service.update_job(db, job_id, payload, current_user)


@router.post(
    "/{job_id}/close",
    response_model=JobRequestResponse,
    status_code=status.HTTP_200_OK,
    summary="Close (cancel) a job request (owner only)",
)
async def close_job(
    job_id: UUID,
    db: DBSession,
    current_user: CurrentUser,
) -> JobRequestResponse:
    """
    Cancel an open or assigned job request.
    Only the posting customer may close it.
    Returns 409 if already cancelled or completed.
    """
    return await job_request_service.close_job(db, job_id, current_user)


# ---------------------------------------------------------------------------
# Phase 2B — Provider Interest endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/{job_id}/interest",
    response_model=JobInterestResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Express interest in a job (provider only)",
    tags=["Job Interests"],
)
async def express_interest(
    job_id: UUID,
    payload: JobInterestCreate,
    db: DBSession,
    current_user: CurrentUser,
) -> JobInterestResponse:
    """
    Register a provider listing's interest in an open job.

    The caller must supply their ``provider_listing_id``.  An optional
    ``message`` (pitch) and ``quoted_price`` (PKR) may also be included.

    Returns 403 if the listing does not belong to the caller or is inactive.
    Returns 404 if the job or listing does not exist.
    Returns 409 if the job is not open or if this listing has already
    expressed interest in this job.
    """
    return await job_interest_service.express_interest(
        db, job_id, payload, current_user
    )


@router.get(
    "/{job_id}/interests",
    response_model=list[JobInterestResponse],
    status_code=status.HTTP_200_OK,
    summary="List interested providers for a job (customer/owner only)",
    tags=["Job Interests"],
)
async def list_interests(
    job_id: UUID,
    db: DBSession,
    current_user: CurrentUser,
) -> list[JobInterestResponse]:
    """
    Return all provider listings that have expressed interest in this job,
    ordered from oldest to newest.

    Only the job's posting customer may access this list.
    Provider phone numbers are not included — they remain gated behind the
    contact-unlock system (Phase 4).

    Returns 403 if the caller is not the job's customer.
    Returns 404 if the job does not exist.
    """
    return await job_interest_service.list_interests(db, job_id, current_user)


@router.delete(
    "/{job_id}/interest",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Withdraw interest from a job (provider only)",
    tags=["Job Interests"],
)
async def withdraw_interest(
    job_id: UUID,
    listing_id: Annotated[
        UUID,
        Query(description="ID of the caller's listing whose interest is being withdrawn"),
    ],
    db: DBSession,
    current_user: CurrentUser,
) -> None:
    """
    Remove a provider listing's interest from a job.

    ``listing_id`` (query parameter) identifies which of the caller's
    listings to withdraw.  Returns 204 No Content on success.

    Returns 403 if the listing does not belong to the caller.
    Returns 404 if the job, the listing, or the interest record is not found.
    """
    await job_interest_service.withdraw_interest(
        db, job_id, listing_id, current_user
    )
