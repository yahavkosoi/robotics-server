from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .storage import DataStore, parse_iso, utc_now_iso


async def run_retention_cleanup_once(store: DataStore) -> None:
    settings = store.read_settings()
    retention_days = int(settings.get("retention_days", 30))
    if retention_days <= 0:
        return

    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    uploads_payload = store.read_uploads()
    files = uploads_payload.setdefault("files", [])
    changed = False

    for file_entry in files:
        if file_entry.get("is_deleted"):
            continue
        created_at = parse_iso(file_entry.get("created_at"))
        if not created_at or created_at > cutoff:
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
        file_entry["deleted_at"] = utc_now_iso()
        changed = True

    if changed:
        store.write_uploads(uploads_payload)


async def cleanup_daemon(store: DataStore, shutdown_event: asyncio.Event) -> None:
    await run_retention_cleanup_once(store)
    while not shutdown_event.is_set():
        try:
            await asyncio.wait_for(shutdown_event.wait(), timeout=24 * 60 * 60)
        except asyncio.TimeoutError:
            await run_retention_cleanup_once(store)
