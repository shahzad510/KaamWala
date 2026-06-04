"""
FastAPI dependency providers.

This module defines the two reusable dependency aliases used across all
protected routes:

  - ``CurrentUser``  — resolves a Bearer token to a verified, active User.
  - ``DBSession``    — provides a per-request async SQLAlchemy session.

Import these aliases directly in route signatures instead of calling
``Depends(...)`` inline; this keeps route handlers readable and makes
the dependency graph easy to change in one place.
"""

from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import extract_user_id
from app.db.session import get_db
from app.models.user import User
from app.services import auth_service

# auto_error=False prevents FastAPI from raising a 403 automatically when the
# Authorization header is missing.  We raise a 401 ourselves below so that the
# WWW-Authenticate header is included, which is required by RFC 6750.
bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """
    Resolve a Bearer token to the corresponding active User.

    Authentication failures (missing/invalid/expired token, unknown user)
    all return 401 with a generic message to avoid leaking information.

    A separate 403 is raised for deactivated accounts: the token is valid
    but the account has been suspended — a distinct error code helps clients
    differentiate "please log in again" from "your account is banned".
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if credentials is None:
        raise credentials_exception

    try:
        user_id_str = extract_user_id(credentials.credentials)
        user_id = UUID(user_id_str)
    except (JWTError, ValueError):
        raise credentials_exception

    user = await auth_service.get_user_by_id(db, user_id)
    if user is None:
        # Return 401, not 404, to avoid confirming whether a user ID exists.
        raise credentials_exception
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated",
        )
    return user


# Type aliases for use in route signatures.
# Annotated[..., Depends(...)] tells FastAPI to inject the dependency while
# preserving the inner type for mypy / pyright.
CurrentUser = Annotated[User, Depends(get_current_user)]
DBSession = Annotated[AsyncSession, Depends(get_db)]
