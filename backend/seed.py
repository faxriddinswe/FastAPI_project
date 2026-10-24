"""
Seed script — creates default admin user.
Run once after `alembic upgrade head`.

Usage:
    cd backend
    python seed.py
"""
import asyncio
from app.database import AsyncSessionLocal, engine, Base
from app.models import User, UserRole
from app.auth import hash_password
from sqlalchemy import select


async def seed():
    async with AsyncSessionLocal() as db:
        # Check if admin already exists
        result = await db.execute(select(User).where(User.email == "admin@pdp.uz"))
        if result.scalar_one_or_none():
            print("✅ Admin already exists — skipping seed")
            return

        admin = User(
            email="admin@pdp.uz",
            full_name="PDP Admin",
            hashed_password=hash_password("Admin@1234"),
            role=UserRole.admin,
        )
        db.add(admin)
        await db.commit()
        print("✅ Admin created: admin@pdp.uz / Admin@1234")


if __name__ == "__main__":
    asyncio.run(seed())
