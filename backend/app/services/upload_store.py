"""Persists batch-upload classification results to disk for 7 days, so a
user can navigate away and come back without re-uploading/re-classifying.

Simple JSON-file store (`data/uploads/{upload_id}.json`) -- no database
dependency. Expired files are swept lazily (on the next save or read), not
via a background scheduler, since this project has no task-queue infra.

Caveat documented for operators: on hosts with ephemeral disk between
deploys (e.g. Render), saved uploads do NOT survive a redeploy, only normal
process/idle-restart cycles. This is a local-first convenience feature, not
a durable record store.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.core.config import settings
from app.ml.utils import to_json_safe

RETENTION_DAYS = 7
UPLOADS_DIR = settings.DATA_DIR / "uploads"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _is_expired(created_at_iso: str) -> bool:
    created_at = datetime.fromisoformat(created_at_iso)
    return datetime.now(timezone.utc) - created_at > timedelta(days=RETENTION_DAYS)


def cleanup_expired_uploads() -> int:
    """Deletes uploads older than RETENTION_DAYS. Returns how many were removed."""
    if not UPLOADS_DIR.is_dir():
        return 0
    removed = 0
    for path in UPLOADS_DIR.glob("*.json"):
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            if _is_expired(data["created_at"]):
                path.unlink()
                removed += 1
        except Exception:
            continue
    return removed


def save_upload_result(result: dict) -> str:
    """Saves a classification result under a new upload_id, sweeps expired
    uploads opportunistically, and returns the new id."""
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    cleanup_expired_uploads()

    upload_id = uuid.uuid4().hex
    payload = {"upload_id": upload_id, "created_at": _now_iso(), "result": to_json_safe(result)}
    with open(UPLOADS_DIR / f"{upload_id}.json", "w", encoding="utf-8") as f:
        json.dump(payload, f)
    return upload_id


def load_upload_result(upload_id: str) -> dict | None:
    """Returns {"upload_id", "created_at", "expires_at", "result"} or None if
    not found or expired (an expired file is deleted on access)."""
    path = UPLOADS_DIR / f"{upload_id}.json"
    if not path.is_file():
        return None
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if _is_expired(data["created_at"]):
        path.unlink(missing_ok=True)
        return None
    created_at = datetime.fromisoformat(data["created_at"])
    return {
        "upload_id": data["upload_id"],
        "created_at": data["created_at"],
        "expires_at": (created_at + timedelta(days=RETENTION_DAYS)).isoformat(),
        "result": data["result"],
    }
