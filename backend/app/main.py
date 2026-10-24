from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse, FileResponse
import os

from app.routers import auth, admin, teacher, student

app = FastAPI(
    title="PDP Academy API",
    description="Student Performance Checker — FastAPI Backend",
    version="1.0.0",
)

# ── CORS ──────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(teacher.router)
app.include_router(student.router)


# ── Admin panel redirect ───────────────────────────────────────────────────────
@app.get("/pdp-education-admin/", include_in_schema=False)
async def admin_panel():
    """Redirect to admin login HTML page."""
    return RedirectResponse(url="/pages/admin/login.html")

frontend_path = os.path.join(os.path.dirname(__file__), "..", "..", "frontend")

# ── Clean URL HTML Routes ─────────────────────────────────────────────────────
@app.get("/student/dashboard", include_in_schema=False)
@app.get("/student/dashboard/{full_path:path}", include_in_schema=False)
async def serve_student_dashboard():
    return FileResponse(os.path.join(frontend_path, "pages", "student", "dashboard.html"))

@app.get("/teacher/dashboard", include_in_schema=False)
@app.get("/teacher/dashboard/{full_path:path}", include_in_schema=False)
async def serve_teacher_dashboard():
    return FileResponse(os.path.join(frontend_path, "pages", "teacher", "dashboard.html"))



# ── Serve frontend as static files ───────────────────────────────────────────
if os.path.exists(frontend_path):
    app.mount("/", StaticFiles(directory=frontend_path, html=True), name="frontend")
