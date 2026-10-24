# Directive: Project Overview — PDP Academy

## Goal
Build a student performance checker platform for an educational institution.

## Tools / Scripts
- `backend/` — FastAPI server (run via `uvicorn app.main:app --reload`)
- `backend/migrations/` — Alembic migrations
- `frontend/` — Static HTML/CSS/JS served by browser
- `skills/ui-ux-pro-max-skill/src/ui-ux-pro-max/scripts/search.py` — design system generator

## Input
- Teacher creates a test (questions + answers)  
- Teacher generates a time-limited link
- Teacher shares link with student

## Output
- Student completes test under proctored conditions
- Score is stored in DB
- Analytics are shown in dashboards (student + teacher)

## Roles & Permissions
| Action | Admin | Teacher | Student |
|---|---|---|---|
| Create teacher | ✅ | ❌ | ❌ |
| Create test | ❌ | ✅ | ❌ |
| Generate test link | ❌ | ✅ | ❌ |
| Take test | ❌ | ❌ | ✅ (via link) |
| View own stats | ❌ | ❌ | ✅ |
| View student stats | ❌ | ✅ | ❌ |
| View all platform data | ✅ | ❌ | ❌ |

## Edge Cases
1. Link expired → 403 response
2. Violations > 3 → auto-submit score=0
3. Student tries to access test page directly (no token) → redirect to home
4. Teacher tries to access admin panel → 403
5. Signup attempt with invalid password/email → 422 with clear message
