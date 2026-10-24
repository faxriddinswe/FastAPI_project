import uuid
from datetime import datetime
from typing import List, Optional, Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from app.database import get_db
from app.models import (
    User, Teacher, Test, Question, TestLink, TestSession, Student,
    Group, GroupStudent, Timetable
)
from app.auth import require_role, get_current_user

router = APIRouter(prefix="/teacher", tags=["teacher"])

teacher_required = require_role("teacher", "admin")


# ── Schemas ────────────────────────────────────────────────────────────────────
class QuestionCreate(BaseModel):
    text: str
    options: Optional[Any] = None
    correct_answer: str      # Can be text or choice
    question_type: str = "multiple_choice" # multiple_choice, open_ended, true_false, matching
    points: float = 1.0


class TestCreate(BaseModel):
    title: str
    description: Optional[str] = None
    topic: Optional[str] = None
    time_limit_minutes: Optional[int] = None
    questions: Optional[List[QuestionCreate]] = None


class LinkCreate(BaseModel):
    start_time: datetime
    end_time: datetime
    group_id: Optional[int] = None

class GroupCreate(BaseModel):
    name: str

class StudentsAdd(BaseModel):
    emails: List[str]


# ── Helpers ───────────────────────────────────────────────────────────────────
async def get_teacher_profile(user: User, db: AsyncSession) -> Teacher:
    result = await db.execute(select(Teacher).where(Teacher.user_id == user.id))
    teacher = result.scalar_one_or_none()
    if not teacher:
        raise HTTPException(status_code=404, detail="Teacher profile not found")
    return teacher


# ── Groups ────────────────────────────────────────────────────────────────────
@router.post("/groups", status_code=201)
async def create_group(
    body: GroupCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(teacher_required)
):
    teacher = await get_teacher_profile(current_user, db)
    group = Group(name=body.name, teacher_id=teacher.id)
    db.add(group)
    await db.commit()
    await db.refresh(group)
    return {"message": "Group created successfully", "group_id": group.id}

@router.get("/groups")
async def list_groups(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(teacher_required)
):
    teacher = await get_teacher_profile(current_user, db)
    res = await db.execute(select(Group).where(Group.teacher_id == teacher.id))
    groups = res.scalars().all()
    
    out = []
    for g in groups:
        # count students
        c_res = await db.execute(select(GroupStudent).where(GroupStudent.group_id == g.id))
        count = len(c_res.scalars().all())
        out.append({"id": g.id, "name": g.name, "students_count": count})
    return {"groups": out}

@router.post("/groups/{group_id}/students")
async def add_students_to_group(
    group_id: int,
    body: StudentsAdd,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(teacher_required)
):
    teacher = await get_teacher_profile(current_user, db)
    # verify group
    res = await db.execute(select(Group).where(Group.id == group_id, Group.teacher_id == teacher.id))
    group = res.scalar_one_or_none()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    
    added = 0
    not_found = []
    
    for email in body.emails:
        email = email.strip()
        if not email: continue
        # Find user
        u_res = await db.execute(select(User).where(User.email == email, User.role == "student"))
        u = u_res.scalar_one_or_none()
        if not u:
            not_found.append(email)
            continue
            
        s_res = await db.execute(select(Student).where(Student.user_id == u.id))
        student = s_res.scalar_one_or_none()
        if not student:
            not_found.append(email)
            continue
            
        # check if already in group
        gs_res = await db.execute(select(GroupStudent).where(GroupStudent.group_id == group.id, GroupStudent.student_id == student.id))
        if gs_res.scalar_one_or_none():
            continue # already in
            
        db.add(GroupStudent(group_id=group.id, student_id=student.id))
        added += 1
        
        
    await db.commit()
    return {"message": f"Added {added} students", "not_found": not_found}


@router.get("/groups/{group_id}")
async def get_group_details(
    group_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(teacher_required)
):
    teacher = await get_teacher_profile(current_user, db)
    # verify group
    res = await db.execute(select(Group).where(Group.id == group_id, Group.teacher_id == teacher.id))
    group = res.scalar_one_or_none()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    # get students
    s_res = await db.execute(
        select(User.full_name, User.email)
        .join(Student, Student.user_id == User.id)
        .join(GroupStudent, GroupStudent.student_id == Student.id)
        .where(GroupStudent.group_id == group.id)
    )
    students = s_res.all()
    
    return {
        "id": group.id,
        "name": group.name,
        "students": [{"full_name": s[0], "email": s[1]} for s in students]
    }


