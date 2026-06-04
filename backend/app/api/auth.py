"""
Authentication routes.

Three endpoints cover the full phone-OTP authentication lifecycle:
  POST /auth/register    — create account and dispatch OTP
  POST /auth/verify-otp  — validate OTP and receive JWT
  GET  /auth/me          — return the caller's own profile (protected)

All business logic lives in ``services/auth_service.py``; these handlers
are intentionally thin adapters.
"""

from fastapi import APIRouter, status

from app.core.dependencies import CurrentUser, DBSession
from app.schemas.user import (
    MessageResponse,
    OTPVerifyRequest,
    TokenResponse,
    UserCreate,
    UserResponse,
)
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/register",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Register phone number and receive OTP",
)
async def register(payload: UserCreate, db: DBSession) -> MessageResponse:
    """
    Accept phone + optional name, create the user if they don't exist,
    then dispatch a (stub) OTP to their phone number.
    """
    result = await auth_service.register_user(db, payload)
    return MessageResponse(**result)


@router.post(
    "/verify-otp",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Verify OTP and receive JWT access token",
)
async def verify_otp(payload: OTPVerifyRequest, db: DBSession) -> TokenResponse:
    """
    Validate the submitted OTP, mark the phone as verified,
    and return a signed JWT access token.
    """
    return await auth_service.verify_otp_and_login(db, payload)


@router.get(
    "/me",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Get the current authenticated user",
)
async def get_me(current_user: CurrentUser) -> UserResponse:
    """Protected route — returns the profile of the bearer-token owner."""
    return UserResponse.model_validate(current_user)
