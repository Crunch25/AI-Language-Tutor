from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import RefreshToken
from app.repositories.base import BaseRepository


class TokenRepository(BaseRepository[RefreshToken]):
    """Repository managing refresh token tracking, verification, and revocation."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(RefreshToken, session)

    async def create_token_record(
        self,
        user_id: UUID,
        jti: str,
        expires_at: datetime,
    ) -> RefreshToken:
        """Persist a refresh token entry to trace active refresh sessions."""
        token = RefreshToken(
            user_id=user_id,
            jti=jti,
            expires_at=expires_at,
            revoked=False,
        )
        self.session.add(token)
        return token

    async def get_active_token(self, jti: str) -> RefreshToken | None:
        """
        Look up a refresh token by JTI ensuring it has not been revoked
        and has not crossed its expiration threshold.
        """
        now = datetime.now(timezone.utc)
        stmt = select(RefreshToken).where(
            RefreshToken.jti == jti,
            RefreshToken.revoked.is_(False),
            RefreshToken.expires_at > now,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def revoke_token(self, jti: str) -> None:
        """Revoke a single refresh token by JTI identifier."""
        stmt = (
            update(RefreshToken)
            .where(RefreshToken.jti == jti)
            .values(revoked=True)
        )
        await self.session.execute(stmt)

    async def revoke_all_user_tokens(self, user_id: UUID) -> None:
        """Revoke all active refresh tokens for a user (force global logout)."""
        stmt = (
            update(RefreshToken)
            .where(
                RefreshToken.user_id == user_id,
                RefreshToken.revoked.is_(False),
            )
            .values(revoked=True)
        )
        await self.session.execute(stmt)