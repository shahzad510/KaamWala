"""
Job interest service — all business logic for the provider interest flow.

Three operations are exposed:
  express_interest  — provider attaches their listing to an open job
  list_interests    — job owner retrieves all interested listings
  withdraw_interest — provider removes their listing's interest

Business rules enforced here (not in the API layer):
  - Caller must be phone-verified before expressing interest.
  - The supplied listing must be active and owned by the caller.
  - Interest may only be expressed on ``open`` jobs.
  - Duplicate (job_id, provider_listing_id) pairs are rejected with 409.
  - Only the job's customer may view the interest list.
  - Only the listing owner may withdraw their own interest.
"""

import logging
import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.job_interest import JobInterest
from app.models.job_request import JobRequest, JobStatus
from app.models.provider_listing import ProviderListing
from app.models.user import User
from app.schemas.job_interest import JobInterestCreate, JobInterestResponse

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


async def _get_job_or_404(db: AsyncSession, job_id: uuid.UUID) -> JobRequest:
    """Fetch a JobRequest by PK or raise 404."""
    result = await db.execute(select(JobRequest).where(JobRequest.id == job_id))
    job = result.scalar_one_or_none()
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job request not found.",
        )
    return job


async def _get_listing_or_404(
    db: AsyncSession, listing_id: uuid.UUID
) -> ProviderListing:
    """Fetch a ProviderListing by PK or raise 404."""
    result = await db.execute(
        select(ProviderListing).where(ProviderListing.id == listing_id)
    )
    listing = result.scalar_one_or_none()
    if listing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Provider listing not found.",
        )
    return listing


async def _get_interest_or_404(
    db: AsyncSession,
    job_id: uuid.UUID,
    listing_id: uuid.UUID,
) -> JobInterest:
    """Fetch a JobInterest by (job_id, listing_id) or raise 404."""
    result = await db.execute(
        select(JobInterest).where(
            JobInterest.job_id == job_id,
            JobInterest.provider_listing_id == listing_id,
        )
    )
    interest = result.scalar_one_or_none()
    if interest is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Interest record not found.",
        )
    return interest


# ---------------------------------------------------------------------------
# Public service functions
# ---------------------------------------------------------------------------


async def express_interest(
    db: AsyncSession,
    job_id: uuid.UUID,
    payload: JobInterestCreate,
    current_user: User,
) -> JobInterestResponse:
    """
    Register a provider listing's interest in an open job.

    Guards (in order):
      1. Phone must be verified.
      2. The supplied listing must exist.
      3. The listing must belong to the caller (prevents impersonation).
      4. The listing must be active (inactive listings cannot bid for work).
      5. The job must exist.
      6. The caller must not be the job's own customer (no self-interest).
      7. The job must be ``open`` (no interest on closed/completed jobs).
      8. No duplicate interest for this (job, listing) pair.
    """
    if not current_user.is_phone_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Phone number must be verified before expressing interest.",
        )

    listing = await _get_listing_or_404(db, payload.provider_listing_id)

    if listing.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only express interest using your own provider listing.",
        )

    if not listing.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive listings cannot express interest in jobs.",
        )

    job = await _get_job_or_404(db, job_id)

    if job.customer_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You cannot express interest in your own job request.",
        )

    if job.job_status != JobStatus.open:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Interest can only be expressed on open jobs. "
                   f"This job is currently '{job.job_status.value}'.",
        )

    # Duplicate check — also backed by a DB unique constraint to handle races.
    existing = await db.execute(
        select(JobInterest).where(
            JobInterest.job_id == job_id,
            JobInterest.provider_listing_id == payload.provider_listing_id,
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You have already expressed interest in this job with this listing.",
        )

    interest = JobInterest(
        job_id=job_id,
        provider_listing_id=payload.provider_listing_id,
        message=payload.message,
        quoted_price=payload.quoted_price,
    )

    db.add(interest)
    await db.flush()
    await db.refresh(interest)

    logger.info(
        "Interest expressed: listing %s on job %s by user %s",
        payload.provider_listing_id,
        job_id,
        current_user.id,
    )
    return JobInterestResponse.from_orm_with_provider(interest)


async def list_interests(
    db: AsyncSession,
    job_id: uuid.UUID,
    current_user: User,
) -> list[JobInterestResponse]:
    """
    Return all provider interests for a job, oldest first.

    Only the job's posting customer may call this endpoint.  Providers
    cannot enumerate their competitors; the customer uses this list to
    decide which provider to contact.
    """
    job = await _get_job_or_404(db, job_id)

    if job.customer_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the job's customer can view interested providers.",
        )

    result = await db.execute(
        select(JobInterest)
        .where(JobInterest.job_id == job_id)
        .order_by(JobInterest.created_at.asc())
    )
    interests = result.scalars().all()

    return [JobInterestResponse.from_orm_with_provider(i) for i in interests]


async def withdraw_interest(
    db: AsyncSession,
    job_id: uuid.UUID,
    listing_id: uuid.UUID,
    current_user: User,
) -> None:
    """
    Remove a provider listing's interest from a job.

    The caller must own the listing they are withdrawing.  There is no
    restriction on job status — a provider can withdraw even after a job
    is no longer open (e.g. if they want to clean up their interest history).
    The job itself must exist to avoid silent no-ops on bad job IDs.
    """
    # Confirm job exists (avoids silent no-ops for stale/invalid job IDs).
    await _get_job_or_404(db, job_id)

    listing = await _get_listing_or_404(db, listing_id)

    if listing.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only withdraw interest for your own provider listing.",
        )

    interest = await _get_interest_or_404(db, job_id, listing_id)

    await db.delete(interest)
    await db.flush()

    logger.info(
        "Interest withdrawn: listing %s from job %s by user %s",
        listing_id,
        job_id,
        current_user.id,
    )
