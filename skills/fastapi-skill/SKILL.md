---
name: fastapi-skill
description: FastAPI patterns for this project — routers, dependencies, JWT auth, Pydantic schemas, async SQLAlchemy, and error handling conventions.
---

# FastAPI Skill — PDP Academy

## Router Pattern
```python
from fastapi import APIRouter, Depends, HTTPException, status
router = APIRouter(prefix="/auth", tags=["auth"])
```

## Dependency Injection — DB Session
```python
from app.database import AsyncSessionLocal
from sqlalchemy.ext.asyncio import AsyncSession

async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session
```

## JWT Auth Dependencies
```python
from app.auth import get_current_user, require_role

# Any authenticated user
@router.get("/me")
async def me(user = Depends(get_current_user)):
    ...

# Role-specific
@router.post("/teachers")
async def create_teacher(user = Depends(require_role("admin")), db = Depends(get_db)):
    ...
```

## Pydantic Schema Convention
- **Request body:** `class UserCreate(BaseModel):`
- **Response:** `class UserOut(BaseModel): model_config = ConfigDict(from_attributes=True)`
- **Never** expose `hashed_password` in response schemas.

## HTTP Exceptions
```python
raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Validation error")
```

## Async SQLAlchemy Query Pattern
```python
from sqlalchemy import select
from app.models import User

result = await db.execute(select(User).where(User.email == email))
user = result.scalar_one_or_none()
```

## Password Hashing
```python
from passlib.context import CryptContext
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
hashed = pwd_context.hash(plain_password)
pwd_context.verify(plain_password, hashed)
```

## CORS Setup (main.py)
```python
app.add_middleware(CORSMiddleware,
    allow_origins=["*"],  # tighten in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

## Validation Regexes
```python
import re
PASSWORD_REGEX = r"^(?=.*?[A-Z])(?=.*?[a-z])(?=.*?[0-9])(?=.*?[#?!@$ %^&*\-]).{8,}$"
EMAIL_REGEX    = r"[^@ \t\r\n]+@[^@ \t\r\n]+\.[^@ \t\r\n]+"

def validate_password(p: str) -> bool:
    return bool(re.match(PASSWORD_REGEX, p))

def validate_email(e: str) -> bool:
    return bool(re.match(EMAIL_REGEX, e))
```
