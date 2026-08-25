"""Orchestrates confirm-and-activate and rollback for the marketplace CSV
feature. Every write path here uses exactly ONE database transaction for
the entire "stage canonical rows -> build derived artifacts -> activate"
sequence -- if validation fails, the analytics build fails, or the
activation lock detects a stale preview, the whole transaction is rolled
back and nothing persists. The previously active version (if any) is never
touched until the single flip inside repo.activate_version() succeeds, so a
failed confirmation always leaves the previously active version serving
every page, never a partial/mixed state.
"""
from __future__ import annotations

from pathlib import Path

from sqlalchemy.orm import Session

from app.core.exceptions import InvalidRequestError
from app.db.marketplace_base import require_postgres
from app.repositories import marketplace_repository as repo
from app.services import marketplace_analytics_service
from app.services.marketplace_import_service import ValidationReport, validate_and_stage


def _new_version_id() -> str:
    import uuid
    return uuid.uuid4().hex


def confirm_and_activate(
    session: Session, *, import_session, mapping: dict[str, str], update_mode: str,
    expected_active_version_id: str | None, actor: str | None, retention: int,
) -> tuple[object, ValidationReport]:
    require_postgres()
    if update_mode not in ("append", "replace"):
        raise InvalidRequestError("update_mode must be 'append' or 'replace'.")
    if not import_session.staged_file_path or not Path(import_session.staged_file_path).is_file():
        raise InvalidRequestError("The staged upload for this session is no longer available (expired or already confirmed).")

    current_active = repo.get_active_version(session)
    parent_version_id = current_active.id if current_active else None

    version_id = _new_version_id()
    version = repo.create_pending_version(
        session, id_=version_id, source_session_id=import_session.id, parent_version_id=parent_version_id,
        update_mode=update_mode, file_hash=import_session.file_hash, row_count=0, distinct_order_count=0,
        date_range_start=None, date_range_end=None, validation_summary={}, created_by=actor,
    )

    def on_chunk(rows: list[dict]) -> None:
        for r in rows:
            r["dataset_version_id"] = version_id
        repo.bulk_insert_canonical_rows(session, rows)

    report = validate_and_stage(Path(import_session.staged_file_path), mapping, on_chunk_ready=on_chunk)

    if not report.ok:
        session.rollback()
        raise InvalidRequestError(
            "Validation failed; confirmation blocked. No data was persisted.",
            details=report.to_dict(),
        )

    summary = report.to_dict()
    if update_mode == "append" and parent_version_id is not None:
        # Copy-forward: the new version starts as the uploaded rows already
        # staged above, plus every parent row whose (order_id, order_item_id)
        # key the upload didn't touch -- see repo.copy_forward_unmatched_rows.
        copied = repo.copy_forward_unmatched_rows(session, parent_version_id=parent_version_id, new_version_id=version_id)
        conflicts = repo.find_merged_order_conflicts(session, version_id)
        if conflicts:
            session.rollback()
            raise InvalidRequestError(
                "Append blocked: merging with the current active version would leave order-level fields "
                "(payment_value/main_payment_type/payment_installments) disagreeing across an order's own rows. "
                "Re-upload every item row of the affected order(s) so the order-grain fields stay consistent.",
                details={"conflicted_order_ids": conflicts[:50], "conflicted_order_count": len(conflicts)},
            )
        merged = repo.recompute_version_summary(session, version_id)
        summary["append_rows_from_new_upload"] = summary["row_count"]
        summary["append_rows_carried_forward_from_parent"] = copied
        summary["row_count"] = merged["row_count"]
        summary["distinct_order_count"] = merged["distinct_order_count"]
        version.row_count = merged["row_count"]
        version.distinct_order_count = merged["distinct_order_count"]
        version.date_range_start = merged["date_range_start"]
        version.date_range_end = merged["date_range_end"]
    else:
        version.row_count = report.row_count
        version.distinct_order_count = report.distinct_order_count
        version.date_range_start = report.date_range_start
        version.date_range_end = report.date_range_end
    version.validation_summary_json = summary
    session.flush()

    # DB-derived, not report.fields_present -- see repo.compute_fields_present
    # docstring: for 'append', the merged table can have data (e.g. seller_id)
    # that this particular upload's own column mapping didn't include.
    merged_fields_present = repo.compute_fields_present(session, version_id)
    marketplace_analytics_service.build_and_store_all(session, version_id, merged_fields_present)

    activated = repo.activate_version(
        session, candidate_version_id=version_id, expected_active_version_id=expected_active_version_id, actor=actor,
    )

    import_session.status = "confirmed"
    staged_path = import_session.staged_file_path
    import_session.staged_file_path = None
    repo.write_audit_event(session, "confirmed", session_id=import_session.id, version_id=version_id, actor=actor, detail={"update_mode": update_mode})
    session.flush()

    # Single commit for the entire sequence -- see module docstring.
    session.commit()

    if staged_path:
        try:
            Path(staged_path).unlink(missing_ok=True)
        except OSError:
            pass

    repo.retire_eligible_versions(session, retention=retention, actor=actor)

    return activated, report


def rollback_to_version(session: Session, *, target_version_id: str, expected_active_version_id: str | None, actor: str | None, retention: int):
    """Reactivates an existing, already-built version -- no re-processing:
    its canonical rows and derived artifacts were never deleted (retention
    always protects the active version's immediate parent), so this is just
    another call into the same locked activation path."""
    require_postgres()
    target = repo.get_version(session, target_version_id)
    if target is None:
        raise InvalidRequestError("Target dataset version not found.")
    activated = repo.activate_version(
        session, candidate_version_id=target_version_id, expected_active_version_id=expected_active_version_id, actor=actor,
    )
    repo.write_audit_event(session, "rollback", version_id=target_version_id, actor=actor)
    session.commit()
    repo.retire_eligible_versions(session, retention=retention, actor=actor)
    return activated
