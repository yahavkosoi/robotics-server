from __future__ import annotations

import re
import secrets
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from .auth import require_admin
from .storage import DataStore, parse_iso, utc_now_iso

router = APIRouter(prefix="/api", tags=["uploads"])

GRADE_PATTERN = re.compile(r"^grade(7|8|9|10|11|12)$")
SAFE_NAME_PATTERN = re.compile(r"[^A-Za-z0-9._-]+")


class DownloadManyRequest(BaseModel):
    file_ids: list[str] = Field(default_factory=list)


class CopyStringRequest(BaseModel):
    file_ids: list[str] = Field(default_factory=list)


class DeleteManyRequest(BaseModel):
    file_ids: list[str] = Field(default_factory=list)


class CreateUploaderRequest(BaseModel):
    display_name: str
    grade: int
    extra_groups: list[str] = Field(default_factory=list)


async def _save_upload_file(upload_file: UploadFile, destination: Path, max_bytes: int) -> int:
    size = 0
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        with destination.open("wb") as out:
            while True:
                chunk = await upload_file.read(1024 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > max_bytes:
                    raise HTTPException(status_code=400, detail=f"File too large: {upload_file.filename}")
                out.write(chunk)
    except Exception:
        if destination.exists():
            destination.unlink(missing_ok=True)
        raise
    finally:
        await upload_file.close()
    return size


def _normalize_name(name: str) -> str:
    return name.strip().lower()


def _parse_grade(value: int | str | None) -> int | None:
    if value is None:
        return None
    try:
        grade = int(value)
    except (TypeError, ValueError):
        return None
    if 7 <= grade <= 12:
        return grade
    return None


def _resolve_or_create_uploader(
    store: DataStore,
    display_name: str,
    grade: int | None,
    extra_groups: list[str] | None = None,
) -> dict[str, Any]:
    normalized = _normalize_name(display_name)
    if not normalized:
        raise HTTPException(status_code=400, detail="Uploader name is required")

    payload = store.read_uploaders()
    uploaders = payload.setdefault("uploaders", [])

    uploader = next((u for u in uploaders if u.get("normalized_name") == normalized), None)
    if uploader:
        if uploader.get("grade") is None and grade is not None:
            uploader["grade"] = grade
            uploader["is_active_for_upload"] = True
            uploader["updated_at"] = utc_now_iso()
            store.write_uploaders(payload)
        if not uploader.get("is_active_for_upload", True):
            raise HTTPException(status_code=400, detail="Uploader name is disabled for new uploads")
        if uploader.get("grade") is None:
            raise HTTPException(status_code=400, detail="Uploader grade is missing; ask admin to set it")
        return uploader

    parsed_grade = _parse_grade(grade)
    if parsed_grade is None:
        raise HTTPException(status_code=400, detail="New uploader requires grade between 7 and 12")

    now = utc_now_iso()
    uploader = {
        "id": secrets.token_hex(8),
        "display_name": display_name.strip(),
        "normalized_name": normalized,
        "grade": parsed_grade,
        "extra_groups": sorted(set(extra_groups or [])),
        "is_active_for_upload": True,
        "created_at": now,
        "updated_at": now,
    }
    uploaders.append(uploader)
    store.write_uploaders(payload)
    return uploader


def _validate_upload_access(settings: dict[str, Any], upload_password: str | None) -> None:
    mode = settings.get("upload_access_mode", "open_lan")
    if mode == "open_lan":
        return
    if mode == "shared_password":
        expected = settings.get("upload_shared_password", "")
        if not expected:
            raise HTTPException(status_code=503, detail="Upload password mode is misconfigured")
        if upload_password != expected:
            raise HTTPException(status_code=401, detail="Invalid upload password")
        return
    raise HTTPException(status_code=403, detail="Upload mode does not allow public uploads")


def _allowed_extension(filename: str, settings: dict[str, Any]) -> bool:
    allowed = [ext.lower().strip() for ext in settings.get("allowed_extensions", []) if ext.strip()]
    if not allowed:
        return True
    ext = Path(filename or "").suffix.lower()
    return ext in allowed


def _safe_storage_name(filename: str) -> str:
    basename = Path(filename).name or "file"
    cleaned = SAFE_NAME_PATTERN.sub("_", basename)
    return f"{uuid4().hex}_{cleaned}"


def _build_admin_upload_view(store: DataStore) -> list[dict[str, Any]]:
    uploads_payload = store.read_uploads()
    files = uploads_payload.get("files", [])
    batches = uploads_payload.get("batches", [])

    files_by_batch: dict[str, list[dict[str, Any]]] = {}
    for file_entry in files:
        files_by_batch.setdefault(file_entry.get("upload_batch_id", ""), []).append(file_entry)

    output: list[dict[str, Any]] = []
    for batch in batches:
        batch_files = files_by_batch.get(batch.get("id", ""), [])
        batch_files_sorted = sorted(batch_files, key=lambda item: item.get("created_at", ""))
        rendered_files = []
        for file_entry in batch_files_sorted:
            if file_entry.get("is_deleted", False):
                continue
            stored_name = file_entry.get("stored_filename")
            rendered_files.append(
                {
                    "id": file_entry.get("id"),
                    "original_filename": file_entry.get("original_filename"),
                    "description": file_entry.get("description"),
                    "version": file_entry.get("version"),
                    "created_at": file_entry.get("created_at"),
                    "size_bytes": file_entry.get("size_bytes"),
                    "is_deleted": False,
                    "has_blob": bool(stored_name and (store.files_dir / stored_name).exists()),
                }
            )

        if not rendered_files:
            continue

        output.append(
            {
                "id": batch.get("id"),
                "uploader_name": batch.get("uploader_display_name_snapshot"),
                "created_at": batch.get("created_at"),
                "files": rendered_files,
            }
        )

    output.sort(key=lambda item: item.get("created_at", ""), reverse=True)
    return output


@router.get("/uploaders")
async def list_uploaders(request: Request) -> dict[str, Any]:
    store: DataStore = request.app.state.store
    payload = store.read_uploaders()
    uploaders = [u for u in payload.get("uploaders", []) if u.get("is_active_for_upload", True)]
    uploaders.sort(key=lambda item: item.get("display_name", "").lower())
    return {"uploaders": uploaders}


@router.post("/uploaders")
async def create_uploader(request: Request, body: CreateUploaderRequest) -> dict[str, Any]:
    store: DataStore = request.app.state.store
    uploader = _resolve_or_create_uploader(
        store=store,
        display_name=body.display_name,
        grade=body.grade,
        extra_groups=body.extra_groups,
    )
    return {"uploader": uploader}


@router.post("/upload-batches")
async def create_upload_batch(
    request: Request,
    uploader_name: str = Form(...),
    uploader_grade: int | None = Form(default=None),
    descriptions: list[str] = Form(...),
    versions: list[str] = Form(...),
    files: list[UploadFile] = File(...),
    upload_password: str | None = Form(default=None),
) -> dict[str, Any]:
    if not files:
        raise HTTPException(status_code=400, detail="At least one file is required")
    if len(descriptions) != len(files) or len(versions) != len(files):
        raise HTTPException(status_code=400, detail="Each file must have description and version")

    store: DataStore = request.app.state.store
    settings = store.read_settings()
    _validate_upload_access(settings, upload_password)

    max_bytes = int(settings.get("max_file_size_mb", 1024)) * 1024 * 1024
    uploader = _resolve_or_create_uploader(store=store, display_name=uploader_name, grade=uploader_grade)

    uploads_payload = store.read_uploads()
    batches = uploads_payload.setdefault("batches", [])
    files_payload = uploads_payload.setdefault("files", [])

    now = utc_now_iso()
    batch_id = secrets.token_hex(8)
    batch = {
        "id": batch_id,
        "uploader_profile_id": uploader["id"],
        "uploader_display_name_snapshot": uploader["display_name"],
        "created_at": now,
        "client_ip": request.client.host if request.client else None,
        "file_ids": [],
    }

    validated_rows = []
    for index, upload_file in enumerate(files):
        description = (descriptions[index] or "").strip()
        version = (versions[index] or "").strip()
        filename = upload_file.filename or "unnamed"

        if not description:
            raise HTTPException(status_code=400, detail=f"Description is required for {filename}")
        if not version:
            raise HTTPException(status_code=400, detail=f"Version is required for {filename}")
        if not _allowed_extension(filename, settings):
            raise HTTPException(status_code=400, detail=f"File extension not allowed: {filename}")

        validated_rows.append((upload_file, description, version, filename))

    saved_paths: list[Path] = []
    try:
        for upload_file, description, version, filename in validated_rows:
            stored_name = _safe_storage_name(filename)
            target = store.files_dir / stored_name
            size_bytes = await _save_upload_file(upload_file, target, max_bytes)
            saved_paths.append(target)

            file_id = secrets.token_hex(8)
            file_entry = {
                "id": file_id,
                "upload_batch_id": batch_id,
                "original_filename": Path(filename).name,
                "stored_filename": stored_name,
                "description": description,
                "version": version,
                "size_bytes": size_bytes,
                "mime_type": upload_file.content_type or "application/octet-stream",
                "created_at": now,
                "is_deleted": False,
                "deleted_at": None,
            }
            files_payload.append(file_entry)
            batch["file_ids"].append(file_id)
    except Exception:
        for saved_path in saved_paths:
            if saved_path.exists():
                saved_path.unlink(missing_ok=True)
        raise

    batches.append(batch)
    store.write_uploads(uploads_payload)

    return {"batch": batch}


@router.get("/admin/uploads")
async def admin_uploads(request: Request, _: dict[str, Any] = Depends(require_admin)) -> dict[str, Any]:
    store: DataStore = request.app.state.store
    return {"uploads": _build_admin_upload_view(store)}


@router.get("/admin/files/{file_id}/download")
async def admin_download_file(file_id: str, request: Request, _: dict[str, Any] = Depends(require_admin)) -> FileResponse:
    store: DataStore = request.app.state.store
    uploads_payload = store.read_uploads()
    file_entry = next((item for item in uploads_payload.get("files", []) if item.get("id") == file_id), None)
    if not file_entry or file_entry.get("is_deleted"):
        raise HTTPException(status_code=404, detail="File not found")

    path = store.files_dir / file_entry.get("stored_filename", "")
    if not path.exists():
        raise HTTPException(status_code=404, detail="File is no longer available")
    return FileResponse(path=path, filename=file_entry.get("original_filename") or "download")


@router.post("/admin/files/download-many")
async def admin_download_many(
    body: DownloadManyRequest,
    request: Request,
    _: dict[str, Any] = Depends(require_admin),
) -> dict[str, Any]:
    store: DataStore = request.app.state.store
    wanted = set(body.file_ids)
    uploads_payload = store.read_uploads()
    file_entries = [
        file_entry
        for file_entry in uploads_payload.get("files", [])
        if file_entry.get("id") in wanted and not file_entry.get("is_deleted", False)
    ]

    downloads = []
    for file_entry in file_entries:
        stored_name = file_entry.get("stored_filename")
        if not stored_name or not (store.files_dir / stored_name).exists():
            continue
        downloads.append(
            {
                "file_id": file_entry.get("id"),
                "filename": file_entry.get("original_filename"),
                "url": f"/api/admin/files/{file_entry.get('id')}/download",
            }
        )

    return {"downloads": downloads}


@router.post("/admin/files/delete-many")
async def admin_delete_many(
    body: DeleteManyRequest,
    request: Request,
    _: dict[str, Any] = Depends(require_admin),
) -> dict[str, int]:
    if not body.file_ids:
        raise HTTPException(status_code=400, detail="No files selected")

    store: DataStore = request.app.state.store
    uploads_payload = store.read_uploads()
    files = uploads_payload.get("files", [])
    wanted = set(body.file_ids)
    now = utc_now_iso()
    deleted_count = 0

    for file_entry in files:
        if file_entry.get("id") not in wanted:
            continue
        if file_entry.get("is_deleted", False):
            continue

        stored_name = file_entry.get("stored_filename")
        if stored_name:
            file_path = store.files_dir / stored_name
            if file_path.exists():
                try:
                    file_path.unlink()
                except OSError:
                    pass

        file_entry["is_deleted"] = True
        file_entry["deleted_at"] = now
        deleted_count += 1

    if deleted_count:
        store.write_uploads(uploads_payload)

    return {"deleted_count": deleted_count}


@router.post("/admin/copy-string")
async def admin_copy_string(
    body: CopyStringRequest,
    request: Request,
    admin: dict[str, Any] = Depends(require_admin),
) -> dict[str, Any]:
    if not body.file_ids:
        raise HTTPException(status_code=400, detail="No files selected")

    store: DataStore = request.app.state.store
    uploads_payload = store.read_uploads()
    files_by_id = {item.get("id"): item for item in uploads_payload.get("files", [])}
    batches_by_id = {item.get("id"): item for item in uploads_payload.get("batches", [])}

    selected_files: list[dict[str, Any]] = []
    uploader_names: set[str] = set()

    for file_id in body.file_ids:
        file_entry = files_by_id.get(file_id)
        if not file_entry or file_entry.get("is_deleted"):
            continue
        selected_files.append(file_entry)
        batch = batches_by_id.get(file_entry.get("upload_batch_id"))
        if batch and batch.get("uploader_display_name_snapshot"):
            uploader_names.add(batch["uploader_display_name_snapshot"])

    if not selected_files:
        raise HTTPException(status_code=404, detail="No available files found")

    filenames = ", ".join(file_entry.get("original_filename", "") for file_entry in selected_files)
    versions = ", ".join(file_entry.get("version", "") for file_entry in selected_files)
    uploader_segment = ", ".join(sorted(uploader_names, key=lambda item: item.lower()))
    date_str = datetime.now().strftime("%d-%m-%Y")

    text = f"{filenames} [{versions}] {{{admin['username']} - {uploader_segment}}} ({date_str})"
    return {"text": text}