# ── Endpoints ──────────────────────────────────────────────────────────────────
@router.post("/tests", status_code=201)
async def create_test(
    body: TestCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(teacher_required),
):
    teacher = await get_teacher_profile(current_user, db)
    test = Test(
        title=body.title,
        description=body.description,
        topic=body.topic,
        time_limit_minutes=body.time_limit_minutes,
        teacher_id=teacher.id,
    )
    db.add(test)
    await db.flush()

    if body.questions:
        for q in body.questions:
            question = Question(
                test_id=test.id,
                text=q.text,
                options=q.options,
                correct_answer=q.correct_answer,
                question_type=q.question_type,
                points=q.points,
            )
            db.add(question)

    await db.commit()
    await db.refresh(test)
    return {"message": "Test created", "test_id": test.id}


@router.get("/tests")
async def list_my_tests(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(teacher_required),
):
    teacher = await get_teacher_profile(current_user, db)
    result = await db.execute(select(Test).where(Test.teacher_id == teacher.id, Test.is_active == True))
    tests = result.scalars().all()
    return [
        {
            "id": t.id,
            "title": t.title,
            "description": t.description,
            "topic": t.topic,
            "time_limit_minutes": t.time_limit_minutes,
            "created_at": t.created_at.isoformat(),
        }
        for t in tests
    ]


@router.post("/tests/{test_id}/questions", status_code=201)
async def add_question(
    test_id: int,
    body: QuestionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(teacher_required),
):
    teacher = await get_teacher_profile(current_user, db)
    result = await db.execute(select(Test).where(Test.id == test_id, Test.teacher_id == teacher.id))
    test = result.scalar_one_or_none()
    if not test:
        raise HTTPException(status_code=404, detail="Test not found")

    question = Question(
        test_id=test_id,
        text=body.text,
        options=body.options,
        correct_answer=body.correct_answer if body.question_type in ["code_editor", "open_ended"] else body.correct_answer.upper(),
        question_type=body.question_type,
        points=body.points,
    )
    db.add(question)
    await db.commit()
    return {"message": "Question added", "question_id": question.id}


@router.delete("/tests/{test_id}", status_code=204)
async def delete_test(
    test_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(teacher_required),
):
    teacher = await get_teacher_profile(current_user, db)
    result = await db.execute(select(Test).where(Test.id == test_id, Test.teacher_id == teacher.id))
    test = result.scalar_one_or_none()
    if not test:
        raise HTTPException(status_code=404, detail="Test not found")

    await db.delete(test)
    await db.commit()
    return None

class TestUpdate(BaseModel):
    title: str
    description: Optional[str] = None
    topic: Optional[str] = None
    questions: Optional[List[QuestionCreate]] = None

@router.put("/tests/{test_id}", status_code=200)
async def update_test(
    test_id: int,
    body: TestUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(teacher_required),
):
    teacher = await get_teacher_profile(current_user, db)
    from sqlalchemy.orm import selectinload
    result = await db.execute(
        select(Test)
        .options(selectinload(Test.questions))
        .where(Test.id == test_id, Test.teacher_id == teacher.id)
    )
    test = result.scalar_one_or_none()
    if not test:
        raise HTTPException(status_code=404, detail="Test not found")

    test.title = body.title
    test.description = body.description
    test.topic = body.topic

    if body.questions is not None:
        # Note: In a production app, we would better sync by ID.
        # Here we just clear the old questions to simple rewrite, but we must be careful with existing answers.
        # SQLite cascade handles it, but losing older answers isn't ideal.
        # Alternatively we can just disable test editing if it has been taken.
        await db.execute(select(Question).where(Question.test_id == test_id))
        test.questions = []
        for q in body.questions:
            question = Question(
                text=q.text,
                options=q.options,
                correct_answer=q.correct_answer,
                question_type=q.question_type,
                points=q.points,
            )
            test.questions.append(question)

    await db.commit()
    return {"message": "Test updated"}

@router.get("/tests/{test_id}")
async def get_test_detail(
    test_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(teacher_required),
):
    teacher = await get_teacher_profile(current_user, db)
    result = await db.execute(
        select(Test).where(Test.id == test_id, Test.teacher_id == teacher.id)
    )
    test = result.scalar_one_or_none()
    if not test:
        raise HTTPException(status_code=404, detail="Test not found")

    q_result = await db.execute(select(Question).where(Question.test_id == test_id))
    questions = q_result.scalars().all()

    return {
        "id": test.id,
        "title": test.title,
        "description": test.description,
        "topic": test.topic,
        "questions": [
            {
                "id": q.id,
                "text": q.text,
                "options": q.options,
                "question_type": q.question_type or "multiple_choice",
                "correct_answer": q.correct_answer,
                "points": q.points,
            }
            for q in questions
        ],
    }


