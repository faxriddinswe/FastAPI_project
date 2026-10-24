# ANTIGRAVITY.md — PDP Academy Project Guide

## Project: Student Performance Checker

A full-stack education platform for managing students, teachers, and performance analytics.

## Architecture
- **Backend:** FastAPI (Python 3.11+) — `backend/`
- **Frontend:** HTML + CSS + JS — `frontend/`
- **DB:** SQLite (dev) via SQLAlchemy 2.x (async)
- **Migrations:** Alembic
- **Auth:** JWT (python-jose), bcrypt (passlib)

## Roles
| Role | Access | Login |
|---|---|---|
| `admin` | Full platform control, creates teachers | `/pdp-education-admin/` |
| `teacher` | Creates tests, generates links, views analytics | Home login |
| `student` | Takes tests via link, views own stats | Home signup/login |

## Running the Project

```bash
# Backend
cd backend
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload
# → http://127.0.0.1:8000
# → http://127.0.0.1:8000/docs

# Frontend
# Open frontend/ with Live Server or any static file server
# → http://127.0.0.1:5500
```

## Default Admin Credentials (seed)
- Email: `admin@pdp.uz`
- Password: `Admin@1234`

## Key Business Rules
1. Only **students** self-register via signup form.
2. **Teachers** are created only by admin.
3. Test access requires a **time-limited UUID link** from teacher.
4. Tests must be taken in **full-screen mode**.
5. > 3 fullscreen violations → auto-fail (score = 0, status = "Fail").
6. Students see only **statistics** in their dashboard — not raw test links.

## Validation Rules
- Password: `^(?=.*?[A-Z])(?=.*?[a-z])(?=.*?[0-9])(?=.*?[#?!@$ %^&*-]).{8,}$`
- Email: `[^@ \t\r\n]+@[^@ \t\r\n]+\.[^@ \t\r\n]+`

## Skills Available
- `skills/fastapi-skill/` — FastAPI patterns, JWT, Pydantic, routers
- `skills/alembic-skill/` — Alembic migration patterns
- `skills/ui-ux-pro-max-skill/` — Design intelligence & search

## Design System
- **Colors:** `#6366F1` (primary), `#06B6D4` (cyan), `#10B981` (success), `#EF4444` (danger)
- **Background:** `#0F172A`
- **Fonts:** Outfit (headings), Inter (body) — Google Fonts
- **Style:** Dark mode, soft UI evolution, bento grid cards
- See: `design-system/MASTER.md`
