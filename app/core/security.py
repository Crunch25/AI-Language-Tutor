from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID, uuid4

import jwt
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError, PyJWTError
from pwdlib import PasswordHash

from app.core.config import get_settings

settings = get_settings()

# Initialize Argon2-based password hashing via pwdlib recommended defaults
password_hash = PasswordHash.recommended()


class TokenVerificationError(Exception):
    """Raised when a JWT signature, format, or claim validation fails."""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(self.message)


class TokenExpiredError(TokenVerificationError):
    """Raised when a JWT has expired."""

    def __init__(self, message: str = "Token has expired") -> None:
        super().__init__(message)


def hash_password(password: str) -> str:
    """Hash a plaintext password using Argon2id."""
    return password_hash.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against an existing hash."""
    return password_hash.verify(plain_password, hashed_password)


def create_token(
    subject: str | UUID,
    token_type: str,
    expires_delta: timedelta,
    extra_claims: dict[str, Any] | None = None,
) -> str:
    """Encode a HS256 signed JWT with standardized UTC timestamps and claims."""
    now = datetime.now(timezone.utc)
    expire = now + expires_delta

    payload: dict[str, Any] = {
        "sub": str(subject),
        "type": token_type,
        "iat": int(now.timestamp()),
        "nbf": int(now.timestamp()),
        "exp": int(expire.timestamp()),
        "iss": settings.APP_NAME,
    }

    if extra_claims:
        payload.update(extra_claims)

    return jwt.encode(
        payload=payload,
        key=settings.JWT_SECRET_KEY.get_secret_value(),
        algorithm=settings.JWT_ALGORITHM,
    )


def decode_token(token: str) -> dict[str, Any]:
    """
    Decode and validate a JWT.
    Enforces signature, expiration, not-before, and issuer validation.
    """
    try:
        return jwt.decode(
            jwt=token,
            key=settings.JWT_SECRET_KEY.get_secret_value(),
            algorithms=[settings.JWT_ALGORITHM],
            options={
                "verify_signature": True,
                "verify_exp": True,
                "verify_nbf": True,
                "verify_iat": True,
                "require": ["sub", "type", "exp", "iat"],
            },
            issuer=settings.APP_NAME,
        )
    except ExpiredSignatureError as exc:
        raise TokenExpiredError() from exc
    except (InvalidTokenError, PyJWTError) as exc:
        raise TokenVerificationError(f"Could not validate token: {exc!s}") from exc


def create_access_token(
    subject: str | UUID,
    expires_delta: timedelta | None = None,
    extra_claims: dict[str, Any] | None = None,
) -> tuple[str, int]:
    """
    Creates a short-lived access token (default 15 minutes).
    Returns a tuple containing the token string and the lifetime in seconds.
    """
    delta = expires_delta or timedelta(minutes=15)
    token = create_token(
        subject=subject,
        token_type="access",
        expires_delta=delta,
        extra_claims=extra_claims,
    )
    return token, int(delta.total_seconds())


def create_refresh_token(
    subject: str | UUID,
    expires_delta: timedelta | None = None,
    extra_claims: dict[str, Any] | None = None,
) -> str:
    """
    Creates a long-lived refresh token (default 7 days) containing a unique jti.
    """
    delta = expires_delta or timedelta(days=7)
    claims = {"jti": str(uuid4())}
    if extra_claims:
        claims.update(extra_claims)

    return create_token(
        subject=subject,
        token_type="refresh",
        expires_delta=delta,
        extra_claims=claims,
    )