@router.post("/tests/{test_id}/duplicate", status_code=201)
async def duplicate_test(
    test_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(teacher_required),
):
    teacher = await get_teacher_profile(current_user, db)
    result = await db.execute(select(Test).where(Test.id == test_id, Test.teacher_id == teacher.id))
    test = result.scalar_one_or_none()
    if not test:
        raise HTTPException(status_code=404, detail="Test not found")

    q_result = await db.execute(select(Question).where(Question.test_id == test_id))
    questions = q_result.scalars().all()

    new_test = Test(
        title=f"{test.title} (Copy)",
        description=test.description,
        topic=test.topic,
        time_limit_minutes=test.time_limit_minutes,
        teacher_id=teacher.id
    )
    db.add(new_test)
    await db.flush()

    for q in questions:
        new_q = Question(
            test_id=new_test.id,
            text=q.text,
            options=q.options,
            correct_answer=q.correct_answer,
            question_type=q.question_type,
            points=q.points,
        )
        db.add(new_q)

    await db.commit()
    return {"message": "Test duplicated", "id": new_test.id}


@router.post("/tests/{test_id}/links", status_code=201)
async def generate_link(
    test_id: int,
    body: LinkCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(teacher_required),
):
    teacher = await get_teacher_profile(current_user, db)
    result = await db.execute(select(Test).where(Test.id == test_id, Test.teacher_id == teacher.id))
    test = result.scalar_one_or_none()
    if not test:
        raise HTTPException(status_code=404, detail="Test not found")

    if body.end_time <= body.start_time:
        raise HTTPException(status_code=422, detail="end_time must be after start_time")

    token = str(uuid.uuid4())
    link = TestLink(
        test_id=test_id,
        group_id=body.group_id,
        token=token,
        start_time=body.start_time,
        end_time=body.end_time,
    )
    db.add(link)
    await db.commit()

    return {
        "token": token,
        "test_link": f"/pages/test/take.html?token={token}",
        "start_time": body.start_time.isoformat(),
        "end_time": body.end_time.isoformat(),
    }


@router.get("/timetable")
async def get_teacher_timetable(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(teacher_required),
):
    teacher = await get_teacher_profile(current_user, db)
    result = await db.execute(
        select(Timetable, Group)
        .join(Group, Group.id == Timetable.group_id)
        .where(Timetable.teacher_id == teacher.id)
        .order_by(Timetable.day_of_week, Timetable.lesson_number)
    )
    rows = result.all()
    return [
        {
            "id": t.id,
            "day_of_week": t.day_of_week,
            "lesson_number": t.lesson_number,
            "start_time": t.start_time,
            "end_time": t.end_time,
            "room": t.room,
            "subject": t.subject,
            "group_name": g.name
        }
        for t, g in rows
    ]

@router.get("/attendance")
async def get_daily_attendance(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(teacher_required),
):
    teacher = await get_teacher_profile(current_user, db)
    # Students in groups managed by this teacher
    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    
    result = await db.execute(
        select(User, Student, Group)
        .join(Student, Student.user_id == User.id)
        .join(GroupStudent, GroupStudent.student_id == Student.id)
        .join(Group, Group.id == GroupStudent.group_id)
        .where(Group.teacher_id == teacher.id)
    )
    students = result.all()
    
    output = []
    for u, s, g in students:
        # Check if student had any session today
        sess_res = await db.execute(
            select(TestSession)
            .where(TestSession.student_id == s.id, TestSession.started_at >= today)
        )
        has_taken = sess_res.scalar_one_or_none() is not None
        output.append({
            "id": s.id,
            "full_name": u.full_name,
            "email": u.email,
            "group_name": g.name,
            "taken_today": has_taken
        })
    return output

@router.get("/profile")
async def get_profile(current_user: User = Depends(teacher_required)):
    return {
        "full_name": current_user.full_name,
        "email": current_user.email,
        "phone": current_user.phone,
        "address": current_user.address,
        "avatar_url": current_user.avatar_url,
        "gender": current_user.gender,
        "birth_date": current_user.birth_date.isoformat() if current_user.birth_date else None,
        "nationality": current_user.nationality,
        "passport_id": current_user.passport_id,
    }

class ProfileUpdate(BaseModel):
    full_name: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    avatar_url: Optional[str] = None
    gender: Optional[str] = None
    birth_date: Optional[datetime] = None
    nationality: Optional[str] = None
    passport_id: Optional[str] = None

