"""Marketplace CSV data-management endpoints.

Authorization: write/administrative routes require require_marketplace_admin_key
(always enforced, independent of the global REQUIRE_API_KEY switch -- see
app/core/security.py). Read routes that only ever expose the currently
ACTIVE version's already-public-shaped analytics (the same class of data
the existing /customers, /sellers, /products endpoints already serve
openly) stay public, matching Checkpoint B's endpoint table.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, Query, Request, UploadFile

from app.core.config import settings
from app.core.exceptions import InvalidRequestError, ResourceNotFoundError
from app.core.security import require_marketplace_admin_key
from app.db.base import get_session_factory
from app.db.marketplace_base import require_postgres
from app.repositories import marketplace_repository as repo
from app.schemas.common import envelope
from app.schemas.marketplace import ConfirmRequest, MappingRequest, RollbackRequest
from app.services import marketplace_import_service as import_service
from app.services import marketplace_version_service as version_service

router = APIRouter(prefix="/marketplace-data", tags=["marketplace-data"])


def _db_session():
    factory = get_session_factory()
    session = factory()
    try:
        yield session
    finally:
        session.close()


# -- public: template + active-version reads ---------------------------------

@router.get("/template")
def get_template():
    fields = import_service.CANONICAL_FIELDS
    return envelope({
        "columns": list(fields.keys()),
        "required": import_service.REQUIRED_FIELDS,
        "grain": {k: v["grain"] for k, v in fields.items()},
        "notes": (
            "One row per order item. Item-less orders (canceled/unavailable before fulfillment) must still "
            "appear as exactly one row with blank item-grain fields (order_item_id, product_id, seller_id, "
            "price, freight_value). Order-grain fields (order_id, customer_*, order_status, timestamps, "
            "payment_value, main_payment_type, payment_installments, review_*) must be identical across every "
            "row of the same order_id -- payment_value/main_payment_type/payment_installments conflicts across "
            "an order's rows block confirmation. main_payment_type must already be the dominant/mode payment "
            "type for the order (this consolidated CSV does not accept raw normalized multi-payment rows)."
        ),
    })


@router.get("/active")
def get_active(session=Depends(_db_session)):
    require_postgres()
    active = repo.get_active_version(session)
    if active is None:
        return envelope({"active": False, "source": "historical_packaged"})
    artifacts = repo.list_derived_artifacts(session, active.id)
    return envelope({
        "active": True,
        "version_id": active.id,
        "update_mode": active.update_mode,
        "row_count": active.row_count,
        "distinct_order_count": active.distinct_order_count,
        "date_range_start": active.date_range_start.isoformat() if active.date_range_start else None,
        "date_range_end": active.date_range_end.isoformat() if active.date_range_end else None,
        "created_at": active.created_at.isoformat(),
        "availability_matrix": artifacts.get("availability_matrix"),
        "dataset_metadata": artifacts.get("dataset_metadata"),
    })


@router.get("/active/aggregate/{artifact_name}")
def get_active_aggregate(artifact_name: str, session=Depends(_db_session)):
    require_postgres()
    active = repo.get_active_version(session)
    if active is None:
        raise ResourceNotFoundError("No active marketplace dataset version.")
    payload = repo.get_derived_artifact(session, active.id, artifact_name)
    if payload is None:
        raise ResourceNotFoundError(f"Artifact '{artifact_name}' not found for the active version.")
    return envelope(payload)


@router.get("/active/customers")
def get_active_customers(session=Depends(_db_session), limit: int = Query(50, le=500), offset: int = Query(0, ge=0), sort_by: str = "total_spend", sort_dir: str = "desc", segment: str | None = None):
    require_postgres()
    active = repo.get_active_version(session)
    if active is None:
        raise ResourceNotFoundError("No active marketplace dataset version.")
    rows, total = repo.list_customer_analytics(session, active.id, limit=limit, offset=offset, sort_by=sort_by, sort_dir=sort_dir, segment=segment)
    return envelope({"total": total, "limit": limit, "offset": offset, "items": [
        {"customer_unique_id": r.customer_unique_id, "order_count": r.order_count, "total_spend": float(r.total_spend),
         "average_order_value": float(r.average_order_value), "recency": r.recency, "frequency": r.frequency,
         "monetary": r.monetary, "rfm_segment": r.rfm_segment, "rfm_out_of_distribution": r.rfm_out_of_distribution,
         "customer_city": r.customer_city, "customer_state": r.customer_state} for r in rows
    ]})


@router.get("/active/sellers")
def get_active_sellers(session=Depends(_db_session), limit: int = Query(50, le=500), offset: int = Query(0, ge=0), sort_by: str = "item_revenue", sort_dir: str = "desc"):
    require_postgres()
    active = repo.get_active_version(session)
    if active is None:
        raise ResourceNotFoundError("No active marketplace dataset version.")
    rows, total = repo.list_seller_analytics(session, active.id, limit=limit, offset=offset, sort_by=sort_by, sort_dir=sort_dir)
    return envelope({"total": total, "limit": limit, "offset": offset, "items": [
        {"seller_id": r.seller_id, "order_count": r.order_count, "item_count": r.item_count,
         "item_revenue": float(r.item_revenue), "average_item_value": float(r.average_item_value),
         "late_delivery_rate": r.late_delivery_rate, "product_count": r.product_count, "category_count": r.category_count,
         "seller_city": r.seller_city, "seller_state": r.seller_state} for r in rows
    ]})


@router.get("/active/products")
def get_active_products(session=Depends(_db_session), limit: int = Query(50, le=500), offset: int = Query(0, ge=0), sort_by: str = "item_revenue", sort_dir: str = "desc", category: str | None = None):
    require_postgres()
    active = repo.get_active_version(session)
    if active is None:
        raise ResourceNotFoundError("No active marketplace dataset version.")
    rows, total = repo.list_product_analytics(session, active.id, limit=limit, offset=offset, sort_by=sort_by, sort_dir=sort_dir, category=category)
    return envelope({"total": total, "limit": limit, "offset": offset, "items": [
        {"product_id": r.product_id, "product_category_name": r.product_category_name, "item_count": r.item_count,
         "item_revenue": float(r.item_revenue), "average_item_price": float(r.average_item_price),
         "freight_value": float(r.freight_value),
         "order_review_score_associated_with_single_category_orders": r.associated_single_category_order_review_average,
         "associated_review_order_count": r.associated_review_order_count,
         "associated_review_excluded_order_count": r.associated_review_excluded_order_count} for r in rows
    ]})


# -- admin: upload / mapping / preview / confirm / rollback -------------------

@router.post("/uploads", dependencies=[Depends(require_marketplace_admin_key)])
async def create_upload(file: UploadFile = File(...), session=Depends(_db_session), actor: str = Depends(require_marketplace_admin_key)):
    require_postgres()
    repo.expire_stale_sessions(session)

    staging_dir = settings.MARKETPLACE_STAGING_DIR
    session_id = uuid.uuid4().hex
    staged_filename = f"{session_id}.csv"
    try:
        path, file_hash, size_bytes = await import_service.save_upload_stream(file, staging_dir, staged_filename)
    finally:
        await file.close()

    approx_lines = import_service.count_lines_fast(path)
    if approx_lines - 1 > settings.MARKETPLACE_MAX_ROWS * 1.02:  # small buffer for the embedded-newline over-count
        path.unlink(missing_ok=True)
        raise InvalidRequestError(
            f"Upload appears to exceed the {settings.MARKETPLACE_MAX_ROWS}-row limit (~{approx_lines - 1} rows detected).",
            details={"approx_row_count": approx_lines - 1, "limit": settings.MARKETPLACE_MAX_ROWS},
        )

    row = repo.create_import_session(
        session, id_=session_id, filename=file.filename or "upload.csv", file_hash=file_hash, file_size_bytes=size_bytes,
        ttl_minutes=settings.MARKETPLACE_IMPORT_TTL_MINUTES, created_by=actor,
    )
    row.staged_file_path = str(path)
    session.commit()
    repo.write_audit_event(session, "upload", session_id=row.id, actor=actor, detail={"filename": row.filename, "size_bytes": size_bytes})
    session.commit()

    header = import_service.read_header(path)
    return envelope({
        "session_id": row.id, "filename": row.filename, "size_bytes": size_bytes,
        "expires_at": row.expires_at.isoformat(), "detected_columns": header,
        "canonical_fields": list(import_service.CANONICAL_FIELDS.keys()),
    })


@router.get("/uploads/{session_id}", dependencies=[Depends(require_marketplace_admin_key)])
def get_upload(session_id: str, session=Depends(_db_session)):
    require_postgres()
    row = repo.get_active_import_session(session, session_id)
    if row is None:
        raise ResourceNotFoundError("Import session not found or expired.")
    return envelope({
        "session_id": row.id, "filename": row.filename, "status": row.status, "mapping": row.mapping_json,
        "validation_report": row.validation_report_json, "expires_at": row.expires_at.isoformat(),
    })


@router.patch("/uploads/{session_id}/mapping", dependencies=[Depends(require_marketplace_admin_key)])
def set_mapping(session_id: str, body: MappingRequest, session=Depends(_db_session)):
    require_postgres()
    row = repo.get_active_import_session(session, session_id)
    if row is None:
        raise ResourceNotFoundError("Import session not found or expired.")
    unknown = [f for f in body.mapping.values() if f not in import_service.CANONICAL_FIELDS]
    if unknown:
        raise InvalidRequestError(f"Unknown canonical field(s): {unknown}")
    repo.update_session(session, row, mapping_json=body.mapping, status="mapped")
    session.commit()
    return envelope({"session_id": row.id, "status": row.status, "mapping": row.mapping_json})


@router.get("/uploads/{session_id}/preview", dependencies=[Depends(require_marketplace_admin_key)])
def preview_upload(session_id: str, session=Depends(_db_session)):
    require_postgres()
    row = repo.get_active_import_session(session, session_id)
    if row is None:
        raise ResourceNotFoundError("Import session not found or expired.")
    if not row.mapping_json:
        raise InvalidRequestError("Set a column mapping before previewing (PATCH .../mapping).")
    if not row.staged_file_path:
        raise InvalidRequestError("Staged upload content is no longer available for this session.")

    from pathlib import Path
    report = import_service.validate_and_stage(Path(row.staged_file_path), row.mapping_json, on_chunk_ready=None)
    availability = import_service.build_availability_matrix(report.fields_present)

    repo.update_session(
        session, row, validation_report_json=report.to_dict(),
        status="previewed" if report.ok else row.status,
    )
    session.commit()

    current_active = repo.get_active_version(session)
    return envelope({
        "session_id": row.id, "validation": report.to_dict(), "availability_matrix": availability,
        "expected_active_version_id": current_active.id if current_active else None,
    })


@router.post("/uploads/{session_id}/confirm", dependencies=[Depends(require_marketplace_admin_key)])
def confirm_upload(session_id: str, body: ConfirmRequest, request: Request, session=Depends(_db_session), actor: str = Depends(require_marketplace_admin_key)):
    require_postgres()
    row = repo.get_active_import_session(session, session_id)
    if row is None:
        raise ResourceNotFoundError("Import session not found or expired.")
    if not row.mapping_json:
        raise InvalidRequestError("Set a column mapping before confirming (PATCH .../mapping).")

    version, report = version_service.confirm_and_activate(
        session, import_session=row, mapping=row.mapping_json, update_mode=body.update_mode,
        expected_active_version_id=body.expected_active_version_id, actor=actor,
        retention=settings.MARKETPLACE_VERSION_RETENTION,
    )

    # Cache reload happens ONLY after the activation transaction committed
    # (see marketplace_version_service.confirm_and_activate -- it commits
    # before returning), never before.
    if hasattr(request.app.state, "marketplace_cache"):
        request.app.state.marketplace_cache.load_active()

    return envelope({
        "version_id": version.id, "row_count": version.row_count, "distinct_order_count": version.distinct_order_count,
        # version.validation_summary_json, not the bare report.to_dict(): for
        # 'append' it's been enriched with append_rows_from_new_upload /
        # append_rows_carried_forward_from_parent -- see confirm_and_activate.
        "update_mode": version.update_mode, "validation": version.validation_summary_json,
    })


@router.delete("/uploads/{session_id}", dependencies=[Depends(require_marketplace_admin_key)])
def delete_upload(session_id: str, session=Depends(_db_session), actor: str = Depends(require_marketplace_admin_key)):
    require_postgres()
    row = repo.get_active_import_session(session, session_id)
    if row is None:
        raise ResourceNotFoundError("Import session not found or expired.")
    repo.delete_session(session, row)
    return envelope({"session_id": session_id, "status": "deleted"})


@router.get("/versions", dependencies=[Depends(require_marketplace_admin_key)])
def list_versions(session=Depends(_db_session)):
    require_postgres()
    versions = repo.list_versions(session)
    return envelope({"items": [
        {"version_id": v.id, "is_active": v.is_active, "update_mode": v.update_mode, "row_count": v.row_count,
         "distinct_order_count": v.distinct_order_count, "created_at": v.created_at.isoformat(),
         "parent_version_id": v.parent_version_id} for v in versions
    ]})


@router.post("/versions/rollback", dependencies=[Depends(require_marketplace_admin_key)])
def rollback(body: RollbackRequest, request: Request, session=Depends(_db_session), actor: str = Depends(require_marketplace_admin_key)):
    require_postgres()
    activated = version_service.rollback_to_version(
        session, target_version_id=body.target_version_id, expected_active_version_id=body.expected_active_version_id,
        actor=actor, retention=settings.MARKETPLACE_VERSION_RETENTION,
    )
    if hasattr(request.app.state, "marketplace_cache"):
        request.app.state.marketplace_cache.load_active()
    return envelope({"version_id": activated.id, "is_active": activated.is_active})
