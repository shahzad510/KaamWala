from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt

from app.core.config import settings


def create_access_token(subject: str, extra_data: dict[str, Any] | None = None) -> str:
    """Create a signed JWT access token for the given subject (user ID)."""
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    payload: dict[str, Any] = {
        "sub": str(subject),
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    if extra_data:
        payload.update(extra_data)

    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def verify_token(token: str) -> dict[str, Any]:
    """Decode and validate a JWT token. Raises JWTError on failure."""
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        return payload
    except JWTError:
        raise


def extract_user_id(token: str) -> str:
    """Extract the subject (user ID) from a valid JWT token."""
    payload = verify_token(token)
    user_id: str | None = payload.get("sub")
    if user_id is None:
        raise JWTError("Token has no subject claim")
    return user_id
