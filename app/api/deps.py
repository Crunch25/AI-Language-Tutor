from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from app.core.security import TokenExpiredError, TokenVerificationError, decode_token
from app.core.exceptions import InvalidTokenError
from app.core.unit_of_work import UOWDep
from app.models.user import User
from app.schemas.auth import TokenPayload

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    uow: UOWDep,
) -> User:
    """
    Decodes the Bearer access token, validates claims,
    and loads the corresponding active User from the database.
    """
    authenticate_value = "Bearer"
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": authenticate_value},
    )

    try:
        raw_claims = decode_token(token)
        claims = TokenPayload.model_validate(raw_claims)
    except TokenExpiredError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": authenticate_value},
        )
    except (TokenVerificationError, InvalidTokenError, Exception):
        raise credentials_exception

    # Enforce access token classification to prevent refresh token misuse
    if claims.type != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type: Expected access token",
            headers={"WWW-Authenticate": authenticate_value},
        )

    try:
        user_id = UUID(str(claims.sub))
    except (ValueError, TypeError):
        raise credentials_exception

    user = await uow.user_repo.get_by_id(user_id)
    if user is None:
        raise credentials_exception

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Inactive user account",
            headers={"WWW-Authenticate": authenticate_value},
        )

    return user


async def get_current_active_superuser(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """Validates that the authenticated caller holds superuser privileges."""
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions for this operation",
        )
    return current_user


# Strongly typed injection aliases for route handlers
CurrentUser = Annotated[User, Depends(get_current_user)]
CurrentAdmin = Annotated[User, Depends(get_current_active_superuser)]