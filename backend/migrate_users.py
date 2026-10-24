
import asyncio
from sqlalchemy import text
from app.database import engine

async def migrate():
    print("Starting migration: Adding profile columns to 'users' table...")
    
    # List of columns to add
    columns = [
        ("phone", "VARCHAR(50)"),
        ("address", "TEXT"),
        ("avatar_url", "VARCHAR(500)"),
        ("gender", "VARCHAR(20)"),
        ("birth_date", "DATETIME"),
        ("nationality", "VARCHAR(100)"),
        ("passport_id", "VARCHAR(100)")
    ]
    
    async with engine.begin() as conn:
        for col_name, col_type in columns:
            try:
                print(f"Adding column: {col_name}...")
                await conn.execute(text(f"ALTER TABLE users ADD COLUMN {col_name} {col_type}"))
                print(f"Successfully added {col_name}.")
            except Exception as e:
                # If column already exists, sqlite will throw an error
                if "duplicate column name" in str(e).lower():
                    print(f"Column {col_name} already exists. Skipping.")
                else:
                    print(f"Error adding {col_name}: {e}")
                    
        # Also ensure Timetable table exists (create_all would have done this, but let's be safe)
        from app.models import Base
        await conn.run_sync(Base.metadata.create_all)
        
    print("Migration complete.")

if __name__ == "__main__":
    asyncio.run(migrate())