@router.put("/profile")
async def update_profile(
    body: ProfileUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(teacher_required),
):
    if body.full_name is not None: current_user.full_name = body.full_name
    if body.phone is not None: current_user.phone = body.phone
    if body.address is not None: current_user.address = body.address
    if body.avatar_url is not None: current_user.avatar_url = body.avatar_url
    if body.gender is not None: current_user.gender = body.gender
    if body.birth_date is not None: current_user.birth_date = body.birth_date
    if body.nationality is not None: current_user.nationality = body.nationality
    if body.passport_id is not None: current_user.passport_id = body.passport_id
    
    await db.commit()
    return {"message": "Profile updated successfully"}

@router.get("/ungraded-sessions")
async def get_ungraded_sessions(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(teacher_required),
):
    teacher = await get_teacher_profile(current_user, db)
    result = await db.execute(
        select(TestSession, Test, User)
        .join(TestLink, TestLink.id == TestSession.test_link_id)
        .join(Test, Test.id == TestLink.test_id)
        .join(Student, Student.id == TestSession.student_id)
        .join(User, User.id == Student.user_id)
        .where(Test.teacher_id == teacher.id, TestSession.is_graded == False, TestSession.status == "passed")
    )
    rows = result.all()
    return [
        {
            "session_id": s.id,
            "test_title": t.title,
            "student_name": u.full_name,
            "score": s.score,
            "submitted_at": s.submitted_at.isoformat() if s.submitted_at else None,
        }
        for s, t, u in rows
    ]


@router.get("/tests/{test_id}/results")
async def test_results(
    test_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(teacher_required),
):
    teacher = await get_teacher_profile(current_user, db)
    # Verify ownership
    result = await db.execute(select(Test).where(Test.id == test_id, Test.teacher_id == teacher.id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Test not found")

    sessions_result = await db.execute(
        select(TestSession, Student, User)
        .join(TestLink, TestLink.id == TestSession.test_link_id)
        .join(Student, Student.id == TestSession.student_id)
        .join(User, User.id == Student.user_id)
        .where(TestLink.test_id == test_id)
    )
    rows = sessions_result.all()

    return [
        {
            "session_id": s.id,
            "student_name": u.full_name,
            "student_email": u.email,
            "score": s.score,
            "status": s.status.value,
            "total_questions": s.total_questions,
            "correct_answers": s.correct_answers,
            "violations": s.violations_count,
            "is_graded": s.is_graded,
            "teacher_grade": s.teacher_grade,
            "submitted_at": s.submitted_at.isoformat() if s.submitted_at else None,
        }
        for s, st, u in rows
    ]

class GradeRequest(BaseModel):
    grade: str # Pass, Merit, Distinction

@router.post("/sessions/{session_id}/grade")
async def grade_session(
    session_id: int,
    body: GradeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(teacher_required),
):
    teacher = await get_teacher_profile(current_user, db)
    
    # Needs to verify this session belongs to a test created by this teacher
    result = await db.execute(
        select(TestSession, Test)
        .join(TestLink, TestLink.id == TestSession.test_link_id)
        .join(Test, Test.id == TestLink.test_id)
        .where(TestSession.id == session_id, Test.teacher_id == teacher.id)
    )
    row = result.first()
    if not row:
        raise HTTPException(status_code=404, detail="Test session not found or access denied")
        
    session = row[0]
    if session.status.value in ["failed", "auto_failed"]:
        raise HTTPException(status_code=400, detail="Cannot grade a failed test")

    session.teacher_grade = body.grade
    session.is_graded = True
    await db.commit()
    
    return {"message": "Grade saved successfully"}



@router.get("/students/{student_id}/stats")
async def student_stats_for_teacher(
    student_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(teacher_required),
):
    result = await db.execute(
        select(TestSession, TestLink, Test, User, Student)
        .join(TestLink, TestLink.id == TestSession.test_link_id)
        .join(Test, Test.id == TestLink.test_id)
        .join(Student, Student.id == TestSession.student_id)
        .join(User, User.id == Student.user_id)
        .where(TestSession.student_id == student_id, TestSession.status != "in_progress")
    )
    rows = result.all()
    if not rows:
        return {"sessions": [], "topics": {}}

    student_user = rows[0][3]
    sessions_out = []
    topic_scores: dict[str, list] = {}

    for s, tl, t, u, st in rows:
        sessions_out.append({
            "test_title": t.title,
            "topic": t.topic,
            "score": s.score,
            "status": s.status.value,
            "submitted_at": s.submitted_at.isoformat() if s.submitted_at else None,
        })
        if t.topic and s.score is not None:
            topic_scores.setdefault(t.topic, []).append(s.score)

    topic_avg = {topic: round(sum(scores) / len(scores), 1) for topic, scores in topic_scores.items()}

    return {
        "student_name": student_user.full_name,
        "student_email": student_user.email,
        "sessions": sessions_out,
        "topic_averages": topic_avg,
    }
