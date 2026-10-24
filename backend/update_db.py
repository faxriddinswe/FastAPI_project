
import asyncio
from app.database import engine, Base
import app.models # Ensuring all models are loaded

async def init_db():
    print("Updating database schema...")
    async with engine.begin() as conn:
        # This will create any missing tables
        await conn.run_sync(Base.metadata.create_all)
    print("Schema updated successfully.")

if __name__ == "__main__":
    asyncio.run(init_db())
