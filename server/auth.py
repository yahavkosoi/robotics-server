from __future__ import annotations

import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import Depends, HTTPException, Request, status

from .storage import DataStore, parse_iso, utc_now_iso

SESSION_COOKIE_NAME = "lab_session"
SESSION_TTL_HOURS = 12
DEFAULT_ADMIN_USERNAME = "Admin"
DEFAULT_ADMIN_PASSWORD_ENV = "ROBOTICS_DEFAULT_ADMIN_PASSWORD"


def _hash_pbkdf2(password: str, salt: bytes, iterations: int = 390000) -> str:
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return f"pbkdf2_sha256${iterations}${salt.hex()}${digest.hex()}"


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    return _hash_pbkdf2(password, salt)


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, iterations, salt_hex, digest_hex = encoded.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        expected = _hash_pbkdf2(password, bytes.fromhex(salt_hex), int(iterations))
        return hmac.compare_digest(expected, encoded)
    except Exception:
        return False


def _find_admin_by_username(admins: list[dict[str, Any]], username: str) -> dict[str, Any] | None:
    target = username.strip().lower()
    for admin in admins:
        if admin.get("username", "").lower() == target:
            return admin
    return None


def _get_default_admin_password() -> str:
    password = os.getenv(DEFAULT_ADMIN_PASSWORD_ENV)
    if password:
        return password
    raise RuntimeError(
        f"{DEFAULT_ADMIN_PASSWORD_ENV} is required when bootstrapping the default admin. "
        "Set it before first run, or pre-create admins.json."
    )


def ensure_default_admin(store: DataStore) -> None:
    payload = store.read_admins()
    admins = payload.setdefault("admins", [])
    if _find_admin_by_username(admins, DEFAULT_ADMIN_USERNAME):
        return
    bootstrap_password = _get_default_admin_password()
    now = utc_now_iso()
    admins.append(
        {
            "id": secrets.token_hex(8),
            "username": DEFAULT_ADMIN_USERNAME,
            "password_hash": hash_password(bootstrap_password),
            "is_active": True,
            "created_at": now,
            "last_login_at": None,
        }
    )
    store.write_admins(payload)


def authenticate_admin(store: DataStore, username: str, password: str) -> dict[str, Any] | None:
    payload = store.read_admins()
    admin = _find_admin_by_username(payload.get("admins", []), username)
    if not admin:
        return None
    if not admin.get("is_active", True):
        return None
    if not verify_password(password, admin.get("password_hash", "")):
        return None
    admin["last_login_at"] = utc_now_iso()
    store.write_admins(payload)
    return admin


def create_session(store: DataStore, admin: dict[str, Any]) -> str:
    sessions_payload = store.read_sessions()
    sessions = sessions_payload.setdefault("sessions", [])
    now = datetime.now(timezone.utc)
    token = secrets.token_urlsafe(32)
    sessions.append(
        {
            "id": token,
            "admin_id": admin["id"],
            "username": admin["username"],
            "created_at": now.isoformat(),
            "expires_at": (now + timedelta(hours=SESSION_TTL_HOURS)).isoformat(),
        }
    )
    store.write_sessions(sessions_payload)
    return token


def delete_session(store: DataStore, session_id: str) -> None:
    sessions_payload = store.read_sessions()
    sessions_payload["sessions"] = [
        session for session in sessions_payload.get("sessions", []) if session.get("id") != session_id
    ]
    store.write_sessions(sessions_payload)


def cleanup_expired_sessions(store: DataStore) -> None:
    now = datetime.now(timezone.utc)
    sessions_payload = store.read_sessions()
    sessions_payload["sessions"] = [
        session
        for session in sessions_payload.get("sessions", [])
        if (parse_iso(session.get("expires_at")) or now) > now
    ]
    store.write_sessions(sessions_payload)


def get_current_admin_from_request(request: Request) -> dict[str, Any]:
    store: DataStore = request.app.state.store
    cleanup_expired_sessions(store)

    token = request.cookies.get(SESSION_COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Admin login required")

    sessions_payload = store.read_sessions()
    session = next((s for s in sessions_payload.get("sessions", []) if s.get("id") == token), None)
    if not session:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired")

    if (parse_iso(session.get("expires_at")) or datetime.now(timezone.utc)) <= datetime.now(timezone.utc):
        delete_session(store, token)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired")

    admins_payload = store.read_admins()
    admin = next((a for a in admins_payload.get("admins", []) if a.get("id") == session.get("admin_id")), None)
    if not admin or not admin.get("is_active", True):
        delete_session(store, token)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Admin unavailable")
    return admin


def require_admin(admin: dict[str, Any] = Depends(get_current_admin_from_request)) -> dict[str, Any]:
    return admin
