---
name: alembic-skill
description: Alembic migration patterns for this FastAPI project — setup, auto-generation, applying, rolling back.
---

# Alembic Skill — PDP Academy

## Initial Setup (already done)
```bash
cd backend
alembic init migrations
```

## env.py Config (key parts)
```python
from app.models import Base
from app.database import DATABASE_URL

config.set_main_option("sqlalchemy.url", DATABASE_URL)
target_metadata = Base.metadata
```

## Workflow
```bash
# Apply all pending migrations
alembic upgrade head

# Auto-generate a new migration after changing models.py
alembic revision --autogenerate -m "describe_what_changed"

# Apply new migration
alembic upgrade head

# Roll back one step
alembic downgrade -1

# View current version
alembic current

# View history
alembic history --verbose
```

## Naming Convention for Migration Files
`NNNN_verb_noun.py` — e.g., `0001_initial_schema.py`, `0002_add_violation_count.py`

## Important Rules
- **Always** run `alembic upgrade head` after pulling new code.
- **Never** edit an already-applied migration file. Create a new one.
- After changing `backend/app/models.py`, always generate a new migration.
- For SQLite: drop and recreate the dev DB if schema is in chaos (`rm app.db && alembic upgrade head`).

## Common Errors
| Error | Fix |
|---|---|
| `Can't locate revision` | Run `alembic stamp head` then `alembic upgrade head` |
| `Table already exists` | Add `checkfirst=True` or use `IF NOT EXISTS` in manual migration |
| `No module named 'app'` | Run from `backend/` directory, ensure `PYTHONPATH` includes `.` |
