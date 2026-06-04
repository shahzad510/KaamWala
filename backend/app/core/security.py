"""
JWT utility functions.

All token operations are centralised here so that algorithm and secret
rotation can be done in a single place.  Routes and services must never
call python-jose directly — they must go through these helpers.
"""

from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt

from app.core.config import settings


def create_access_token(subject: str, extra_data: dict[str, Any] | None = None) -> str:
    """
    Build and sign a JWT access token.

    ``subject`` should be the user's UUID string — it becomes the ``sub`` claim.
    ``extra_data`` can inject additional claims (e.g. roles) without changing
    the function signature; callers must ensure they don't overwrite reserved
    claims (sub, exp, iat).
    """
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
    """
    Decode and validate a JWT token, returning its payload.

    Raises ``JWTError`` for any failure: expired token, invalid signature,
    malformed structure.  Callers are expected to catch this and respond
    with a 401.  Expiry is checked automatically by python-jose.
    """
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
    """
    Extract the ``sub`` claim (user UUID string) from a verified token.

    Raises ``JWTError`` if the token is invalid or the ``sub`` claim is absent.
    The returned string must be cast to UUID by the caller.
    """
    payload = verify_token(token)
    user_id: str | None = payload.get("sub")
    if user_id is None:
        raise JWTError("Token has no subject claim")
    return user_id
