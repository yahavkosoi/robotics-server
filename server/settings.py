from __future__ import annotations

import secrets
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from .auth import hash_password, require_admin
from .storage import DataStore, utc_now_iso

router = APIRouter(prefix="/api/admin", tags=["settings"])


class SettingsUpdateRequest(BaseModel):
    retention_days: int | None = None
    max_file_size_mb: int | None = None
    allowed_extensions: list[str] | None = None
    upload_access_mode: str | None = None
    upload_shared_password: str | None = None
    backend_port: int | None = None
    web_port: int | None = None


class CreateAdminRequest(BaseModel):
    username: str
    password: str


class UpdateAdminRequest(BaseModel):
    password: str | None = None
    is_active: bool | None = None


class UpdateUploaderRequest(BaseModel):
    display_name: str | None = None
    grade: int | None = None
    is_active_for_upload: bool | None = None
    extra_groups: list[str] | None = None


def _normalize_extensions(values: list[str]) -> list[str]:
    normalized = []
    seen = set()
    for value in values:
        ext = value.strip().lower()
        if not ext:
            continue
        if not ext.startswith("."):
            ext = f".{ext}"
        if ext in seen:
            continue
        seen.add(ext)
        normalized.append(ext)
    return normalized


def _serialize_admin(admin: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": admin.get("id"),
        "username": admin.get("username"),
        "is_active": admin.get("is_active", True),
        "created_at": admin.get("created_at"),
        "last_login_at": admin.get("last_login_at"),
    }


@router.get("/settings")
async def get_settings(request: Request, _: dict[str, Any] = Depends(require_admin)) -> dict[str, Any]:
    store: DataStore = request.app.state.store
    return {"settings": store.read_settings()}


@router.put("/settings")
async def update_settings(
    request: Request,
    body: SettingsUpdateRequest,
    _: dict[str, Any] = Depends(require_admin),
) -> dict[str, Any]:
    store: DataStore = request.app.state.store
    settings = store.read_settings()

    if body.retention_days is not None:
        if body.retention_days < 1:
            raise HTTPException(status_code=400, detail="retention_days must be >= 1")
        settings["retention_days"] = body.retention_days

    if body.max_file_size_mb is not None:
        if body.max_file_size_mb < 1:
            raise HTTPException(status_code=400, detail="max_file_size_mb must be >= 1")
        settings["max_file_size_mb"] = body.max_file_size_mb

    if body.allowed_extensions is not None:
        settings["allowed_extensions"] = _normalize_extensions(body.allowed_extensions)

    if body.upload_access_mode is not None:
        if body.upload_access_mode not in {"open_lan", "shared_password", "disabled"}:
            raise HTTPException(status_code=400, detail="Invalid upload_access_mode")
        settings["upload_access_mode"] = body.upload_access_mode

    if body.upload_shared_password is not None:
        settings["upload_shared_password"] = body.upload_shared_password

    if body.backend_port is not None:
        if body.backend_port < 1 or body.backend_port > 65535:
            raise HTTPException(status_code=400, detail="backend_port must be between 1 and 65535")
        settings["backend_port"] = body.backend_port

    if body.web_port is not None:
        if body.web_port < 1 or body.web_port > 65535:
            raise HTTPException(status_code=400, detail="web_port must be between 1 and 65535")
        settings["web_port"] = body.web_port

    store.write_settings(settings)
    return {"settings": settings}


@router.get("/users")
async def list_admin_users(request: Request, _: dict[str, Any] = Depends(require_admin)) -> dict[str, Any]:
    store: DataStore = request.app.state.store
    admins = store.read_admins().get("admins", [])
    admins = sorted(admins, key=lambda item: item.get("username", "").lower())
    return {"admins": [_serialize_admin(admin) for admin in admins]}


@router.post("/users")
async def create_admin_user(
    request: Request,
    body: CreateAdminRequest,
    _: dict[str, Any] = Depends(require_admin),
) -> dict[str, Any]:
    username = body.username.strip()
    if not username:
        raise HTTPException(status_code=400, detail="username is required")
    if len(body.password) < 6:
        raise HTTPException(status_code=400, detail="password must be at least 6 characters")

    store: DataStore = request.app.state.store
    payload = store.read_admins()
    admins = payload.setdefault("admins", [])

    if any(admin.get("username", "").lower() == username.lower() for admin in admins):
        raise HTTPException(status_code=409, detail="Admin username already exists")

    admin = {
        "id": secrets.token_hex(8),
        "username": username,
        "password_hash": hash_password(body.password),
        "is_active": True,
        "created_at": utc_now_iso(),
        "last_login_at": None,
    }
    admins.append(admin)
    store.write_admins(payload)
    return {"admin": _serialize_admin(admin)}


