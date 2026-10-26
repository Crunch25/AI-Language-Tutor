from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.repositories.base import BaseRepository
from app.schemas.auth import UserRegister


class UserRepository(BaseRepository[User]):
    """Repository handling User persistence and identity lookups."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(User, session)

    async def get_by_id(self, user_id: UUID) -> User | None:
        """Fetch user by primary key ID."""
        return await self.get(user_id)

    async def get_by_email(self, email: str) -> User | None:
        """Fetch user by case-insensitive unique email."""
        stmt = select(User).where(User.email == email.lower().strip())
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create(self, user_in: UserRegister, hashed_password: str) -> User:
        """Persist a new User model from validated registration DTO."""
        user = User(
            email=user_in.email.lower().strip(),
            hashed_password=hashed_password,
            full_name=user_in.full_name.strip(),
            native_language=user_in.native_language.strip(),
            target_language=user_in.target_language.strip(),
            is_active=True,
            is_superuser=False,
            is_verified=False,
        )
        self.session.add(user)
        return user