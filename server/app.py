from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

from .auth import (
    SESSION_COOKIE_NAME,
    authenticate_admin,
    create_session,
    delete_session,
    ensure_default_admin,
    get_current_admin_from_request,
)
from .cleanup import cleanup_daemon
from .migrate_legacy import router as migrate_router
from .settings import router as settings_router
from .storage import BASE_DIR, DataStore
from .uploads import router as uploads_router


class LoginRequest(BaseModel):
    username: str
    password: str


app = FastAPI(title="Robotics Lab File Share", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(uploads_router)
app.include_router(settings_router)
app.include_router(migrate_router)


@app.on_event("startup")
async def startup_event() -> None:
    store = DataStore()
    store.initialize()
    ensure_default_admin(store)

    app.state.store = store
    app.state.shutdown_event = asyncio.Event()
    app.state.cleanup_task = asyncio.create_task(cleanup_daemon(store, app.state.shutdown_event))


@app.on_event("shutdown")
async def shutdown_event() -> None:
    shutdown = getattr(app.state, "shutdown_event", None)
    task = getattr(app.state, "cleanup_task", None)
    if shutdown:
        shutdown.set()
    if task:
        await task


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/admin/login")
async def admin_login(body: LoginRequest, response: Response, request: Request) -> dict[str, Any]:
    store: DataStore = request.app.state.store
    admin = authenticate_admin(store, body.username, body.password)
    if not admin:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    session_token = create_session(store, admin)
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=session_token,
        httponly=True,
        secure=False,
        samesite="lax",
        max_age=12 * 60 * 60,
        path="/",
    )
    return {
        "admin": {
            "id": admin.get("id"),
            "username": admin.get("username"),
            "is_active": admin.get("is_active", True),
        }
    }


@app.post("/api/admin/logout")
async def admin_logout(response: Response, request: Request) -> dict[str, bool]:
    store: DataStore = request.app.state.store
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if token:
        delete_session(store, token)
    response.delete_cookie(SESSION_COOKIE_NAME, path="/")
    return {"ok": True}


@app.get("/api/admin/me")
async def admin_me(request: Request) -> dict[str, Any]:
    admin = get_current_admin_from_request(request)
    return {
        "admin": {
            "id": admin.get("id"),
            "username": admin.get("username"),
            "is_active": admin.get("is_active", True),
        }
    }


WEB_DIST = BASE_DIR / "web" / "dist"


if WEB_DIST.exists():

    @app.get("/")
    async def serve_index() -> FileResponse:
        return FileResponse(WEB_DIST / "index.html")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str) -> FileResponse:
        requested = WEB_DIST / full_path
        if requested.exists() and requested.is_file():
            return FileResponse(requested)
        return FileResponse(WEB_DIST / "index.html")
else:

    @app.get("/")
    async def root_message() -> dict[str, str]:
        return {
            "message": "Backend is running. Build frontend in /web and serve /web/dist to use the UI.",
        }
