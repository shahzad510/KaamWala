import re
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.user import UserType

# Pakistani phone: 03XXXXXXXXX or +923XXXXXXXXX
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
    phone: str = Field(..., examples=["03001234567"])
    name: str | None = Field(None, max_length=255, examples=["Ali Raza"])

    @field_validator("phone", mode="before")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        return normalize_phone(v)


class OTPVerifyRequest(BaseModel):
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
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class MessageResponse(BaseModel):
    message: str
    detail: str | None = None
