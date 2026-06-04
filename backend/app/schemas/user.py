"""
User-related Pydantic schemas.

Phone numbers are accepted in either local (03XXXXXXXXX) or international
(+923XXXXXXXXX) format and normalised to E.164 (+923XXXXXXXXX) before any
DB operation.  Normalisation is enforced at schema level so the service
layer and model always see a consistent format.
"""

import re
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.user import UserType

# Matches both local (03…) and international (+923…) Pakistani mobile formats.
# Captures the 10-digit suffix starting with 3 for normalisation.
_PK_PHONE_RE = re.compile(r"^(?:\+92|0)(3\d{9})$")


def normalize_phone(value: str) -> str:
    """Strip whitespace and normalize to +92XXXXXXXXXX international format."""
    value = value.strip().replace(" ", "").replace("-", "")
    match = _PK_PHONE_RE.match(value)
    if not match:
        raise ValueError(
            "Invalid Pakistani phone number. "
            "Accepted formats: 03001234567 or +923001234567"
        )
    return f"+92{match.group(1)}"


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class UserCreate(BaseModel):
    """Request body for the /auth/register endpoint."""

    phone: str = Field(..., examples=["03001234567"])
    name: str | None = Field(None, max_length=255, examples=["Ali Raza"])

    @field_validator("phone", mode="before")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        return normalize_phone(v)


class OTPVerifyRequest(BaseModel):
    """Request body for the /auth/verify-otp endpoint."""

    phone: str = Field(..., examples=["03001234567"])
    otp: str = Field(..., min_length=4, max_length=6, examples=["1234"])

    @field_validator("phone", mode="before")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        return normalize_phone(v)


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class UserResponse(BaseModel):
    """
    Public-safe user profile returned to authenticated clients.

    Sensitive financial fields (``outstanding_debt``, ``debt_incurred_at``,
    ``has_used_pay_later``) are intentionally excluded — they are internal
    billing data and should not be visible to client applications.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    phone: str
    name: str | None
    user_type: UserType
    is_phone_verified: bool
    free_contacts_remaining: int
    is_active: bool
    created_at: datetime


class TokenResponse(BaseModel):
    """Response body for the /auth/verify-otp endpoint."""

    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class MessageResponse(BaseModel):
    """Generic acknowledgement response for operations that return no resource."""

    message: str
    detail: str | None = None
