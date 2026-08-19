"""Persists batch-upload classification results for 7 days, so a user can
navigate away and come back without re-uploading/re-classifying.

Two backends, same public function signatures so nothing else in the app
needs to change based on which is active:

- DB-backed (app/repositories/batch_repository.py) when `DATABASE_URL` is
  configured -- durable across redeploys, since it lives in a real database
  rather than the web service's own ephemeral disk.
- Local-JSON-file (the original implementation) otherwise -- zero-dependency
  fallback for local dev or a deployment with no database configured.

Caveat documented for operators: the local-JSON backend does NOT survive a
redeploy on hosts with ephemeral disk (e.g. Render) -- that's exactly the gap
the DB backend closes. See DATABASE_SETUP.md.
"""
from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.core.config import settings
from app.core.exceptions import InvalidRequestError
from app.db.base import db_configured
from app.ml.utils import to_json_safe

RETENTION_DAYS = 7
UPLOADS_DIR = settings.DATA_DIR / "uploads"

# Defense in depth: the API layer already validates upload_id against this
# same pattern (see UPLOAD_ID_PATTERN in api/v1/endpoints/sentiment.py), but
# this module must not trust its caller -- an upload_id built into a
# filesystem path with no validation of its own is a path-traversal
# vulnerability regardless of what already ran upstream.
_UPLOAD_ID_RE = re.compile(r"\A[0-9a-f]{32}\Z")


def _upload_path(upload_id: str) -> Path:
    if not _UPLOAD_ID_RE.match(upload_id):
        raise InvalidRequestError("Malformed upload id.")
    path = (UPLOADS_DIR / f"{upload_id}.json").resolve()
    if not path.is_relative_to(UPLOADS_DIR.resolve()):
        raise InvalidRequestError("Malformed upload id.")
    return path


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _is_expired(created_at_iso: str) -> bool:
    created_at = datetime.fromisoformat(created_at_iso)
    return datetime.now(timezone.utc) - created_at > timedelta(days=RETENTION_DAYS)


def _cleanup_expired_uploads_json() -> int:
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


def _save_upload_result_json(result: dict) -> str:
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    _cleanup_expired_uploads_json()

    upload_id = uuid.uuid4().hex
    payload = {"upload_id": upload_id, "created_at": _now_iso(), "result": to_json_safe(result)}
    with open(_upload_path(upload_id), "w", encoding="utf-8") as f:
        json.dump(payload, f)
    return upload_id


def _load_upload_result_json(upload_id: str) -> dict | None:
    path = _upload_path(upload_id)
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


def cleanup_expired_uploads() -> int:
    """Deletes uploads older than RETENTION_DAYS. Returns how many were removed."""
    if db_configured():
        from app.db.base import get_session_factory
        from app.repositories import batch_repository

        session = get_session_factory()()
        try:
            return batch_repository.cleanup_expired_jobs(session)
        finally:
            session.close()
    return _cleanup_expired_uploads_json()


def save_upload_result(result: dict) -> str:
    """Saves a classification result under a new upload_id, sweeps expired
    uploads opportunistically, and returns the new id."""
    if db_configured():
        try:
            from app.db.base import get_session_factory
            from app.repositories import batch_repository

            session = get_session_factory()()
            try:
                return batch_repository.save_batch_job(session, to_json_safe(result))
            finally:
                session.close()
        except Exception:
            # Best-effort: a DB write failure must never break the upload
            # response itself -- fall back to the local file so the user
            # still gets a working upload_id for this session.
            pass
    return _save_upload_result_json(result)


def load_upload_result(upload_id: str) -> dict | None:
    """Returns {"upload_id", "created_at", "expires_at", "result"} or None if
    not found or expired (an expired file/row is deleted on access)."""
    if db_configured():
        try:
            from app.db.base import get_session_factory
            from app.repositories import batch_repository

            session = get_session_factory()()
            try:
                found = batch_repository.get_batch_job(session, upload_id)
                if found is not None:
                    return found
            finally:
                session.close()
        except Exception:
            pass
    return _load_upload_result_json(upload_id)
