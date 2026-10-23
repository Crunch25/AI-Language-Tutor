from datetime import datetime, timedelta, timezone
from uuid import UUID

from backend.app.core.exceptions import (
    DuplicateEmailError,
    InactiveUserError,
    InvalidCredentialsError,
    InvalidTokenError,
    SecurityCompromisedError,
    TokenRevokedError,
)
from backend.app.core.security import (
    TokenExpiredError,
    TokenVerificationError,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from backend.app.core.unit_of_work import IUnitOfWork
from backend.app.models.user import User
from backend.app.schemas.auth import TokenPayload, TokenResponse, UserLogin, UserRegister


class AuthService:
    def __init__(self, uow: IUnitOfWork) -> None:
        self.uow = uow

    async def register(self, payload: UserRegister) -> User:
        """
        Registers a new user account.
        
        Checks email availability, generates an Argon2 hash, and saves the user record.
        """
        existing_user = await self.uow.user_repo.get_by_email(payload.email)
        if existing_user is not None:
            raise DuplicateEmailError()

        hashed_pwd = hash_password(payload.password)
        user = await self.uow.user_repo.create(payload, hashed_password=hashed_pwd)
        await self.uow.commit()
        return user

    async def authenticate(self, payload: UserLogin) -> TokenResponse:
        """
        Authenticates user credentials and provisions a fresh token pair.
        """
        user = await self.uow.user_repo.get_by_email(payload.email)
        if user is None:
            raise InvalidCredentialsError()

        if not user.is_active:
            raise InactiveUserError()

        if not verify_password(payload.password, user.hashed_password):
            raise InvalidCredentialsError()

        # Generate tokens
        access_token, expires_in = create_access_token(subject=user.id)
        refresh_token_str = create_refresh_token(subject=user.id)

        # Decode token to extract auto-generated JTI and EXP
        decoded_claims = decode_token(refresh_token_str)
        jti = decoded_claims["jti"]
        exp_timestamp = decoded_claims["exp"]
        expires_at = datetime.fromtimestamp(exp_timestamp, tz=timezone.utc)

        # Persist refresh token tracking record
        await self.uow.token_repo.create_token_record(
            user_id=user.id,
            jti=jti,
            expires_at=expires_at,
        )
        await self.uow.commit()

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token_str,
            token_type="bearer",
            expires_in=expires_in,
        )

    async def refresh_token(self, refresh_token_str: str) -> TokenResponse:
        """
        Rotates an existing refresh token for a new access + refresh token pair.

        Detects replay attacks: if a revoked token is used, all active sessions
        for the owning user are immediately invalidated.
        """
        try:
            raw_claims = decode_token(refresh_token_str)
            claims = TokenPayload.model_validate(raw_claims)
        except (TokenVerificationError, TokenExpiredError, Exception) as exc:
            raise InvalidTokenError() from exc

        if claims.type != "refresh" or not claims.jti:
            raise InvalidTokenError("Token is not a valid refresh token.")

        user_id = UUID(str(claims.sub))
        jti = claims.jti

        # Look up token record directly by JTI
        stored_token = await self.uow.token_repo.get(
            # Fetch by checking matching JTI directly
            entity_id=None  # Handled via custom lookup below
        ) if False else None

        # Direct search by JTI across all rows
        token_record = await self.uow.token_repo.get_active_token(jti)

        if token_record is None:
            # Check if token exists in revoked state to detect replay attack
            from sqlalchemy import select
            from backend.app.models.user import RefreshToken

            stmt = select(RefreshToken).where(RefreshToken.jti == jti)
            result = await self.uow.token_repo.session.execute(stmt)
            revoked_record = result.scalar_one_or_none()

            if revoked_record is not None:
                # Token reuse detected: Revoke all refresh tokens for this user
                await self.uow.token_repo.revoke_all_user_tokens(user_id)
                await self.uow.commit()
                raise SecurityCompromisedError()

            raise TokenRevokedError()

        # Mark existing token as revoked (rotation policy)
        await self.uow.token_repo.revoke_token(jti)

        # Verify the user is active
        user = await self.uow.user_repo.get_by_id(user_id)
        if user is None or not user.is_active:
            await self.uow.commit()
            raise InactiveUserError()

        # Generate new token pair
        new_access_token, expires_in = create_access_token(subject=user.id)
        new_refresh_token_str = create_refresh_token(subject=user.id)

        # Extract claims of newly minted refresh token
        new_claims = decode_token(new_refresh_token_str)
        new_jti = new_claims["jti"]
        new_exp_timestamp = new_claims["exp"]
        new_expires_at = datetime.fromtimestamp(new_exp_timestamp, tz=timezone.utc)

        # Store new refresh token record
        await self.uow.token_repo.create_token_record(
            user_id=user.id,
            jti=new_jti,
            expires_at=new_expires_at,
        )
        await self.uow.commit()

        return TokenResponse(
            access_token=new_access_token,
            refresh_token=new_refresh_token_str,
            token_type="bearer",
            expires_in=expires_in,
        )

    async def logout(self, refresh_token_str: str) -> None:
        """
        Invalidates a refresh token session by revoking its unique JTI.
        """
        try:
            raw_claims = decode_token(refresh_token_str)
            claims = TokenPayload.model_validate(raw_claims)
        except Exception:
            # If token is invalid or malformed, return cleanly to maintain idempotent logout
            return

        if claims.type == "refresh" and claims.jti:
            await self.uow.token_repo.revoke_token(claims.jti)
            await self.uow.commit()