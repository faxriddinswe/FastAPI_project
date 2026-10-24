from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from app.database import get_db
from app.models import (
    User, Student, TestLink, Test, Question,
    TestSession, Answer, TestStatus, Group, GroupStudent, Timetable
)
from app.auth import require_role, get_current_user

router = APIRouter(prefix="/student", tags=["student"])
student_required = require_role("student")

class ProfileUpdate(BaseModel):
    full_name: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    avatar_url: Optional[str] = None
    gender: Optional[str] = None
    birth_date: Optional[datetime] = None
    nationality: Optional[str] = None
    passport_id: Optional[str] = None

@router.get("/profile")
async def get_student_profile_data(current_user: User = Depends(student_required)):
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

@router.put("/profile")
async def update_student_profile(
    body: ProfileUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(student_required),
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

@router.get("/timetable")
async def get_student_timetable(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(student_required),
):
    student = await get_student_profile(current_user, db)
    # Get groups this student is in
    result = await db.execute(
        select(Timetable, Group)
        .join(Group, Group.id == Timetable.group_id)
        .join(GroupStudent, GroupStudent.group_id == Group.id)
        .where(GroupStudent.student_id == student.id)
        .order_by(Timetable.day_of_week, Timetable.lesson_number)
    )
    rows = result.all()
    return [
        {
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

MAX_VIOLATIONS = 3


# ── Helpers ───────────────────────────────────────────────────────────────────
async def get_student_profile(user: User, db: AsyncSession) -> Student:
    result = await db.execute(select(Student).where(Student.user_id == user.id))
    student = result.scalar_one_or_none()
    if not student:
        raise HTTPException(status_code=404, detail="Student profile not found")
    return student


async def get_valid_link(token: str, db: AsyncSession, student_id: int) -> TestLink:
    result = await db.execute(select(TestLink).where(TestLink.token == token, TestLink.is_active == True))
    link = result.scalar_one_or_none()

    if not link:
        raise HTTPException(status_code=404, detail="Invalid or inactive test link")

    now_utc = datetime.utcnow()
    if now_utc < link.start_time or now_utc > link.end_time:
        raise HTTPException(status_code=400, detail="Test link expired")

    # check group restriction
    if link.group_id:
        gres = await db.execute(select(GroupStudent).where(GroupStudent.group_id == link.group_id, GroupStudent.student_id == student_id))
        if not gres.scalar_one_or_none():
            raise HTTPException(status_code=403, detail="Test is restricted to members of a specific group.")

    return link


# ── Endpoints ──────────────────────────────────────────────────────────────────
@router.get("/tests/{token}")
async def access_test(
    token: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(student_required),
):
    student = await get_student_profile(current_user, db)
    link = await get_valid_link(token, db, student.id)

    # Check for existing complete session
    existing_result = await db.execute(
        select(TestSession).where(
            TestSession.student_id == student.id,
            TestSession.test_link_id == link.id,
            TestSession.status != TestStatus.in_progress,
        )
    )
    if existing_result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="You have already completed this test")

    # Get or create in-progress session
    session_result = await db.execute(
        select(TestSession).where(
            TestSession.student_id == student.id,
            TestSession.test_link_id == link.id,
            TestSession.status == TestStatus.in_progress,
        )
    )
    session = session_result.scalar_one_or_none()
    if not session:
        session = TestSession(student_id=student.id, test_link_id=link.id)
        db.add(session)
        await db.commit()
        await db.refresh(session)

    # Load test + questions (without correct answers)
    test_result = await db.execute(select(Test).where(Test.id == link.test_id))
    test = test_result.scalar_one()
    questions_result = await db.execute(select(Question).where(Question.test_id == test.id))
    questions = questions_result.scalars().all()

    # Calculate effective timer end time
    # If test has a time_limit_minutes, timer = session.started_at + limit (or link end if sooner)
    timer_end = link.end_time
    if test.time_limit_minutes:
        from datetime import timedelta, timezone
        limit_end = session.started_at + timedelta(minutes=test.time_limit_minutes)
        timer_end = min(limit_end, link.end_time)
    
    from datetime import timezone
    if timer_end.tzinfo is None:
        timer_end_str = timer_end.replace(tzinfo=timezone.utc).isoformat()
    else:
        timer_end_str = timer_end.isoformat()

    return {
        "session_id": session.id,
        "test_title": test.title,
        "test_description": test.description,
        "topic": test.topic,
        "end_time": timer_end_str,
        "time_limit_minutes": test.time_limit_minutes,
        "violations_count": session.violations_count,
        "questions": [
            {
                "id": q.id,
                "text": q.text,
                "options": q.options,
                "question_type": q.question_type,
                "points": q.points,
            }
            for q in questions
        ],
    }


class ViolationResponse(BaseModel):
    violations_count: int
    auto_submitted: bool
    message: str


@router.post("/tests/{token}/violation", response_model=ViolationResponse)
async def report_violation(
    token: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(student_required),
):
    student = await get_student_profile(current_user, db)
    link = await get_valid_link(token, db, student.id)

    session_result = await db.execute(
        select(TestSession).where(
            TestSession.student_id == student.id,
            TestSession.test_link_id == link.id,
            TestSession.status == TestStatus.in_progress,
        )
    )
    session = session_result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Active test session not found")

    session.violations_count += 1

    if session.violations_count >= MAX_VIOLATIONS:
        session.status = TestStatus.auto_failed
        session.score = 0.0
        session.submitted_at = datetime.utcnow()
        await db.commit()
        return ViolationResponse(
            violations_count=session.violations_count,
            auto_submitted=True,
            message="Test auto-submitted due to fullscreen violations. Score: 0",
        )

    await db.commit()
    return ViolationResponse(
        violations_count=session.violations_count,
        auto_submitted=False,
        message=f"Warning {session.violations_count}/{MAX_VIOLATIONS}: Return to fullscreen",
    )


class SubmitAnswerItem(BaseModel):
    question_id: int
    chosen_answer: Optional[str] = None  # "A","B","C","D" or null


class SubmitRequest(BaseModel):
    answers: List[SubmitAnswerItem]
    force_fail: bool = False


@router.post("/tests/{token}/submit")
async def submit_test(
    token: str,
    body: SubmitRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(student_required),
):
    student = await get_student_profile(current_user, db)
    link = await get_valid_link(token, db, student.id)

    session_result = await db.execute(
        select(TestSession).where(
            TestSession.student_id == student.id,
            TestSession.test_link_id == link.id,
            TestSession.status == TestStatus.in_progress,
        )
    )
    session = session_result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="No active session found")

    # Load questions
    questions_result = await db.execute(select(Question).where(Question.test_id == link.test_id))
    questions = {q.id: q for q in questions_result.scalars().all()}

    # Score calculation unconditionally
    total_points = sum(q.points for q in questions.values())
    session.total_questions = len(questions)

    if body.force_fail or session.violations_count >= MAX_VIOLATIONS:
        session.score = 0.0
        session.status = TestStatus.auto_failed
    else:
        earned_points = 0.0
        correct_answers = 0

        for answer_item in body.answers:
            q = questions.get(answer_item.question_id)
            if not q:
                continue
            answer_record = Answer(
                session_id=session.id,
                question_id=answer_item.question_id,
                chosen_answer=answer_item.chosen_answer,
            )
            db.add(answer_record)
            
            answer_val = str(answer_item.chosen_answer) if answer_item.chosen_answer else ""
            correct_val = str(q.correct_answer)
            
            def norm_text(t: str) -> str:
                lines = t.replace('\r\n', '\n').replace('\t', '    ').split('\n')
                lines = [l.rstrip() for l in lines]
                while lines and not lines[-1]: lines.pop()
                while lines and not lines[0]: lines.pop(0)
                return '\n'.join(lines)
            
            answer_val_norm = norm_text(answer_val)
            correct_val_norm = norm_text(correct_val)
            
            is_correct = False
            
            import json
            if q.question_type == "matching":
                try:
                    user_dict = json.loads(answer_item.chosen_answer)
                    correct_dict = json.loads(q.correct_answer)
                    # strict dictionary match
                    if user_dict == correct_dict:
                        is_correct = True
                except:
                    pass
            elif q.question_type == "code_editor":
                if answer_item.chosen_answer:
                    import subprocess
                    import tempfile
                    import os
                    import sys
                    
                    fd, path = tempfile.mkstemp(suffix=".py")
                    with os.fdopen(fd, 'w', encoding='utf-8') as f:
                        f.write(answer_val)
                    
                    output = ""
                    try:
                        result = subprocess.run(["python", path], capture_output=True, text=True, timeout=2.0)
                        output = result.stdout
                        if result.stderr:
                            output += "\n" + result.stderr
                    except subprocess.TimeoutExpired:
                        output = "Timeout"
                    finally:
                        try:
                            os.remove(path)
                        except:
                            pass
                            
                    output_norm = norm_text(output)
                    if output_norm == correct_val_norm:
                        is_correct = True
            elif q.question_type == "open_ended":
                if answer_item.chosen_answer and answer_val_norm == correct_val_norm:
                    is_correct = True
            elif answer_item.chosen_answer and answer_val_norm.upper() == correct_val_norm.upper():
                is_correct = True
                
            if is_correct:
                earned_points += q.points
                correct_answers += 1
                
        session.correct_answers = correct_answers

        session.score = round((earned_points / total_points) * 100, 1) if total_points > 0 else 0.0
        session.status = TestStatus.passed if session.score >= 60 else TestStatus.failed

    session.submitted_at = datetime.utcnow()
    await db.commit()

    return {
        "score": session.score,
        "status": session.status.value,
        "message": "Test submitted successfully",
    }


@router.get("/stats")
async def my_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(student_required),
):
    student = await get_student_profile(current_user, db)

    sessions_result = await db.execute(
        select(TestSession, TestLink, Test)
        .join(TestLink, TestLink.id == TestSession.test_link_id)
        .join(Test, Test.id == TestLink.test_id)
        .where(
            TestSession.student_id == student.id,
            TestSession.status != TestStatus.in_progress,
        )
    )
    rows = sessions_result.all()

    sessions_out = []
    topic_scores: dict = {}

    for s, tl, t in rows:
        sessions_out.append({
            "test_title": t.title,
            "topic": t.topic,
            "score": s.score,
            "status": s.status.value,
            "violations": s.violations_count,
            "total_questions": s.total_questions,
            "correct_answers": s.correct_answers,
            "is_graded": s.is_graded,
            "teacher_grade": s.teacher_grade,
            "submitted_at": s.submitted_at.isoformat() if s.submitted_at else None,
        })
        if t.topic and s.score is not None:
            topic_scores.setdefault(t.topic, []).append(s.score)

    topic_avg = {
        topic: round(sum(scores) / len(scores), 1)
        for topic, scores in topic_scores.items()
    }

    total = len(sessions_out)
    passed = sum(1 for s in sessions_out if s["status"] == "passed")

    return {
        "full_name": current_user.full_name,
        "total_tests": total,
        "passed": passed,
        "failed": total - passed,
        "pass_rate": round((passed / total * 100), 1) if total > 0 else 0,
        "sessions": sessions_out,
        "topic_averages": topic_avg,
    }


