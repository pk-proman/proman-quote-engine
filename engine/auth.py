"""
PROMAN Authentication Module
JWT cookie-based auth with bcrypt passwords and role-based access.

Roles:
  admin  — full access (quotation engine + masters admin)
  user   — quotation engine only (no /masters)

Users stored in engine/users.json — never commit this file with real passwords.
Default admin on first boot: admin / proman@2024  (CHANGE IMMEDIATELY)

Environment variables:
  SECRET_KEY   — JWT signing secret (required in production, set on Render)
  TOKEN_EXPIRE_HOURS — session duration (default 12)
"""

import json
import os
import secrets
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Cookie, HTTPException, status

# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------

SECRET_KEY = os.getenv("SECRET_KEY") or secrets.token_hex(32)
ALGORITHM  = "HS256"
TOKEN_EXPIRE_HOURS = int(os.getenv("TOKEN_EXPIRE_HOURS", "12"))

USERS_FILE = Path(__file__).parent / "users.json"

pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ---------------------------------------------------------------------------
# USER STORE
# ---------------------------------------------------------------------------

def _load_users() -> dict:
    if not USERS_FILE.exists():
        _bootstrap_default_user()
    with open(USERS_FILE, "r") as f:
        return json.load(f)


def _save_users(data: dict):
    with open(USERS_FILE, "w") as f:
        json.dump(data, f, indent=2)


def _bootstrap_default_user():
    """Create initial admin user if no users file exists."""
    data = {
        "_note": "PROMAN user store. Keep this file private. Never commit to public repos.",
        "users": {
            "admin": {
                "hashed_password": pwd_ctx.hash("proman@2024"),
                "role": "admin",
                "name": "Admin",
                "active": True,
                "must_change_password": True,
            }
        }
    }
    _save_users(data)


# ---------------------------------------------------------------------------
# PASSWORD HELPERS
# ---------------------------------------------------------------------------

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_ctx.verify(plain, hashed)


def hash_password(plain: str) -> str:
    return pwd_ctx.hash(plain)


# ---------------------------------------------------------------------------
# JWT
# ---------------------------------------------------------------------------

def create_token(username: str, role: str) -> str:
    expire = datetime.utcnow() + timedelta(hours=TOKEN_EXPIRE_HOURS)
    payload = {"sub": username, "role": role, "exp": expire}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    """Returns payload dict or raises HTTPException."""
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired or invalid. Please log in again.",
        )


# ---------------------------------------------------------------------------
# USER CRUD
# ---------------------------------------------------------------------------

def authenticate_user(username: str, password: str) -> Optional[dict]:
    """Returns user dict if credentials valid, else None."""
    store = _load_users()
    user  = store["users"].get(username)
    if not user or not user.get("active"):
        return None
    if not verify_password(password, user["hashed_password"]):
        return None
    return {"username": username, **user}


def get_user(username: str) -> Optional[dict]:
    store = _load_users()
    user  = store["users"].get(username)
    if user:
        return {"username": username, **user}
    return None


def list_users() -> list:
    store = _load_users()
    return [
        {"username": u, "name": v.get("name",""), "role": v.get("role","user"),
         "active": v.get("active", True), "must_change_password": v.get("must_change_password", False)}
        for u, v in store["users"].items()
    ]


def create_user(username: str, password: str, name: str, role: str = "user") -> dict:
    store = _load_users()
    if username in store["users"]:
        raise ValueError(f"User '{username}' already exists.")
    store["users"][username] = {
        "hashed_password":       hash_password(password),
        "role":                  role,
        "name":                  name,
        "active":                True,
        "must_change_password":  True,
    }
    _save_users(store)
    return {"username": username, "role": role, "name": name}


def update_user(username: str, updates: dict) -> dict:
    store = _load_users()
    if username not in store["users"]:
        raise ValueError(f"User '{username}' not found.")
    if "password" in updates:
        store["users"][username]["hashed_password"] = hash_password(updates.pop("password"))
        store["users"][username]["must_change_password"] = False
    store["users"][username].update(updates)
    _save_users(store)
    return {"username": username, **store["users"][username]}


def delete_user(username: str):
    store = _load_users()
    if username == "admin":
        raise ValueError("Cannot delete the admin account.")
    store["users"].pop(username, None)
    _save_users(store)


# ---------------------------------------------------------------------------
# FASTAPI DEPENDENCIES
# ---------------------------------------------------------------------------

def _get_current_user(token: Optional[str]) -> dict:
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"X-Redirect": "/login"},
        )
    payload = decode_token(token)
    user = get_user(payload["sub"])
    if not user or not user.get("active"):
        raise HTTPException(status_code=401, detail="User inactive or not found.")
    return user


def require_login(proman_token: Optional[str] = Cookie(default=None)) -> dict:
    """Dependency: any authenticated user."""
    return _get_current_user(proman_token)


def require_admin(proman_token: Optional[str] = Cookie(default=None)) -> dict:
    """Dependency: admin role only."""
    user = _get_current_user(proman_token)
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required.")
    return user
