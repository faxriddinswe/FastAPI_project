from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional

from app.database import get_db
from app.models import User, Teacher, UserRole
from app.auth import require_role, hash_password, validate_email, validate_password

router = APIRouter(prefix="/admin", tags=["admin"])

admin_required = require_role("admin")


class CreateTeacherRequest(BaseModel):
    full_name: str
    email: str
    password: str
    subject: Optional[str] = None


@router.post("/teachers", status_code=status.HTTP_201_CREATED)
async def create_teacher(
    body: CreateTeacherRequest,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(admin_required),
):
    if not validate_email(body.email):
        raise HTTPException(status_code=422, detail="Invalid email format")
    if not validate_password(body.password):
        raise HTTPException(
            status_code=422,
            detail="Password must be at least 8 chars with uppercase, lowercase, digit, and special char",
        )

    existing = await db.execute(select(User).where(User.email == body.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(
        email=body.email,
        full_name=body.full_name,
        hashed_password=hash_password(body.password),
        role=UserRole.teacher,
    )
    db.add(user)
    await db.flush()

    teacher = Teacher(user_id=user.id, subject=body.subject)
    db.add(teacher)
    await db.commit()
    await db.refresh(user)

    return {"message": "Teacher created", "user_id": user.id, "teacher_id": teacher.id}


@router.get("/teachers")
async def list_teachers(
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(admin_required),
):
    result = await db.execute(
        select(User, Teacher)
        .join(Teacher, Teacher.user_id == User.id)
        .where(User.role == UserRole.teacher)
    )
    rows = result.all()
    return [
        {
            "user_id": u.id,
            "teacher_id": t.id,
            "full_name": u.full_name,
            "email": u.email,
            "subject": t.subject,
            "is_active": u.is_active,
            "created_at": u.created_at.isoformat(),
        }
        for u, t in rows
    ]


@router.delete("/teachers/{user_id}", status_code=204)
async def delete_teacher(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(admin_required),
):
    result = await db.execute(select(User).where(User.id == user_id, User.role == UserRole.teacher))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Teacher not found")
    user.is_active = False
    await db.commit()


@router.get("/stats")
async def admin_stats(
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(admin_required),
):
    from sqlalchemy import func
    from app.models import Student, TestSession

    teachers_count = (await db.execute(select(func.count()).where(User.role == UserRole.teacher, User.is_active == True))).scalar()
    students_count = (await db.execute(select(func.count()).where(User.role == UserRole.student, User.is_active == True))).scalar()
    sessions_count = (await db.execute(select(func.count(TestSession.id)))).scalar()

    return {
        "teachers": teachers_count,
        "students": students_count,
        "test_sessions": sessions_count,
    }