@router.get("/leaderboard")
async def leaderboard(
    group_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(student_required),
):
    current_student = await get_student_profile(current_user, db)

    # Base query for test sessions
    q = select(TestSession, Student, User)\
        .join(Student, Student.id == TestSession.student_id)\
        .join(User, User.id == Student.user_id)\
        .where(
            TestSession.status == TestStatus.passed,
            TestSession.score.isnot(None),
        )

    # Optional group filter
    if group_id:
        q = q.join(GroupStudent, GroupStudent.student_id == Student.id)\
             .where(GroupStudent.group_id == group_id)

    sessions_result = await db.execute(q)
    rows = sessions_result.all()

    student_data: dict = {}
    for session, student, user in rows:
        sid = student.id
        if sid not in student_data:
            student_data[sid] = {"student_id": sid, "full_name": user.full_name, "scores": [], "tests_passed": 0}
        student_data[sid]["scores"].append(session.score)
        student_data[sid]["tests_passed"] += 1

    rankings = []
    for data in student_data.values():
        avg = round(sum(data["scores"]) / len(data["scores"]), 1)
        rankings.append({
            "student_id": data["student_id"],
            "full_name": data["full_name"],
            "avg_score": avg,
            "tests_passed": data["tests_passed"],
            "best_score": max(data["scores"]),
        })

    rankings.sort(key=lambda x: (-x["avg_score"], -x["tests_passed"]))
    for i, r in enumerate(rankings):
        r["rank"] = i + 1

    my_rank = next((r for r in rankings if r["student_id"] == current_student.id), None)

    # fetch student's groups to show in the dropdown
    g_res = await db.execute(
        select(Group.id, Group.name)
        .join(GroupStudent, GroupStudent.group_id == Group.id)
        .where(GroupStudent.student_id == current_student.id)
    )
    my_groups = [{"id": r[0], "name": r[1]} for r in g_res.all()]

    return {
        "rankings": rankings,
        "my_rank": my_rank,
        "total_students": len(rankings),
        "available_groups": my_groups
    }
