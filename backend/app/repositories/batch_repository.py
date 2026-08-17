"""Data-access layer for batch_upload_jobs -- the DB-backed replacement for
upload_store.py's local-JSON records. Functions here return the exact same
shapes upload_store.py already did, so it can delegate to this module
transparently when DATABASE_URL is configured (see upload_store.py)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.db.models import BatchUploadJob

RETENTION_DAYS = 7


def save_batch_job(session: Session, result: dict[str, Any]) -> str:
    now = datetime.now(timezone.utc)
    row = BatchUploadJob(
        filename=result.get("filename", "unknown"),
        model_name=result.get("model_name", "unknown"),
        text_column_used=result.get("text_column_used", ""),
        rows_processed=result.get("rows_processed", 0),
        n_positive=result.get("n_positive", 0),
        n_negative=result.get("n_negative", 0),
        result_json=result,
        created_at=now,
        expires_at=now + timedelta(days=RETENTION_DAYS),
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return row.id


def get_batch_job(session: Session, job_id: str) -> dict[str, Any] | None:
    row = session.get(BatchUploadJob, job_id)
    if row is None:
        return None
    now = datetime.now(timezone.utc)
    expires_at = row.expires_at if row.expires_at.tzinfo else row.expires_at.replace(tzinfo=timezone.utc)
    if now > expires_at:
        session.delete(row)
        session.commit()
        return None
    return {
        "upload_id": row.id,
        "created_at": row.created_at.isoformat(),
        "expires_at": row.expires_at.isoformat(),
        "result": row.result_json,
    }


def cleanup_expired_jobs(session: Session) -> int:
    now = datetime.now(timezone.utc)
    result = session.execute(delete(BatchUploadJob).where(BatchUploadJob.expires_at < now))
    session.commit()
    return result.rowcount or 0
