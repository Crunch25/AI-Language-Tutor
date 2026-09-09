# seed_test_data.py
import asyncio
from uuid import UUID
from app.core.database import async_session_factory
from app.models.user import User
from app.models.chat import ChatSession, CEFRLevel

async def seed():
    async with async_session_factory() as session:
        user_id = UUID("11111111-1111-1111-1111-111111111111")
        
        # Check if user already exists
        user = await session.get(User, user_id)
        if not user:
            user = User(
                id=user_id,
                email="learner@example.com",
                hashed_password="not_used_in_mock",
                full_name="Mock Student",
                is_active=True,
            )
            session.add(user)
            await session.flush()

        # Create a sample session
        chat_session = ChatSession(
            user_id=user.id,
            target_language="Spanish",
            current_cefr_level=CEFRLevel.A1,
            title="Swagger Test Session",
        )
        session.add(chat_session)
        await session.commit()
        
        print("\n Seeding complete!")
        print(f"Session ID to use in Swagger: {chat_session.id}\n")

if __name__ == "__main__":
    asyncio.run(seed())