from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace

from server.uploads import (
    _build_admin_upload_view,
    _copy_filename_token,
    _copy_version_token,
    _effective_filename,
    admin_copy_string,
    admin_download_file,
    admin_download_many,
)


def _request_with_store(store: object) -> SimpleNamespace:
    return SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(store=store)))


class DummyStore:
    def __init__(self, files_dir: Path, uploads_payload: dict):
        self.files_dir = files_dir
        self._uploads_payload = uploads_payload

    def read_uploads(self) -> dict:
        return self._uploads_payload


def test_effective_filename_description_plus_extension() -> None:
    file_entry = {"description": "Arm Bracket", "original_filename": "part.stl"}
    assert _effective_filename(file_entry) == "Arm Bracket.stl"


def test_effective_filename_when_description_already_has_extension() -> None:
    file_entry = {"description": "Arm Bracket.stl", "original_filename": "part.stl"}
    assert _effective_filename(file_entry) == "Arm Bracket.stl"


def test_effective_filename_extension_match_is_case_insensitive() -> None:
    file_entry = {"description": "Arm Bracket.STL", "original_filename": "part.stl"}
    assert _effective_filename(file_entry) == "Arm Bracket.STL"


def test_effective_filename_falls_back_to_original_when_description_blank() -> None:
    file_entry = {"description": "   ", "original_filename": "part.stl"}
    assert _effective_filename(file_entry) == "part.stl"


def test_effective_filename_without_original_extension_uses_description() -> None:
    file_entry = {"description": "Arm Bracket", "original_filename": "part"}
    assert _effective_filename(file_entry) == "Arm Bracket"


def test_copy_filename_token_strips_extension() -> None:
    file_entry = {"description": "Arm Bracket", "original_filename": "part.stl"}
    assert _copy_filename_token(file_entry) == "Arm Bracket"


def test_copy_filename_token_falls_back_to_original_stem_when_description_blank() -> None:
    file_entry = {"description": " ", "original_filename": "part.stl"}
    assert _copy_filename_token(file_entry) == "part"


def test_copy_version_token_prefixes_with_uppercase_v() -> None:
    file_entry = {"version": "1"}
    assert _copy_version_token(file_entry) == "V1"


def test_copy_version_token_avoids_double_v_prefix() -> None:
    file_entry = {"version": "v2"}
    assert _copy_version_token(file_entry) == "V2"


def test_admin_uploads_view_uses_effective_filename_for_display(tmp_path: Path) -> None:
    blob_name = "stored_a.stl"
    (tmp_path / blob_name).write_bytes(b"abc")

    uploads_payload = {
        "batches": [
            {
                "id": "batch-1",
                "uploader_display_name_snapshot": "Tom",
                "created_at": "2026-02-13T13:08:21.945500+00:00",
            }
        ],
        "files": [
            {
                "id": "file-a",
                "upload_batch_id": "batch-1",
                "original_filename": "source.stl",
                "stored_filename": blob_name,
                "description": "Arm Bracket",
                "version": "1",
                "created_at": "2026-02-13T13:08:21.945500+00:00",
                "size_bytes": 3,
                "is_deleted": False,
            },
            {
                "id": "file-b",
                "upload_batch_id": "batch-1",
                "original_filename": "fallback.json",
                "stored_filename": "missing.json",
                "description": "  ",
                "version": "2",
                "created_at": "2026-02-13T13:08:22.945500+00:00",
                "size_bytes": 4,
                "is_deleted": False,
            },
        ],
    }
    store = DummyStore(files_dir=tmp_path, uploads_payload=uploads_payload)

    rows = _build_admin_upload_view(store)
    names = [file_row["original_filename"] for file_row in rows[0]["files"]]
    assert names == ["Arm Bracket.stl", "fallback.json"]


def test_copy_string_uses_effective_filenames_in_selected_order(tmp_path: Path) -> None:
    uploads_payload = {
        "batches": [{"id": "batch-1", "uploader_display_name_snapshot": "Tom"}],
        "files": [
            {
                "id": "f1",
                "upload_batch_id": "batch-1",
                "original_filename": "first.stl",
                "description": "Desc One",
                "version": "1",
                "is_deleted": False,
            },
            {
                "id": "f2",
                "upload_batch_id": "batch-1",
                "original_filename": "second.json",
                "description": "Desc Two.json",
                "version": "2",
                "is_deleted": False,
            },
        ],
    }
    store = DummyStore(files_dir=tmp_path, uploads_payload=uploads_payload)
    request = _request_with_store(store)
    body = SimpleNamespace(file_ids=["f1", "f2"])
    admin = {"username": "Admin"}

    result = asyncio.run(admin_copy_string(body=body, request=request, admin=admin))
    assert result["text"].startswith("Desc One, Desc Two [V1, V2] {Admin - Tom} (")


def test_download_many_uses_effective_filename(tmp_path: Path) -> None:
    stored = "blob.stl"
    (tmp_path / stored).write_bytes(b"abc")
    uploads_payload = {
        "batches": [],
        "files": [
            {
                "id": "f1",
                "original_filename": "source.stl",
                "description": "Arm Bracket",
                "stored_filename": stored,
                "is_deleted": False,
            }
        ],
    }
    store = DummyStore(files_dir=tmp_path, uploads_payload=uploads_payload)
    request = _request_with_store(store)
    body = SimpleNamespace(file_ids=["f1"])

    result = asyncio.run(admin_download_many(body=body, request=request, _={}))
    assert result["downloads"][0]["filename"] == "Arm Bracket.stl"


def test_single_download_uses_effective_filename(tmp_path: Path) -> None:
    stored = "blob.stl"
    (tmp_path / stored).write_bytes(b"abc")
    uploads_payload = {
        "batches": [],
        "files": [
            {
                "id": "f1",
                "original_filename": "source.stl",
                "description": "Arm Bracket",
                "stored_filename": stored,
                "is_deleted": False,
            }
        ],
    }
    store = DummyStore(files_dir=tmp_path, uploads_payload=uploads_payload)
    request = _request_with_store(store)

    response = asyncio.run(admin_download_file(file_id="f1", request=request, _={}))
    assert response.filename == "Arm Bracket.stl"
