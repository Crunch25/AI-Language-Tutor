# init_db.py
import asyncio
from app.core.database import engine, Base, dispose_database_engine
import app.models

async def init():
    print("Creating tables in Neon PostgreSQL...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("Database tables & indexes created successfully!")
    await dispose_database_engine()

if __name__ == "__main__":
    asyncio.run(init())