import hashlib
import os
import secrets
from typing import Optional, Dict, Any, List
from fastapi import Request, HTTPException, status, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

from app.database import get_db, SessionLocal
from app.models import User

SECRET_KEY = os.environ.get("LINEUP_SECRET_KEY", "lineup-super-secret-key-2026-secure")
serializer = URLSafeTimedSerializer(SECRET_KEY, salt="lineup-session-salt")
COOKIE_NAME = "lineup_session"
SESSION_MAX_AGE = 60 * 60 * 24 * 7  # 7 days

def hash_password(password: str) -> str:
    """Hash password using standard PBKDF2-HMAC-SHA256."""
    salt = secrets.token_hex(16)
    key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100000)
    return f"{salt}${key.hex()}"

def verify_password(password: str, stored_hash: str) -> bool:
    """Verify password against stored salt$hash."""
    try:
        salt, key_hex = stored_hash.split("$")
        key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100000)
        return secrets.compare_digest(key.hex(), key_hex)
    except Exception:
        return False

def create_session_token(user: User) -> str:
    payload = {
        "user_id": user.id,
        "username": user.username,
        "role": user.role,
        "counter_number": user.counter_number
    }
    return serializer.dumps(payload)

def decode_session_token(token: str) -> Optional[Dict[str, Any]]:
    try:
        return serializer.loads(token, max_age=SESSION_MAX_AGE)
    except (BadSignature, SignatureExpired, Exception):
        return None

def seed_default_users(db: Session):
    """Seed initial Admin and Staff accounts if users table is empty."""
    user_count = db.query(User).count()
    if user_count == 0:
        default_users = [
            User(
                username="admin",
                password_hash=hash_password("admin123"),
                role="admin",
                counter_number=1
            ),
            User(
                username="staff1",
                password_hash=hash_password("staff123"),
                role="staff",
                counter_number=1
            ),
            User(
                username="staff2",
                password_hash=hash_password("staff123"),
                role="staff",
                counter_number=2
            ),
        ]
        for u in default_users:
            db.add(u)
        db.commit()

def get_current_user_optional(request: Request, db: Session = Depends(get_db)) -> Optional[User]:
    """Retrieve logged in user from cookie or Authorization header, or None."""
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:]

    if not token:
        return None

    data = decode_session_token(token)
    if not data or "user_id" not in data:
        return None

    user = db.query(User).filter(User.id == data["user_id"]).first()
    return user

def require_staff_user(request: Request, db: Session = Depends(get_db)) -> User:
    """Ensure user is logged in as staff or admin. Redirects or raises 401."""
    user = get_current_user_optional(request, db)
    if not user:
        # Check if browser HTML request -> redirect to login
        accept = request.headers.get("accept", "")
        if "text/html" in accept:
            raise HTTPException(
                status_code=status.HTTP_307_TEMPORARY_REDIRECT,
                headers={"Location": f"/login?next={request.url.path}"}
            )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="សូមចូលប្រើប្រាស់ជាមុនសិន / Please log in as staff or admin"
        )
    
    if user.role not in ["staff", "admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="អ្នកមិនមានសិទ្ធិប្រើប្រាស់មុខងារនេះទេ / Access forbidden: Staff role required"
        )
    return user

def require_admin_user(request: Request, db: Session = Depends(get_db)) -> User:
    """Ensure user is logged in as admin."""
    user = require_staff_user(request, db)
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="ទាមទារសិទ្ធិជា Admin / Access forbidden: Admin role required"
        )
    return user
