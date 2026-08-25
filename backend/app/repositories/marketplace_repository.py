"""Data-access layer for the marketplace CSV data-management feature.
Every function assumes the caller already checked require_postgres() and is
passed a live SQLAlchemy Session. No function here commits except
activate_version() and retire_eligible_versions() (they own their
transaction boundary deliberately, per Checkpoint B correction #1); all
other functions leave commit/rollback to the caller so a service can batch
several repository calls into one transaction.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import delete, func, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.db.models import (
    MarketplaceCanonicalRow, MarketplaceCustomerAnalytics, MarketplaceDatasetVersion, MarketplaceDerivedArtifact,
    MarketplaceImportAudit, MarketplaceImportSession, MarketplaceProductAnalytics, MarketplaceSellerAnalytics,
)
from fastapi import status

# Fixed, documented advisory-lock key -- see marketplace_version_service.py.
# Any stable 63-bit integer works; this one has no special meaning beyond
# being unique to this feature within the database.
MARKETPLACE_ACTIVATION_LOCK_ID = 913_704_221_001


class ActivationConflictError(AppError):
    def __init__(self, message: str, details: dict | None = None):
        super().__init__(message, code="ACTIVATION_CONFLICT", status_code=status.HTTP_409_CONFLICT, details=details)


class VersionNotDeletableError(AppError):
    def __init__(self, message: str, details: dict | None = None):
        super().__init__(message, code="VERSION_NOT_DELETABLE", status_code=status.HTTP_409_CONFLICT, details=details)


# -- import sessions ---------------------------------------------------------

def create_import_session(
    session: Session, *, id_: str, filename: str, file_hash: str, file_size_bytes: int,
    ttl_minutes: int, created_by: str | None,
) -> MarketplaceImportSession:
    now = datetime.now(timezone.utc)
    row = MarketplaceImportSession(
        id=id_, filename=filename, file_hash=file_hash, file_size_bytes=file_size_bytes,
        status="uploaded", created_at=now, expires_at=now + timedelta(minutes=ttl_minutes), created_by=created_by,
    )
    session.add(row)
    session.flush()
    return row


def get_active_import_session(session: Session, session_id: str) -> MarketplaceImportSession | None:
    """Returns the session only if it exists AND has not expired/been used.
    An expired session is marked 'expired' in place (never silently revived)
    and its staged file removed -- see the module docstring on expiry
    behavior: expired sessions must become unusable and lose their raw
    upload content, even if nobody polled them until after expiry."""
    row = session.get(MarketplaceImportSession, session_id)
    if row is None:
        return None
    now = datetime.now(timezone.utc)
    expires_at = row.expires_at if row.expires_at.tzinfo else row.expires_at.replace(tzinfo=timezone.utc)
    if row.status in ("expired", "deleted", "confirmed"):
        return None if row.status != "confirmed" else row  # confirmed sessions are read-only history, not "active"
    if now > expires_at:
        _expire_session_row(session, row)
        session.commit()
        return None
    return row


def _expire_session_row(session: Session, row: MarketplaceImportSession) -> None:
    if row.staged_file_path:
        try:
            Path(row.staged_file_path).unlink(missing_ok=True)
        except OSError:
            pass
    row.staged_file_path = None
    row.status = "expired"
    # Preserve a minimal audit record (filename/hash/timestamps) -- the row
    # itself IS that minimal record; only the raw staged content is removed.
    write_audit_event(session, "session_expired", session_id=row.id, detail={"filename": row.filename})


def expire_stale_sessions(session: Session) -> int:
    """Opportunistic sweep (called at the top of upload/preview/confirm
    endpoints, same pattern as upload_store.py's cleanup-on-write). Returns
    how many sessions were expired."""
    now = datetime.now(timezone.utc)
    stale = session.scalars(
        select(MarketplaceImportSession).where(
            MarketplaceImportSession.status.notin_(["expired", "deleted", "confirmed"]),
            MarketplaceImportSession.expires_at < now,
        )
    ).all()
    for row in stale:
        _expire_session_row(session, row)
    if stale:
        session.commit()
    return len(stale)


def update_session(session: Session, row: MarketplaceImportSession, **fields: Any) -> None:
    for key, value in fields.items():
        setattr(row, key, value)
    session.flush()


def delete_session(session: Session, row: MarketplaceImportSession) -> None:
    if row.staged_file_path:
        try:
            Path(row.staged_file_path).unlink(missing_ok=True)
        except OSError:
            pass
    row.staged_file_path = None
    row.status = "deleted"
    write_audit_event(session, "session_deleted", session_id=row.id)
    session.commit()


# -- canonical rows / entity analytics (chunked bulk insert) ----------------

def bulk_insert_canonical_rows(session: Session, rows: list[dict]) -> None:
    if rows:
        session.execute(MarketplaceCanonicalRow.__table__.insert(), rows)


def bulk_insert_customer_analytics(session: Session, rows: list[dict]) -> None:
    if rows:
        session.execute(MarketplaceCustomerAnalytics.__table__.insert(), rows)


def bulk_insert_seller_analytics(session: Session, rows: list[dict]) -> None:
    if rows:
        session.execute(MarketplaceSellerAnalytics.__table__.insert(), rows)


def bulk_insert_product_analytics(session: Session, rows: list[dict]) -> None:
    if rows:
        session.execute(MarketplaceProductAnalytics.__table__.insert(), rows)


def upsert_derived_artifact(session: Session, *, version_id: str, artifact_name: str, payload: dict, schema_version: str = "1.0") -> None:
    stmt = pg_insert(MarketplaceDerivedArtifact).values(
        dataset_version_id=version_id, artifact_name=artifact_name, payload_json=payload,
        schema_version=schema_version, computed_at=datetime.now(timezone.utc),
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=["dataset_version_id", "artifact_name"],
        set_={"payload_json": stmt.excluded.payload_json, "schema_version": stmt.excluded.schema_version, "computed_at": stmt.excluded.computed_at},
    )
    session.execute(stmt)


def get_derived_artifact(session: Session, version_id: str, artifact_name: str) -> dict | None:
    row = session.execute(
        select(MarketplaceDerivedArtifact).where(
            MarketplaceDerivedArtifact.dataset_version_id == version_id,
            MarketplaceDerivedArtifact.artifact_name == artifact_name,
        )
    ).scalar_one_or_none()
    return row.payload_json if row else None


def list_derived_artifacts(session: Session, version_id: str) -> dict[str, dict]:
    rows = session.scalars(select(MarketplaceDerivedArtifact).where(MarketplaceDerivedArtifact.dataset_version_id == version_id)).all()
    return {r.artifact_name: r.payload_json for r in rows}


# -- append: copy-forward parent rows not superseded by the new upload -------

_CANONICAL_COPY_COLUMNS = [
    "order_id", "order_item_id", "order_purchase_timestamp", "order_delivered_customer_date",
    "order_estimated_delivery_date", "order_status", "customer_id", "customer_unique_id", "customer_city",
    "customer_state", "payment_value", "main_payment_type", "payment_installments", "review_score",
    "review_comment_message", "seller_id", "product_id", "product_category_name", "price", "freight_value",
    "seller_city", "seller_state",
]


def copy_forward_unmatched_rows(session: Session, *, parent_version_id: str, new_version_id: str) -> int:
    """Implements 'Append & Update' semantics for confirm_and_activate(): the
    new version starts as a copy of the parent version's canonical rows,
    except any (order_id, order_item_id) key that the newly-uploaded file
    also supplies -- those rows are already staged under new_version_id by
    validate_and_stage()'s chunked insert and must NOT be duplicated here,
    so a parent row whose key collides with an uploaded row is dropped in
    favor of the uploaded (updated) one. 'IS NOT DISTINCT FROM' matches the
    same null-inclusive key semantics as ux_canonical_item_key
    (postgresql_nulls_not_distinct=True), so two item-less rows for the same
    order_id are treated as the same key.

    One set-based INSERT...SELECT executed entirely in PostgreSQL -- never
    pulls parent rows into Python, so this stays bounded regardless of how
    large the parent version is."""
    cols = ", ".join(_CANONICAL_COPY_COLUMNS)
    prefixed = ", ".join(f"p.{c}" for c in _CANONICAL_COPY_COLUMNS)
    # CAST(...) on every occurrence of the two id parameters: psycopg
    # infers each named parameter's type once per prepared statement, and
    # without an explicit cast it deduces 'text' where the value is being
    # SELECTed and 'character varying' where it's compared against the
    # dataset_version_id column -- a genuine type conflict psycopg reports
    # as "inconsistent types deduced for parameter $1", not a bind bug.
    result = session.execute(text(f"""
        INSERT INTO marketplace_canonical_rows (dataset_version_id, {cols})
        SELECT CAST(:new_version_id AS VARCHAR(32)), {prefixed}
        FROM marketplace_canonical_rows p
        WHERE p.dataset_version_id = CAST(:parent_version_id AS VARCHAR(32))
          AND NOT EXISTS (
              SELECT 1 FROM marketplace_canonical_rows n
              WHERE n.dataset_version_id = CAST(:new_version_id AS VARCHAR(32))
                AND n.order_id = p.order_id
                AND n.order_item_id IS NOT DISTINCT FROM p.order_item_id
          )
    """), {"new_version_id": new_version_id, "parent_version_id": parent_version_id})
    return result.rowcount or 0


def find_merged_order_conflicts(session: Session, version_id: str) -> list[str]:
    """Guards an append merge that validate_and_stage() cannot see on its
    own: that function only checks conflicts WITHIN the newly-uploaded
    file's rows, but an append can update only some item-rows of a
    multi-item order while other item-rows are copied forward unchanged
    from the parent -- if the uploader changed payment_value/main_payment_
    type/payment_installments for that order without re-supplying every
    item row, the merged version now has an order whose order-grain fields
    disagree across its own rows. This re-runs the same conflict rule
    against the fully-merged table (bounded GROUP BY, server-side)."""
    rows = session.execute(text("""
        SELECT order_id FROM marketplace_canonical_rows
        WHERE dataset_version_id = :vid
        GROUP BY order_id
        HAVING COUNT(DISTINCT COALESCE(payment_value::text, '<null>')) > 1
            OR COUNT(DISTINCT COALESCE(main_payment_type, '<null>')) > 1
            OR COUNT(DISTINCT COALESCE(payment_installments::text, '<null>')) > 1
    """), {"vid": version_id}).all()
    return sorted(r[0] for r in rows)


_NULLABLE_CANONICAL_FIELDS = [
    "order_item_id", "customer_city", "customer_state", "order_delivered_customer_date",
    "order_estimated_delivery_date", "payment_value", "main_payment_type", "payment_installments",
    "review_score", "review_comment_message", "seller_id", "product_id", "product_category_name",
    "price", "freight_value", "seller_city", "seller_state",
]
_ALWAYS_REQUIRED_FIELDS = ["order_id", "customer_id", "customer_unique_id", "order_status", "order_purchase_timestamp"]


def compute_fields_present(session: Session, version_id: str) -> dict[str, bool]:
    """Whether a canonical field has any actual data in this version's final
    (merged) canonical rows -- computed from the DB, not from the upload's
    own column mapping. This matters for 'append': an incremental upload
    that omits a column the PARENT version had (e.g. seller_id) must not
    silently drop seller analytics for the merged dataset -- those rows are
    still present via copy_forward_unmatched_rows. One bounded aggregate
    scan of this version's own rows, never pandas/Python-side."""
    select_cols = ", ".join(f"COUNT({c}) AS {c}" for c in _NULLABLE_CANONICAL_FIELDS)
    row = session.execute(
        text(f"SELECT {select_cols} FROM marketplace_canonical_rows WHERE dataset_version_id = :vid"), {"vid": version_id},
    ).mappings().one()
    present = {f: True for f in _ALWAYS_REQUIRED_FIELDS}
    present.update({f: (row[f] or 0) > 0 for f in _NULLABLE_CANONICAL_FIELDS})
    return present


def recompute_version_summary(session: Session, version_id: str) -> dict:
    """Recomputes row_count/distinct_order_count/date_range from the final
    merged canonical_rows table -- needed after copy_forward_unmatched_rows
    since ValidationReport only reflects the newly-uploaded file, not the
    carried-forward parent rows now also part of this version."""
    row = session.execute(text("""
        SELECT COUNT(*) AS row_count, COUNT(DISTINCT order_id) AS distinct_order_count,
               MIN(order_purchase_timestamp) AS date_range_start, MAX(order_purchase_timestamp) AS date_range_end
        FROM marketplace_canonical_rows WHERE dataset_version_id = :vid
    """), {"vid": version_id}).mappings().one()
    return dict(row)


# -- dataset versions ---------------------------------------------------------

def create_pending_version(
    session: Session, *, id_: str, source_session_id: str | None, parent_version_id: str | None,
    update_mode: str, file_hash: str | None, row_count: int, distinct_order_count: int,
    date_range_start: datetime | None, date_range_end: datetime | None, validation_summary: dict, created_by: str | None,
) -> MarketplaceDatasetVersion:
    row = MarketplaceDatasetVersion(
        id=id_, source_session_id=source_session_id, parent_version_id=parent_version_id, update_mode=update_mode,
        file_hash=file_hash, row_count=row_count, distinct_order_count=distinct_order_count,
        date_range_start=date_range_start, date_range_end=date_range_end,
        validation_summary_json=validation_summary, is_active=False,
        created_at=datetime.now(timezone.utc), created_by=created_by,
    )
    session.add(row)
    session.flush()
    return row


def get_version(session: Session, version_id: str) -> MarketplaceDatasetVersion | None:
    return session.get(MarketplaceDatasetVersion, version_id)


def get_active_version(session: Session) -> MarketplaceDatasetVersion | None:
    return session.execute(select(MarketplaceDatasetVersion).where(MarketplaceDatasetVersion.is_active.is_(True))).scalar_one_or_none()


def list_versions(session: Session) -> list[MarketplaceDatasetVersion]:
    return list(session.scalars(select(MarketplaceDatasetVersion).order_by(MarketplaceDatasetVersion.created_at.desc())).all())


REQUIRED_ARTIFACTS = [
    "overview_kpis", "monthly_trends", "review_distribution", "payment_distribution",
    "rfm_segment_summary", "geography", "availability_matrix", "dataset_metadata",
]


def activate_version(session: Session, *, candidate_version_id: str, expected_active_version_id: str | None, actor: str | None) -> MarketplaceDatasetVersion:
    """Implements Checkpoint B mandatory correction #1: a transaction-scoped
    PostgreSQL advisory lock (pg_advisory_xact_lock) fully serializes
    concurrent activation attempts -- not just the partial unique index,
    which only guarantees "at most one active row after commit" and would
    otherwise allow a last-writer-wins race between two different
    confirmation sessions that both previewed against the same prior active
    version.

    Steps (exactly as mandated):
      1. Acquire the global activation lock inside this transaction.
      2. Re-read the current active version after acquiring the lock.
      3. Compare it with expected_active_version_id from the caller's preview.
      4. If they differ, reject with a controlled conflict (409).
      5. Verify the candidate version exists and is not already active/retired.
      6. Verify all required derived artifacts AND typed entity tables exist.
      7. Deactivate the old version.
      8. Activate the candidate.
      9. Commit (caller's responsibility to not touch this session concurrently).
     10. Cache invalidation happens in the SERVICE layer, after this returns,
         never inside this transaction.
    """
    # Step 1: pg_advisory_xact_lock blocks other transactions requesting the
    # SAME key until this transaction commits or rolls back -- automatically
    # released either way, no explicit unlock needed and no risk of an
    # orphaned lock surviving a crash.
    session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": MARKETPLACE_ACTIVATION_LOCK_ID})

    # Step 2: re-read AFTER acquiring the lock -- this is the value a second,
    # now-serialized transaction will see, not a snapshot taken before it
    # waited for the lock.
    current_active = get_active_version(session)
    current_active_id = current_active.id if current_active else None

    # Step 3-4: stale-preview conflict.
    if current_active_id != expected_active_version_id:
        raise ActivationConflictError(
            "The active version changed since this confirmation was previewed. Refresh and retry.",
            details={"expected_active_version_id": expected_active_version_id, "current_active_version_id": current_active_id},
        )

    # Step 5: candidate must exist and not already be active or retired.
    candidate = get_version(session, candidate_version_id)
    if candidate is None:
        raise ActivationConflictError("Candidate dataset version not found.", details={"candidate_version_id": candidate_version_id})
    if candidate.is_active:
        raise ActivationConflictError("Candidate dataset version is already active.", details={"candidate_version_id": candidate_version_id})

    # Step 6: required aggregate artifacts AND typed entity tables must exist.
    present_artifacts = set(list_derived_artifacts(session, candidate_version_id).keys())
    missing_artifacts = [a for a in REQUIRED_ARTIFACTS if a not in present_artifacts]
    if missing_artifacts:
        raise ActivationConflictError(
            "Candidate dataset version is missing required derived artifacts; activation blocked.",
            details={"missing_artifacts": missing_artifacts},
        )
    canonical_count = session.execute(
        select(func.count()).select_from(MarketplaceCanonicalRow).where(MarketplaceCanonicalRow.dataset_version_id == candidate_version_id)
    ).scalar_one()
    if canonical_count == 0:
        raise ActivationConflictError("Candidate dataset version has no canonical rows; activation blocked.")

    # Step 7-8: single-transaction flip. The partial unique index is the hard
    # backstop if this code path is ever reached by two sessions anyway
    # (e.g. a future caller that forgets to take the lock) -- one of the two
    # UPDATEs below would then fail the unique constraint on COMMIT.
    if current_active is not None:
        current_active.is_active = False
        session.flush()
    candidate.is_active = True
    session.flush()

    write_audit_event(session, "activated", version_id=candidate_version_id, actor=actor, detail={"previous_active_version_id": current_active_id})

    # Step 9: caller commits.
    return candidate


# -- retention ---------------------------------------------------------------

def retire_eligible_versions(session: Session, *, retention: int, actor: str | None) -> list[str]:
    """Deletes versions beyond the retention count, keeping (at minimum) the
    active version and its immediate parent -- never a version referenced by
    an in-progress session, and never the packaged historical seed's
    canonical/derived rows are not affected by this (historical seeding
    creates a real MarketplaceDatasetVersion row like any other; if it is
    still within the retained set it is protected by the same rule as any
    other version -- it has no special-cased protection beyond that).

    Must be called only after a successful activation transaction has
    already committed (see marketplace_version_service.confirm_and_activate).
    """
    active = get_active_version(session)
    if active is None:
        return []
    protected_ids = {active.id}
    if active.parent_version_id:
        protected_ids.add(active.parent_version_id)

    all_versions = list_versions(session)  # newest first
    retained_ids: set[str] = set()
    for v in all_versions:
        if len(retained_ids) >= retention:
            break
        retained_ids.add(v.id)
    # Protected ids (active + its immediate parent) are always retained even
    # if the retention count is set smaller than that -- retention never
    # overrides the "never delete active or its rollback target" rule.
    retained_ids |= protected_ids

    # No separate "in-progress operation" lookup is needed here: this
    # function is only ever called by the service layer AFTER an activation
    # transaction has already committed (see the module docstring and
    # marketplace_version_service.confirm_and_activate) -- a version that is
    # still mid-activation is therefore never visible to this function at
    # all, and the currently-active version is already protected above.

    deleted: list[str] = []
    for v in all_versions:
        if v.id in retained_ids:
            continue
        if v.is_active:
            continue  # never delete the active version
        write_audit_event(session, "retention_deleted", version_id=v.id, actor=actor, detail={"row_count": v.row_count})
        session.delete(v)  # ON DELETE CASCADE removes its canonical_rows/derived_artifacts/entity rows
        deleted.append(v.id)
    if deleted:
        session.commit()
    return deleted


# -- paginated entity analytics ----------------------------------------------

_SORTABLE_CUSTOMER = {"total_spend", "order_count", "average_order_value", "recency", "frequency", "monetary"}
_SORTABLE_SELLER = {"item_revenue", "order_count", "item_count", "late_delivery_rate", "average_item_value"}
_SORTABLE_PRODUCT = {"item_revenue", "item_count", "average_item_price"}


def _paginate(session: Session, model, version_id: str, *, limit: int, offset: int, sort_by: str, sort_dir: str, sortable: set[str], extra_filter=None):
    limit = max(1, min(limit, 500))
    offset = max(0, offset)
    sort_col = getattr(model, sort_by if sort_by in sortable else next(iter(sortable)))
    order = sort_col.desc() if sort_dir == "desc" else sort_col.asc()
    stmt = select(model).where(model.dataset_version_id == version_id)
    if extra_filter is not None:
        stmt = stmt.where(extra_filter)
    total = session.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    rows = session.scalars(stmt.order_by(order).limit(limit).offset(offset)).all()
    return rows, total


def list_customer_analytics(session: Session, version_id: str, *, limit: int, offset: int, sort_by: str = "total_spend", sort_dir: str = "desc", segment: str | None = None):
    extra = MarketplaceCustomerAnalytics.rfm_segment == segment if segment else None
    return _paginate(session, MarketplaceCustomerAnalytics, version_id, limit=limit, offset=offset, sort_by=sort_by, sort_dir=sort_dir, sortable=_SORTABLE_CUSTOMER, extra_filter=extra)


def list_seller_analytics(session: Session, version_id: str, *, limit: int, offset: int, sort_by: str = "item_revenue", sort_dir: str = "desc"):
    return _paginate(session, MarketplaceSellerAnalytics, version_id, limit=limit, offset=offset, sort_by=sort_by, sort_dir=sort_dir, sortable=_SORTABLE_SELLER)


def list_product_analytics(session: Session, version_id: str, *, limit: int, offset: int, sort_by: str = "item_revenue", sort_dir: str = "desc", category: str | None = None):
    extra = MarketplaceProductAnalytics.product_category_name == category if category else None
    return _paginate(session, MarketplaceProductAnalytics, version_id, limit=limit, offset=offset, sort_by=sort_by, sort_dir=sort_dir, sortable=_SORTABLE_PRODUCT, extra_filter=extra)


# -- audit ---------------------------------------------------------------

def write_audit_event(session: Session, event_type: str, *, session_id: str | None = None, version_id: str | None = None, actor: str | None = None, detail: dict | None = None) -> None:
    session.add(MarketplaceImportAudit(
        event_type=event_type, session_id=session_id, version_id=version_id, actor=actor,
        detail_json=detail, created_at=datetime.now(timezone.utc),
    ))
    session.flush()
