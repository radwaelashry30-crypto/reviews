"""Streaming upload, chunked CSV validation, grain detection, and preview
simulation for the marketplace CSV data-management feature.

Every pass over an uploaded file works in bounded chunks
(settings.MARKETPLACE_CHUNK_ROWS rows at a time) -- see Checkpoint B's
measured evidence: a naive whole-file pandas load projected to ~130MB peak
at 150,000 rows, a meaningful fraction of Render's 512MB free tier once the
already-resident model weights are counted. No function in this module ever
calls file.read() or pd.read_csv() without chunksize, and no function
materializes a full-file DataFrame.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from app.core.config import settings
from app.core.exceptions import InvalidRequestError

# -- canonical schema ---------------------------------------------------------
# grain: "order" fields are expected identical across every item row of the
# same order_id (see conflict detection below); "item" fields vary per row
# and are null for item-less order rows.
CANONICAL_FIELDS: dict[str, dict[str, Any]] = {
    "order_id":                        {"required": True,  "grain": "order", "type": "str"},
    "customer_id":                     {"required": True,  "grain": "order", "type": "str"},
    "customer_unique_id":              {"required": True,  "grain": "order", "type": "str"},
    "order_status":                    {"required": True,  "grain": "order", "type": "str"},
    "order_purchase_timestamp":        {"required": True,  "grain": "order", "type": "datetime"},
    "customer_city":                   {"required": False, "grain": "order", "type": "str"},
    "customer_state":                  {"required": False, "grain": "order", "type": "str"},
    "order_delivered_customer_date":   {"required": False, "grain": "order", "type": "datetime"},
    "order_estimated_delivery_date":   {"required": False, "grain": "order", "type": "datetime"},
    "payment_value":                   {"required": False, "grain": "order", "type": "float", "conflict_checked": True},
    "main_payment_type":               {"required": False, "grain": "order", "type": "str", "conflict_checked": True},
    "payment_installments":            {"required": False, "grain": "order", "type": "int", "conflict_checked": True},
    "review_score":                    {"required": False, "grain": "order", "type": "int"},
    "review_comment_message":          {"required": False, "grain": "order", "type": "str"},
    "order_item_id":                   {"required": False, "grain": "item", "type": "int"},
    "product_id":                      {"required": False, "grain": "item", "type": "str"},
    "product_category_name":           {"required": False, "grain": "item", "type": "str"},
    "seller_id":                       {"required": False, "grain": "item", "type": "str"},
    "seller_city":                     {"required": False, "grain": "item", "type": "str"},
    "seller_state":                    {"required": False, "grain": "item", "type": "str"},
    "price":                           {"required": False, "grain": "item", "type": "float"},
    "freight_value":                   {"required": False, "grain": "item", "type": "float"},
}
REQUIRED_FIELDS = [f for f, spec in CANONICAL_FIELDS.items() if spec["required"]]
CONFLICT_CHECKED_FIELDS = [f for f, spec in CANONICAL_FIELDS.items() if spec.get("conflict_checked")]


def template_columns() -> list[str]:
    return list(CANONICAL_FIELDS.keys())


# -- bounded streaming upload -------------------------------------------------

async def save_upload_stream(upload_file, staging_dir: Path, staged_filename: str) -> tuple[Path, str, int]:
    """Reads an UploadFile in bounded chunks and writes it to a temp staging
    file, aborting (and deleting the partial file) the instant the byte
    count exceeds MARKETPLACE_MAX_UPLOAD_BYTES -- never trusts Content-Length
    alone (it can be absent or wrong), and never buffers the whole file in
    memory. Returns (path, sha256_hex, size_bytes)."""
    staging_dir.mkdir(parents=True, exist_ok=True)
    dest = staging_dir / staged_filename
    hasher = hashlib.sha256()
    total = 0
    read_chunk_bytes = 1024 * 1024  # 1MB per read -- bounds peak memory for the stream itself
    try:
        with open(dest, "wb") as out:
            while True:
                chunk = await upload_file.read(read_chunk_bytes)
                if not chunk:
                    break
                total += len(chunk)
                if total > settings.MARKETPLACE_MAX_UPLOAD_BYTES:
                    raise InvalidRequestError(
                        f"Upload exceeds the {settings.MARKETPLACE_MAX_UPLOAD_BYTES} byte limit "
                        f"({settings.MARKETPLACE_MAX_UPLOAD_BYTES / 1_048_576:.0f} MiB).",
                        details={"limit_bytes": settings.MARKETPLACE_MAX_UPLOAD_BYTES},
                    )
                hasher.update(chunk)
                out.write(chunk)
    except Exception:
        dest.unlink(missing_ok=True)
        raise
    return dest, hasher.hexdigest(), total


def count_lines_fast(path: Path) -> int:
    """Bounded-memory pre-check: counts raw newline bytes in fixed-size
    binary chunks (never loads the file into pandas). This is an UPPER
    BOUND on the true row count (a quoted CSV field containing an embedded
    newline adds an extra byte-level newline without adding a real row), so
    it can only reject a file that is actually fine in rare cases, never
    silently admit one that is genuinely oversized -- the authoritative,
    exact check is the chunked pandas parse in validate_and_stage()."""
    count = 0
    with open(path, "rb") as f:
        while True:
            block = f.read(1024 * 1024)
            if not block:
                break
            count += block.count(b"\n")
    return count


def read_header(path: Path) -> list[str]:
    """Bounded: reads only the first line."""
    with open(path, encoding="utf-8-sig", newline="") as f:
        header_line = f.readline()
    import csv
    import io
    return next(csv.reader(io.StringIO(header_line)))


# -- chunked validation / grain detection / preview / staging ----------------

@dataclass
class ValidationReport:
    row_count: int = 0
    distinct_order_count: int = 0
    itemless_row_count: int = 0
    missing_required_columns: list[str] = field(default_factory=list)
    conflicted_order_ids: list[str] = field(default_factory=list)
    duplicate_item_keys: list[str] = field(default_factory=list)
    fields_present: dict[str, bool] = field(default_factory=dict)
    date_range_start: datetime | None = None
    date_range_end: datetime | None = None
    ok: bool = True
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "row_count": self.row_count,
            "distinct_order_count": self.distinct_order_count,
            "itemless_row_count": self.itemless_row_count,
            "missing_required_columns": self.missing_required_columns,
            "conflicted_order_ids": self.conflicted_order_ids[:50],
            "conflicted_order_count": len(self.conflicted_order_ids),
            "duplicate_item_keys": self.duplicate_item_keys[:50],
            "duplicate_item_key_count": len(self.duplicate_item_keys),
            "fields_present": self.fields_present,
            "date_range_start": self.date_range_start.isoformat() if self.date_range_start else None,
            "date_range_end": self.date_range_end.isoformat() if self.date_range_end else None,
            "ok": self.ok,
            "errors": self.errors,
        }


def _coerce_chunk(chunk: pd.DataFrame) -> pd.DataFrame:
    for col, spec in CANONICAL_FIELDS.items():
        if col not in chunk.columns:
            continue
        if spec["type"] == "datetime":
            chunk[col] = pd.to_datetime(chunk[col], errors="coerce", utc=True)
        elif spec["type"] == "float":
            chunk[col] = pd.to_numeric(chunk[col], errors="coerce")
        elif spec["type"] == "int":
            chunk[col] = pd.to_numeric(chunk[col], errors="coerce").astype("Int64")
        else:
            chunk[col] = chunk[col].astype(str).where(chunk[col].notna(), None)
            chunk[col] = chunk[col].replace({"nan": None, "": None})
    return chunk


def validate_and_stage(
    path: Path, mapping: dict[str, str], *, on_chunk_ready=None,
) -> ValidationReport:
    """Single chunked pass over the CSV. If on_chunk_ready is given, it is
    called once per chunk with a list[dict] of canonical-field rows (used by
    the confirm flow to bulk-insert into marketplace_canonical_rows without
    ever holding more than one chunk in memory at a time). Always runs to
    completion so the full ValidationReport is accurate -- callers decide
    whether to discard a partially-staged version on failure.
    """
    report = ValidationReport()
    inverse_mapping = mapping  # {csv_column: canonical_field}
    mapped_canonical_fields = set(inverse_mapping.values())
    report.missing_required_columns = [f for f in REQUIRED_FIELDS if f not in mapped_canonical_fields]
    for f in CANONICAL_FIELDS:
        report.fields_present[f] = f in mapped_canonical_fields
    if report.missing_required_columns:
        report.ok = False
        report.errors.append(f"Missing required column mapping for: {', '.join(report.missing_required_columns)}")
        return report

    order_seen: dict[str, tuple] = {}  # order_id -> (payment_value, main_payment_type, payment_installments)
    conflicted: set[str] = set()
    distinct_orders: set[str] = set()
    item_keys: set[tuple] = set()
    duplicates: set[str] = set()

    try:
        for chunk in pd.read_csv(path, dtype=str, chunksize=settings.MARKETPLACE_CHUNK_ROWS, keep_default_na=True):
            chunk = chunk.rename(columns=inverse_mapping)
            keep_cols = [c for c in mapped_canonical_fields if c in chunk.columns]
            chunk = chunk[keep_cols]
            chunk = _coerce_chunk(chunk)

            report.row_count += len(chunk)
            if report.row_count > settings.MARKETPLACE_MAX_ROWS:
                report.ok = False
                report.errors.append(f"Row count exceeds the {settings.MARKETPLACE_MAX_ROWS}-row limit.")
                return report

            if "order_purchase_timestamp" in chunk.columns:
                chunk_min = chunk["order_purchase_timestamp"].min()
                chunk_max = chunk["order_purchase_timestamp"].max()
                if pd.notna(chunk_min) and (report.date_range_start is None or chunk_min < report.date_range_start):
                    report.date_range_start = chunk_min.to_pydatetime()
                if pd.notna(chunk_max) and (report.date_range_end is None or chunk_max > report.date_range_end):
                    report.date_range_end = chunk_max.to_pydatetime()

            has_item_id = "order_item_id" in chunk.columns
            rows_out: list[dict] = []
            for record in chunk.to_dict(orient="records"):
                order_id = record.get("order_id")
                distinct_orders.add(order_id)

                item_id = record.get("order_item_id") if has_item_id else None
                item_id = None if pd.isna(item_id) else int(item_id)
                key = (order_id, item_id if item_id is not None else "__itemless__")
                if key in item_keys:
                    # Record the conflict but never attempt to insert this
                    # row -- the DB's own unique constraint would raise a
                    # raw IntegrityError instead of the controlled
                    # validation-failure response callers expect.
                    duplicates.add(f"{order_id}:{item_id}")
                    continue
                item_keys.add(key)
                if item_id is None:
                    report.itemless_row_count += 1

                payment_tuple = tuple(
                    (None if pd.isna(record.get(f)) else record.get(f)) for f in CONFLICT_CHECKED_FIELDS
                )
                # Only compare fields the uploader actually mapped -- an
                # entirely-absent optional field is not a "conflict".
                if any(f in mapped_canonical_fields for f in CONFLICT_CHECKED_FIELDS):
                    prior = order_seen.get(order_id)
                    if prior is None:
                        order_seen[order_id] = payment_tuple
                    elif prior != payment_tuple:
                        conflicted.add(order_id)

                if on_chunk_ready is not None:
                    clean = {k: (None if (v is None or (isinstance(v, float) and pd.isna(v))) else v) for k, v in record.items()}
                    rows_out.append(clean)

            if on_chunk_ready is not None:
                on_chunk_ready(rows_out)
    except pd.errors.ParserError as e:
        report.ok = False
        report.errors.append(f"CSV could not be parsed: {e}")
        return report

    report.distinct_order_count = len(distinct_orders)
    report.conflicted_order_ids = sorted(conflicted)
    report.duplicate_item_keys = sorted(duplicates)

    if report.conflicted_order_ids:
        report.ok = False
        report.errors.append(
            f"{len(report.conflicted_order_ids)} order(s) have conflicting payment fields across their item "
            "rows (payment_value/main_payment_type/payment_installments must be identical for every row of "
            "the same order_id). Confirmation is blocked until this is fixed in the source file."
        )
    if report.duplicate_item_keys:
        report.ok = False
        report.errors.append(
            f"{len(report.duplicate_item_keys)} duplicate (order_id, order_item_id) key(s) found; the canonical "
            "grain requires each to be unique (or a single null-item row per item-less order)."
        )
    return report


def build_availability_matrix(fields_present: dict[str, bool]) -> dict[str, bool]:
    """Per Checkpoint B's independent-tier rule (correction #7 / part 7):
    each capability is evaluated on its own required fields, not collapsed
    into one page-level flag."""
    def has(*names: str) -> bool:
        return all(fields_present.get(n) for n in names)

    return {
        "customers": has("customer_id", "customer_unique_id"),
        "customer_rfm": has("order_id", "order_purchase_timestamp", "payment_value"),
        "sellers": has("seller_id"),
        "seller_performance": has("seller_id", "order_delivered_customer_date", "order_estimated_delivery_date"),
        "products_product_level": has("product_id"),
        "products_category_level": has("product_category_name"),
        "product_revenue": has("product_id", "price"),
        "geography": has("customer_city") or has("customer_state") or has("seller_city") or has("seller_state"),
        "reviews_order_level": has("review_score"),
        "reviews_category_restricted": has("review_score", "product_id", "product_category_name"),
        "payment_distribution": has("main_payment_type"),
        "payment_installments": has("payment_installments"),
    }