@router.patch("/users/{admin_id}")
async def update_admin_user(
    admin_id: str,
    request: Request,
    body: UpdateAdminRequest,
    current_admin: dict[str, Any] = Depends(require_admin),
) -> dict[str, Any]:
    store: DataStore = request.app.state.store
    payload = store.read_admins()
    admins = payload.setdefault("admins", [])
    admin = next((item for item in admins if item.get("id") == admin_id), None)
    if not admin:
        raise HTTPException(status_code=404, detail="Admin not found")

    if body.password is not None:
        if len(body.password) < 6:
            raise HTTPException(status_code=400, detail="password must be at least 6 characters")
        admin["password_hash"] = hash_password(body.password)

    if body.is_active is not None:
        if admin.get("id") == current_admin.get("id") and body.is_active is False:
            raise HTTPException(status_code=400, detail="You cannot deactivate your own account")
        admin["is_active"] = body.is_active

    store.write_admins(payload)
    return {"admin": _serialize_admin(admin)}


@router.delete("/users/{admin_id}")
async def delete_admin_user(
    admin_id: str,
    request: Request,
    current_admin: dict[str, Any] = Depends(require_admin),
) -> dict[str, Any]:
    store: DataStore = request.app.state.store
    payload = store.read_admins()
    admins = payload.setdefault("admins", [])

    if current_admin.get("id") == admin_id:
        raise HTTPException(status_code=400, detail="You cannot delete your own account")

    admin = next((item for item in admins if item.get("id") == admin_id), None)
    if not admin:
        raise HTTPException(status_code=404, detail="Admin not found")

    remaining = [item for item in admins if item.get("id") != admin_id]
    active_remaining = [item for item in remaining if item.get("is_active", True)]
    if not active_remaining:
        raise HTTPException(status_code=400, detail="At least one active admin must remain")

    payload["admins"] = remaining
    store.write_admins(payload)
    return {"ok": True}


@router.get("/uploaders")
async def admin_list_uploaders(request: Request, _: dict[str, Any] = Depends(require_admin)) -> dict[str, Any]:
    store: DataStore = request.app.state.store
    uploaders = store.read_uploaders().get("uploaders", [])
    uploaders = sorted(uploaders, key=lambda item: item.get("display_name", "").lower())
    return {"uploaders": uploaders}


@router.patch("/uploaders/{uploader_id}")
async def admin_update_uploader(
    uploader_id: str,
    request: Request,
    body: UpdateUploaderRequest,
    _: dict[str, Any] = Depends(require_admin),
) -> dict[str, Any]:
    store: DataStore = request.app.state.store
    payload = store.read_uploaders()
    uploaders = payload.setdefault("uploaders", [])
    uploader = next((item for item in uploaders if item.get("id") == uploader_id), None)
    if not uploader:
        raise HTTPException(status_code=404, detail="Uploader not found")

    if body.display_name is not None:
        name = body.display_name.strip()
        if not name:
            raise HTTPException(status_code=400, detail="display_name cannot be empty")
        normalized = name.lower()
        duplicate = next(
            (item for item in uploaders if item.get("normalized_name") == normalized and item.get("id") != uploader_id),
            None,
        )
        if duplicate:
            raise HTTPException(status_code=409, detail="Uploader name already exists")
        uploader["display_name"] = name
        uploader["normalized_name"] = normalized

    if body.grade is not None:
        if body.grade < 7 or body.grade > 12:
            raise HTTPException(status_code=400, detail="grade must be between 7 and 12")
        uploader["grade"] = body.grade

    if body.extra_groups is not None:
        uploader["extra_groups"] = sorted(set(group.strip() for group in body.extra_groups if group.strip()))

    if body.is_active_for_upload is not None:
        uploader["is_active_for_upload"] = body.is_active_for_upload

    uploader["updated_at"] = utc_now_iso()
    store.write_uploaders(payload)
    return {"uploader": uploader}


@router.delete("/uploaders/{uploader_id}")
async def admin_disable_uploader(
    uploader_id: str,
    request: Request,
    _: dict[str, Any] = Depends(require_admin),
) -> dict[str, Any]:
    store: DataStore = request.app.state.store
    payload = store.read_uploaders()
    uploaders = payload.setdefault("uploaders", [])
    uploader = next((item for item in uploaders if item.get("id") == uploader_id), None)
    if not uploader:
        raise HTTPException(status_code=404, detail="Uploader not found")

    uploader["is_active_for_upload"] = False
    uploader["updated_at"] = utc_now_iso()
    store.write_uploaders(payload)
    return {"ok": True}
