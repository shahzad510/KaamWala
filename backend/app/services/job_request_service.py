"""
Job Request service — all business logic for job CRUD.
Routes stay thin; this layer owns domain rules and DB access.
"""

import logging
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.job_request import JobRequest, JobStatus, Urgency
from app.models.provider_listing import ServiceCategory
from app.models.user import User
from app.schemas.job_request import (
    JobRequestCreate,
    JobRequestResponse,
    JobRequestUpdate,
    PaginatedJobRequestResponse,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_TERMINAL_STATUSES = {JobStatus.cancelled, JobStatus.completed}


async def _get_job_or_404(db: AsyncSession, job_id: uuid.UUID) -> JobRequest:
    """Fetch a JobRequest by PK or raise 404."""
    result = await db.execute(
        select(JobRequest).where(JobRequest.id == job_id)
    )
    job = result.scalar_one_or_none()
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job request not found.",
        )
    return job


def _assert_owner(job: JobRequest, current_user: User) -> None:
    """Raise 403 if current_user is not the job's customer."""
    if job.customer_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to modify this job request.",
        )


# ---------------------------------------------------------------------------
# CRUD operations
# ---------------------------------------------------------------------------


async def create_job(
    db: AsyncSession,
    payload: JobRequestCreate,
    current_user: User,
) -> JobRequestResponse:
    """Create a new job request for the authenticated customer."""
    if not current_user.is_phone_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Phone number must be verified before posting a job.",
        )

    job = JobRequest(
        customer_id=current_user.id,
        **payload.model_dump(),
    )

    db.add(job)
    await db.flush()
    await db.refresh(job)

    logger.info("Job request created: %s by user %s", job.id, current_user.id)
    return JobRequestResponse.from_orm_with_customer(job)


async def get_my_jobs(
    db: AsyncSession,
    current_user: User,
) -> list[JobRequestResponse]:
    """Return all job requests created by the authenticated user, newest first."""
    result = await db.execute(
        select(JobRequest)
        .where(JobRequest.customer_id == current_user.id)
        .order_by(JobRequest.created_at.desc())
    )
    jobs = result.scalars().all()
    return [JobRequestResponse.from_orm_with_customer(j) for j in jobs]


async def get_job_by_id(
    db: AsyncSession,
    job_id: uuid.UUID,
) -> JobRequestResponse:
    """
    Fetch a single job request by ID, increment its view counter, and return it.
    Available publicly — no auth required at the route level.
    """
    job = await _get_job_or_404(db, job_id)
    job.views_count += 1
    await db.flush()
    return JobRequestResponse.from_orm_with_customer(job)


async def browse_jobs(
    db: AsyncSession,
    page: int,
    page_size: int,
    city: str | None,
    service_category: ServiceCategory | None,
    urgency: Urgency | None,
) -> PaginatedJobRequestResponse:
    """
    Return a paginated list of open job requests with optional filters.
    Only jobs with job_status = open are visible on the public browse feed.
    """
    base_query = select(JobRequest).where(JobRequest.job_status == JobStatus.open)

    if city:
        base_query = base_query.where(
            func.lower(JobRequest.city) == city.lower()
        )
    if service_category:
        base_query = base_query.where(
            JobRequest.service_category == service_category
        )
    if urgency:
        base_query = base_query.where(JobRequest.urgency == urgency)

    count_result = await db.execute(
        select(func.count()).select_from(base_query.subquery())
    )
    total = count_result.scalar_one()

    offset = (page - 1) * page_size
    paginated_query = (
        base_query
        .order_by(JobRequest.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    result = await db.execute(paginated_query)
    jobs = result.scalars().all()

    return PaginatedJobRequestResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=[JobRequestResponse.from_orm_with_customer(j) for j in jobs],
    )


async def update_job(
    db: AsyncSession,
    job_id: uuid.UUID,
    payload: JobRequestUpdate,
    current_user: User,
) -> JobRequestResponse:
    """Update a job request. Only the owner (customer) may do this."""
    job = await _get_job_or_404(db, job_id)
    _assert_owner(job, current_user)

    if job.job_status in _TERMINAL_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot update a job that is already {job.job_status.value}.",
        )

    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(job, field, value)

    job.updated_at = datetime.now(timezone.utc)
    await db.flush()
    await db.refresh(job)

    logger.info("Job request updated: %s by user %s", job.id, current_user.id)
    return JobRequestResponse.from_orm_with_customer(job)


async def close_job(
    db: AsyncSession,
    job_id: uuid.UUID,
    current_user: User,
) -> JobRequestResponse:
    """
    Cancel an open or assigned job request.
    Only the owner may close it; raises 409 if already in a terminal state.
    """
    job = await _get_job_or_404(db, job_id)
    _assert_owner(job, current_user)

    if job.job_status in _TERMINAL_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Job request is already {job.job_status.value} and cannot be closed again.",
        )

    job.job_status = JobStatus.cancelled
    job.updated_at = datetime.now(timezone.utc)
    await db.flush()
    await db.refresh(job)

    logger.info("Job request closed (cancelled): %s by user %s", job.id, current_user.id)
    return JobRequestResponse.from_orm_with_customer(job)
