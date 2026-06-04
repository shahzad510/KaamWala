"""
Auth service — all business logic for registration, OTP verification, and token issuance.
Routes stay thin; this layer owns the domain rules.
"""

import uuid
import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.models.user import User
from app.schemas.user import UserCreate, OTPVerifyRequest, TokenResponse, UserResponse
from app.utils.otp import generate_otp, save_otp, send_otp, verify_otp

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# CRUD helpers
# ---------------------------------------------------------------------------


async def get_user_by_phone(db: AsyncSession, phone: str) -> User | None:
    """Look up a user by their normalised E.164 phone number."""
    result = await db.execute(select(User).where(User.phone == phone))
    return result.scalar_one_or_none()


async def get_user_by_id(db: AsyncSession, user_id: uuid.UUID) -> User | None:
    """Look up a user by their UUID primary key."""
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


# ---------------------------------------------------------------------------
# Business logic
# ---------------------------------------------------------------------------


async def register_user(db: AsyncSession, payload: UserCreate) -> dict:
    """
    Register a new user or silently return success for an existing unverified account.
    Generates and dispatches a (stub) OTP.
    """
    existing = await get_user_by_phone(db, payload.phone)

    if existing and existing.is_phone_verified:
        # User already fully registered — still send a fresh OTP so they can log in.
        # We don't block re-registration: it doubles as the "login" flow.
        logger.info("Existing verified user requesting OTP: %s", payload.phone)
    elif existing is None:
        user = User(
            phone=payload.phone,
            name=payload.name,
        )
        db.add(user)
        await db.flush()  # Assign PK without committing yet
        logger.info("New user registered: %s", payload.phone)

    otp_code = generate_otp()
    save_otp(payload.phone, otp_code)
    send_otp(payload.phone, otp_code)  # Logs to terminal in MVP

    return {"message": "OTP sent successfully", "detail": f"OTP sent to {payload.phone}"}


async def verify_otp_and_login(
    db: AsyncSession, payload: OTPVerifyRequest
) -> TokenResponse:
    """Verify OTP, mark phone as verified, and return a JWT token."""
    is_valid, reason = verify_otp(payload.phone, payload.otp)

    if not is_valid:
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=reason,
        )

    user = await get_user_by_phone(db, payload.phone)
    if user is None:
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found. Please register first.",
        )

    if not user.is_phone_verified:
        user.is_phone_verified = True
        user.updated_at = datetime.now(timezone.utc)

    access_token = create_access_token(subject=str(user.id))

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse.model_validate(user),
    )
