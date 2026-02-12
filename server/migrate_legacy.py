from __future__ import annotations

import json
import secrets
from collections import defaultdict
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from .auth import require_admin
from .storage import BASE_DIR, DataStore, atomic_write_json, parse_iso, utc_now_iso

router = APIRouter(prefix="/api/admin/migrate", tags=["migration"])

GRADE_GROUPS = {f"grade{num}" for num in range(7, 13)}


class LegacyImportRequest(BaseModel):
    users_path: str | None = None
    groups_path: str | None = None


def _load_json_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {path}")
    try:
        with path.open("r", encoding="utf-8") as f:
            loaded = json.load(f)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid JSON in {path}: {exc}") from exc
    if not isinstance(loaded, dict):
        raise HTTPException(status_code=400, detail=f"Expected object JSON in {path}")
    return loaded


@router.post("/import-legacy")
async def import_legacy(
    request: Request,
    body: LegacyImportRequest,
    _: dict[str, Any] = Depends(require_admin),
) -> dict[str, Any]:
    store: DataStore = request.app.state.store

    users_path = Path(body.users_path) if body.users_path else BASE_DIR / "users.json"
    groups_path = Path(body.groups_path) if body.groups_path else BASE_DIR / "groups.json"

    users_src = _load_json_file(users_path)
    groups_src = _load_json_file(groups_path)

    grouped: dict[str, list[tuple[str, dict[str, Any]]]] = defaultdict(list)
    skipped_admins: list[str] = []

    for username, payload in users_src.items():
        if not isinstance(payload, dict):
            continue
        if payload.get("is_admin") is True:
            skipped_admins.append(username)
            continue
        grouped[username.lower()].append((username, payload))

    merged: list[dict[str, Any]] = []
    merged_duplicates: list[dict[str, Any]] = []

    for normalized, records in grouped.items():
        winner_name, winner_payload = max(
            records,
            key=lambda item: (parse_iso(item[1].get("created_at")) or parse_iso("1970-01-01T00:00:00+00:00")),
        )
        merged.append({"normalized": normalized, "name": winner_name, "payload": winner_payload})
        if len(records) > 1:
            merged_duplicates.append(
                {
                    "normalized_name": normalized,
                    "merged_from": [name for name, _ in records],
                    "kept": winner_name,
                }
            )

    uploaders_payload = store.read_uploaders()
    uploaders = uploaders_payload.setdefault("uploaders", [])
    existing_by_normalized = {u.get("normalized_name"): u for u in uploaders}

    imported: list[str] = []
    skipped_no_grade: list[str] = []
    pending_multi_grade: list[str] = []

    for item in sorted(merged, key=lambda row: row["normalized"]):
        username = item["name"]
        payload = item["payload"]

        groups = payload.get("groups") if isinstance(payload.get("groups"), list) else []
        grade_groups = sorted({group for group in groups if group in GRADE_GROUPS})
        extra_groups = sorted({group for group in groups if group not in GRADE_GROUPS and group != "admin"})

        grade: int | None
        active: bool
        if len(grade_groups) == 0:
            skipped_no_grade.append(username)
            continue
        if len(grade_groups) > 1:
            grade = None
            active = False
            pending_multi_grade.append(username)
        else:
            grade = int(grade_groups[0].replace("grade", ""))
            active = True

        normalized = item["normalized"]
        existing = existing_by_normalized.get(normalized)

        now = utc_now_iso()
        if existing:
            existing["display_name"] = username
            if grade is not None:
                existing["grade"] = grade
            elif existing.get("grade") is None:
                existing["grade"] = None
            existing_extra = set(existing.get("extra_groups", []))
            existing["extra_groups"] = sorted(existing_extra.union(extra_groups))
            existing["is_active_for_upload"] = active if grade is None else True
            existing["updated_at"] = now
        else:
            uploader = {
                "id": secrets.token_hex(8),
                "display_name": username,
                "normalized_name": normalized,
                "grade": grade,
                "extra_groups": extra_groups,
                "is_active_for_upload": active,
                "created_at": now,
                "updated_at": now,
            }
            uploaders.append(uploader)
            existing_by_normalized[normalized] = uploader

        imported.append(username)

    store.write_uploaders(uploaders_payload)
    store.write_groups({"groups": groups_src})

    report = {
        "timestamp": utc_now_iso(),
        "source": {"users_path": str(users_path), "groups_path": str(groups_path)},
        "counts": {
            "total_source_users": len(users_src),
            "skipped_admins": len(skipped_admins),
            "post_admin_users": len(users_src) - len(skipped_admins),
            "merged_collision_groups": len(merged_duplicates),
            "post_merge_candidates": len(merged),
            "skipped_no_grade": len(skipped_no_grade),
            "pending_multi_grade": len(pending_multi_grade),
            "imported_uploaders": len(imported),
        },
        "details": {
            "merged_duplicates": merged_duplicates,
            "skipped_no_grade": sorted(skipped_no_grade),
            "pending_multi_grade": sorted(pending_multi_grade),
            "skipped_admins": sorted(skipped_admins),
        },
    }

    report_name = f"legacy-import-{report['timestamp'].replace(':', '-').replace('.', '-')}.json"
    report_path = store.reports_dir / report_name
    atomic_write_json(report_path, report)

    return {"report": report, "report_path": str(report_path)}
