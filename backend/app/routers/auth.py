import os
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from dotenv import load_dotenv
import httpx

# .env is at project root: routers/ -> app/ -> backend/ -> project root
_env_path = Path(__file__).resolve().parent.parent.parent.parent / ".env"
load_dotenv(dotenv_path=_env_path, override=True)

from app.database import get_db
from app.models import User, Student, Teacher, UserRole
from app.auth import (
    validate_email, validate_password,
    hash_password, verify_password,
    create_access_token,
)

router = APIRouter(prefix="/auth", tags=["auth"])

# ── Google OAuth Config ──────────────────────────────────────────────────────
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
GOOGLE_REDIRECT_URI = os.getenv(
    "GOOGLE_REDIRECT_URI",
    "http://localhost:8000/api/auth/google/callback"
)
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"

# After token created, redirect frontend here with token as query param
FRONTEND_CALLBACK = "/auth-callback.html"

# ── Schemas ──────────────────────────────────────────────────────────────────
class SignupRequest(BaseModel):
    full_name: str
    email: str
    password: str


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    full_name: str
    user_id: int


ROLE_REDIRECTS = {
    "admin": "/pdp-education-admin/dashboard.html",
    "teacher": "/pages/teacher/dashboard.html",
    "student": "/pages/student/dashboard.html",
}


# ── Email / Password Auth ────────────────────────────────────────────────────
@router.post("/signup", status_code=status.HTTP_201_CREATED)
async def signup(body: SignupRequest, db: AsyncSession = Depends(get_db)):
    """Student self-registration only."""
    if not validate_email(body.email):
        raise HTTPException(status_code=422, detail="Invalid email format")
    if not validate_password(body.password):
        raise HTTPException(
            status_code=422,
            detail=(
                "Password must be at least 8 characters and include "
                "uppercase, lowercase, digit, and special character (#?!@$ %^&*-)."
            ),
        )

    existing = await db.execute(select(User).where(User.email == body.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(
        email=body.email,
        full_name=body.full_name,
        hashed_password=hash_password(body.password),
        role=UserRole.student,
    )
    db.add(user)
    await db.flush()

    student = Student(user_id=user.id)
    db.add(student)
    await db.commit()
    await db.refresh(user)

    return {"message": "Registered successfully", "user_id": user.id}


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()

    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account disabled")

    token = create_access_token({"sub": str(user.id), "role": user.role.value})

    return TokenResponse(
        access_token=token,
        role=user.role.value,
        full_name=user.full_name,
        user_id=user.id,
    )


# ── Google OAuth ─────────────────────────────────────────────────────────────
@router.get("/google")
async def google_login():
    """Redirect user to Google's OAuth consent screen."""
    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "prompt": "select_account",
    }
    query = "&".join(f"{k}={v}" for k, v in params.items())
    return RedirectResponse(url=f"{GOOGLE_AUTH_URL}?{query}")


@router.get("/google/callback")
async def google_callback(code: str, db: AsyncSession = Depends(get_db)):
    """Handle Google OAuth callback, exchange code for token, create/find user."""
    # 1. Exchange code → access token
    async with httpx.AsyncClient() as client:
        token_resp = await client.post(
            GOOGLE_TOKEN_URL,
            data={
                "code": code,
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "redirect_uri": GOOGLE_REDIRECT_URI,
                "grant_type": "authorization_code",
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        if token_resp.status_code != 200:
            return RedirectResponse(
                url=f"{FRONTEND_CALLBACK}?error=token_exchange_failed"
            )
        token_data = token_resp.json()
        access_token_google = token_data.get("access_token")

        # 2. Fetch user info from Google
        userinfo_resp = await client.get(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token_google}"},
        )
        if userinfo_resp.status_code != 200:
            return RedirectResponse(
                url=f"{FRONTEND_CALLBACK}?error=userinfo_failed"
            )
        userinfo = userinfo_resp.json()

    email = userinfo.get("email")
    full_name = userinfo.get("name", email)
    google_sub = userinfo.get("sub")  # Google unique user ID

    if not email:
        return RedirectResponse(
            url=f"{FRONTEND_CALLBACK}?error=no_email"
        )

    # 3. Find or create user
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if not user:
        # Auto-create student accounts for Google login
        user = User(
            email=email,
            full_name=full_name,
            hashed_password=hash_password(google_sub),  # placeholder, not used for login
            role=UserRole.student,
            is_active=True,
        )
        db.add(user)
        await db.flush()
        student = Student(user_id=user.id)
        db.add(student)
        await db.commit()
        await db.refresh(user)
    elif not user.is_active:
        return RedirectResponse(
            url=f"{FRONTEND_CALLBACK}?error=account_disabled"
        )

    # 4. Issue our own JWT
    jwt_token = create_access_token({"sub": str(user.id), "role": user.role.value})

    # 5. Redirect frontend with token + role embedded in URL
    role = user.role.value
    return RedirectResponse(
        url=f"{FRONTEND_CALLBACK}?token={jwt_token}&role={role}&name={full_name}&user_id={user.id}"
    )
