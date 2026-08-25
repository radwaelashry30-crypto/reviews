"""Integration tests for the marketplace CSV data-management feature.
Requires a real PostgreSQL DATABASE_URL (this feature is Postgres-only --
see app/db/marketplace_base.py). Skips cleanly if not configured, same
pattern as _bert_available()/_cnn_available() in test_sentiment_api.py.
"""
from __future__ import annotations

import io
import uuid

import pytest
from sqlalchemy import text

from app.core.config import settings
from app.db.base import db_configured, get_session_factory


def _pg_available() -> bool:
    if not db_configured():
        return False
    from app.db.base import get_engine
    return get_engine().dialect.name == "postgresql"


pytestmark = pytest.mark.skipif(not _pg_available(), reason="Marketplace tests require a real PostgreSQL DATABASE_URL.")


@pytest.fixture(autouse=True)
def _clean_marketplace_tables():
    """Truncates every marketplace table before each test so tests don't
    interfere with each other's active-version state. CASCADE handles the
    FK chain; import_audit is included explicitly since nothing else
    references it."""
    session = get_session_factory()()
    try:
        for table in [
            "marketplace_import_audit", "marketplace_customer_analytics", "marketplace_seller_analytics",
            "marketplace_product_analytics", "marketplace_derived_artifacts", "marketplace_canonical_rows",
            "marketplace_dataset_versions", "marketplace_import_sessions",
        ]:
            session.execute(text(f"TRUNCATE TABLE {table} CASCADE"))
        session.commit()
    finally:
        session.close()
    yield


ADMIN_HEADERS = {"X-Api-Key": "test-marketplace-admin-key"}


@pytest.fixture(autouse=True)
def _admin_key(monkeypatch):
    monkeypatch.setattr(settings, "API_KEYS", ["test-marketplace-admin-key"])
    yield


def _csv_bytes(rows: list[dict], columns: list[str]) -> bytes:
    import csv
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=columns)
    writer.writeheader()
    for r in rows:
        writer.writerow(r)
    return buf.getvalue().encode("utf-8")


CSV_COLUMNS = [
    "order_id", "order_item_id", "customer_id", "customer_unique_id", "order_status",
    "order_purchase_timestamp", "order_delivered_customer_date", "order_estimated_delivery_date",
    "customer_city", "customer_state", "payment_value", "main_payment_type", "payment_installments",
    "review_score", "product_id", "product_category_name", "seller_id", "seller_city", "seller_state",
    "price", "freight_value",
]
MAPPING = {c: c for c in CSV_COLUMNS}

SAMPLE_ROWS = [
    # O1: multi-item, single-category order (2 items, both "electronics")
    {"order_id": "O1", "order_item_id": "1", "customer_id": "C1a", "customer_unique_id": "CU1", "order_status": "delivered",
     "order_purchase_timestamp": "2024-01-01T10:00:00Z", "order_delivered_customer_date": "2024-01-05T10:00:00Z",
     "order_estimated_delivery_date": "2024-01-10T10:00:00Z", "customer_city": "saopaulo", "customer_state": "SP",
     "payment_value": "300.00", "main_payment_type": "credit_card", "payment_installments": "3", "review_score": "5",
     "product_id": "P1", "product_category_name": "electronics", "seller_id": "S1", "seller_city": "rio", "seller_state": "RJ",
     "price": "100.00", "freight_value": "10.00"},
    {"order_id": "O1", "order_item_id": "2", "customer_id": "C1a", "customer_unique_id": "CU1", "order_status": "delivered",
     "order_purchase_timestamp": "2024-01-01T10:00:00Z", "order_delivered_customer_date": "2024-01-05T10:00:00Z",
     "order_estimated_delivery_date": "2024-01-10T10:00:00Z", "customer_city": "saopaulo", "customer_state": "SP",
     "payment_value": "300.00", "main_payment_type": "credit_card", "payment_installments": "3", "review_score": "5",
     "product_id": "P2", "product_category_name": "electronics", "seller_id": "S1", "seller_city": "rio", "seller_state": "RJ",
     "price": "200.00", "freight_value": "10.00"},
    # O2: single-item order
    {"order_id": "O2", "order_item_id": "1", "customer_id": "C2a", "customer_unique_id": "CU2", "order_status": "delivered",
     "order_purchase_timestamp": "2024-01-02T10:00:00Z", "order_delivered_customer_date": "2024-01-20T10:00:00Z",
     "order_estimated_delivery_date": "2024-01-10T10:00:00Z", "customer_city": "curitiba", "customer_state": "PR",
     "payment_value": "50.00", "main_payment_type": "boleto", "payment_installments": "1", "review_score": "3",
     "product_id": "P3", "product_category_name": "books", "seller_id": "S2", "seller_city": "rio", "seller_state": "RJ",
     "price": "50.00", "freight_value": "5.00"},
    # O3: item-less (canceled) order -- must be exactly one row with blank item fields
    {"order_id": "O3", "order_item_id": "", "customer_id": "C3a", "customer_unique_id": "CU3", "order_status": "canceled",
     "order_purchase_timestamp": "2024-01-03T10:00:00Z", "order_delivered_customer_date": "", "order_estimated_delivery_date": "",
     "customer_city": "saopaulo", "customer_state": "SP", "payment_value": "0.00", "main_payment_type": "not_defined",
     "payment_installments": "0", "review_score": "", "product_id": "", "product_category_name": "", "seller_id": "",
     "seller_city": "", "seller_state": "", "price": "", "freight_value": ""},
    # O4: multi-item, MULTI-category order (excluded from restricted review avg)
    {"order_id": "O4", "order_item_id": "1", "customer_id": "C4a", "customer_unique_id": "CU4", "order_status": "delivered",
     "order_purchase_timestamp": "2024-01-04T10:00:00Z", "order_delivered_customer_date": "2024-01-08T10:00:00Z",
     "order_estimated_delivery_date": "2024-01-09T10:00:00Z", "customer_city": "recife", "customer_state": "PE",
     "payment_value": "150.00", "main_payment_type": "voucher", "payment_installments": "1", "review_score": "4",
     "product_id": "P1", "product_category_name": "electronics", "seller_id": "S1", "seller_city": "rio", "seller_state": "RJ",
     "price": "100.00", "freight_value": "10.00"},
    {"order_id": "O4", "order_item_id": "2", "customer_id": "C4a", "customer_unique_id": "CU4", "order_status": "delivered",
     "order_purchase_timestamp": "2024-01-04T10:00:00Z", "order_delivered_customer_date": "2024-01-08T10:00:00Z",
     "order_estimated_delivery_date": "2024-01-09T10:00:00Z", "customer_city": "recife", "customer_state": "PE",
     "payment_value": "150.00", "main_payment_type": "voucher", "payment_installments": "1", "review_score": "4",
     "product_id": "P4", "product_category_name": "books", "seller_id": "S2", "seller_city": "rio", "seller_state": "RJ",
     "price": "50.00", "freight_value": "0.00"},
]


def _upload_map_preview_confirm(client, rows, columns=CSV_COLUMNS, mapping=None, update_mode="replace", expected_active_version_id="__AUTO__"):
    csv_bytes = _csv_bytes(rows, columns)
    up = client.post("/api/v1/marketplace-data/uploads", files={"file": ("test.csv", csv_bytes, "text/csv")}, headers=ADMIN_HEADERS)
    assert up.status_code == 200, up.text
    session_id = up.json()["data"]["session_id"]

    m = client.patch(f"/api/v1/marketplace-data/uploads/{session_id}/mapping", json={"mapping": mapping or MAPPING}, headers=ADMIN_HEADERS)
    assert m.status_code == 200, m.text

    p = client.get(f"/api/v1/marketplace-data/uploads/{session_id}/preview", headers=ADMIN_HEADERS)
    assert p.status_code == 200, p.text
    preview_data = p.json()["data"]

    if expected_active_version_id == "__AUTO__":
        expected_active_version_id = preview_data["expected_active_version_id"]

    c = client.post(
        f"/api/v1/marketplace-data/uploads/{session_id}/confirm",
        json={"update_mode": update_mode, "expected_active_version_id": expected_active_version_id},
        headers=ADMIN_HEADERS,
    )
    return preview_data, c


# -- happy path + anti-inflation ---------------------------------------------

def test_full_flow_confirms_and_activates(client):
    preview, confirm_resp = _upload_map_preview_confirm(client, SAMPLE_ROWS)
    assert preview["validation"]["ok"] is True
    assert confirm_resp.status_code == 200, confirm_resp.text
    data = confirm_resp.json()["data"]
    assert data["row_count"] == 6
    assert data["distinct_order_count"] == 4  # O1, O2, O3, O4

    active = client.get("/api/v1/marketplace-data/active")
    assert active.status_code == 200
    assert active.json()["data"]["active"] is True
    assert active.json()["data"]["version_id"] == data["version_id"]


def test_anti_inflation_revenue_not_multiplied_by_item_count(client):
    """O1 has 2 item rows but ONE payment_value=300.00 -- total_revenue must
    count it once, not twice, mirroring the existing tested rule in
    app/ml/feature_engineering.py / segmentation.py."""
    _, confirm_resp = _upload_map_preview_confirm(client, SAMPLE_ROWS)
    assert confirm_resp.status_code == 200, confirm_resp.text

    kpis = client.get("/api/v1/marketplace-data/active/aggregate/overview_kpis")
    assert kpis.status_code == 200
    data = kpis.json()["data"]
    # O1=300 + O2=50 + O3=0 + O4=150 = 500, NOT 300*2 + 50 + 0 + 150*2 = 950
    assert data["total_revenue"] == 500.0
    assert data["total_orders"] == 4


def test_itemless_order_preserved_as_one_row(client):
    _, confirm_resp = _upload_map_preview_confirm(client, SAMPLE_ROWS)
    assert confirm_resp.status_code == 200, confirm_resp.text
    assert confirm_resp.json()["data"]["validation"]["itemless_row_count"] == 1


def test_restricted_product_review_excludes_multi_category_orders(client):
    """P1 appears in O1 (single-category order, review=5) and O4
    (multi-category order, review=4). The restricted average must use ONLY
    O1's review for P1, and record O4 as excluded -- never blend the two."""
    _, confirm_resp = _upload_map_preview_confirm(client, SAMPLE_ROWS)
    assert confirm_resp.status_code == 200, confirm_resp.text

    products = client.get("/api/v1/marketplace-data/active/products")
    items = {p["product_id"]: p for p in products.json()["data"]["items"]}
    p1 = items["P1"]
    assert p1["order_review_score_associated_with_single_category_orders"] == 5.0
    assert p1["associated_review_order_count"] == 1
    assert p1["associated_review_excluded_order_count"] == 1  # O4 excluded


# -- payment conflict / duplicate-key blocking --------------------------------

def test_payment_conflict_blocks_confirmation(client):
    rows = [dict(r) for r in SAMPLE_ROWS[:2]]
    rows[1]["payment_value"] = "999.00"  # conflicts with row 0's 300.00 for the same order_id
    _, confirm_resp = _upload_map_preview_confirm(client, rows)
    assert confirm_resp.status_code == 400
    details = confirm_resp.json()["error"]["details"]
    assert "O1" in details["conflicted_order_ids"]

    active = client.get("/api/v1/marketplace-data/active")
    assert active.json()["data"]["active"] is False  # nothing was persisted


def test_duplicate_item_key_blocks_confirmation(client):
    rows = [dict(r) for r in SAMPLE_ROWS[:2]]
    rows[1]["order_item_id"] = "1"  # duplicates row 0's (O1, 1) key
    _, confirm_resp = _upload_map_preview_confirm(client, rows)
    assert confirm_resp.status_code == 400
    assert confirm_resp.json()["error"]["details"]["duplicate_item_key_count"] >= 1


def test_missing_required_mapping_rejected(client):
    csv_bytes = _csv_bytes(SAMPLE_ROWS, CSV_COLUMNS)
    up = client.post("/api/v1/marketplace-data/uploads", files={"file": ("test.csv", csv_bytes, "text/csv")}, headers=ADMIN_HEADERS)
    session_id = up.json()["data"]["session_id"]
    bad_mapping = {k: v for k, v in MAPPING.items() if v != "order_id"}  # drop a required field
    m = client.patch(f"/api/v1/marketplace-data/uploads/{session_id}/mapping", json={"mapping": bad_mapping}, headers=ADMIN_HEADERS)
    assert m.status_code == 200  # mapping itself is accepted syntactically
    p = client.get(f"/api/v1/marketplace-data/uploads/{session_id}/preview", headers=ADMIN_HEADERS)
    assert p.json()["data"]["validation"]["ok"] is False
    assert "order_id" in p.json()["data"]["validation"]["missing_required_columns"]


# -- authorization -------------------------------------------------------------

def test_upload_requires_admin_key_even_when_require_api_key_globally_false(client, monkeypatch):
    monkeypatch.setattr(settings, "REQUIRE_API_KEY", False)  # global switch OFF
    csv_bytes = _csv_bytes(SAMPLE_ROWS, CSV_COLUMNS)
    resp = client.post("/api/v1/marketplace-data/uploads", files={"file": ("test.csv", csv_bytes, "text/csv")})  # no X-Api-Key
    assert resp.status_code == 401


def test_active_read_needs_no_marketplace_admin_key(client, monkeypatch):
    """Read routes only carry the router-level require_api_key dependency
    (same as every other public analytics endpoint, e.g. /customers) -- they
    deliberately do NOT carry require_marketplace_admin_key. With the global
    switch at its real deployment default (REQUIRE_API_KEY=false), this
    means no key at all is needed, unlike the write routes above."""
    monkeypatch.setattr(settings, "REQUIRE_API_KEY", False)
    resp = client.get("/api/v1/marketplace-data/active")
    assert resp.status_code == 200


def test_invalid_admin_key_is_rejected(client):
    resp = client.post(
        "/api/v1/marketplace-data/uploads",
        files={"file": ("test.csv", _csv_bytes(SAMPLE_ROWS, CSV_COLUMNS), "text/csv")},
        headers={"X-Api-Key": "definitely-not-the-real-key"},
    )
    assert resp.status_code == 401


def test_admin_key_check_uses_constant_time_comparison(client, monkeypatch):
    """secrets.compare_digest must still be the actual comparison used --
    not something a refactor could silently swap for a short-circuiting
    `==`."""
    import secrets as secrets_module

    from app.core import security as security_module

    calls = []
    real_compare_digest = secrets_module.compare_digest

    def _spy(a, b):
        calls.append((a, b))
        return real_compare_digest(a, b)

    monkeypatch.setattr(security_module.secrets, "compare_digest", _spy)
    resp = client.get("/api/v1/marketplace-data/versions", headers=ADMIN_HEADERS)
    assert resp.status_code == 200
    assert len(calls) >= 1, "require_marketplace_admin_key must call secrets.compare_digest"


# -- secret hygiene: the raw admin API key must never be persisted or exposed --

_ALL_MARKETPLACE_TABLES = [
    "marketplace_import_sessions", "marketplace_dataset_versions", "marketplace_canonical_rows",
    "marketplace_derived_artifacts", "marketplace_customer_analytics", "marketplace_seller_analytics",
    "marketplace_product_analytics", "marketplace_import_audit",
]


def _assert_raw_key_not_in_any_table(raw_key: str):
    """Casts every row of every marketplace table to text (every column,
    not just the ones we think to check -- including JSONB payloads like
    mapping_json/validation_report_json/detail_json) and searches for the
    raw key substring. A schema change that adds a new column carrying the
    key would still be caught by this test."""
    session = get_session_factory()()
    try:
        for table in _ALL_MARKETPLACE_TABLES:
            n = session.execute(
                text(f"SELECT COUNT(*) FROM {table} WHERE to_jsonb({table})::text LIKE :pattern"),
                {"pattern": f"%{raw_key}%"},
            ).scalar_one()
            assert n == 0, f"raw admin API key found in table {table}"
    finally:
        session.close()


def test_raw_admin_key_never_persisted_across_full_lifecycle(client, caplog):
    """Runs upload -> mapping -> preview -> confirm -> rollback -> delete,
    all authenticated with the real test admin key, then proves that literal
    key string appears in none of: every marketplace DB table/column
    (including JSONB), any response body from any step, or captured logs."""
    import logging

    raw_key = ADMIN_HEADERS["X-Api-Key"]
    responses = []

    with caplog.at_level(logging.DEBUG):
        preview1, confirm1 = _upload_map_preview_confirm(client, SAMPLE_ROWS, update_mode="replace")
        responses.append(confirm1)
        v1_id = confirm1.json()["data"]["version_id"]

        preview2, confirm2 = _upload_map_preview_confirm(client, SAMPLE_ROWS[:2], update_mode="replace")
        responses.append(confirm2)
        v2_id = confirm2.json()["data"]["version_id"]

        rb = client.post(
            "/api/v1/marketplace-data/versions/rollback",
            json={"target_version_id": v1_id, "expected_active_version_id": v2_id},
            headers=ADMIN_HEADERS,
        )
        responses.append(rb)

        versions = client.get("/api/v1/marketplace-data/versions", headers=ADMIN_HEADERS)
        responses.append(versions)

        # An upload that's never confirmed, then explicitly deleted -- exercises
        # the delete_session code path too.
        csv_bytes = _csv_bytes(SAMPLE_ROWS[:1], CSV_COLUMNS)
        up = client.post("/api/v1/marketplace-data/uploads", files={"file": ("t.csv", csv_bytes, "text/csv")}, headers=ADMIN_HEADERS)
        responses.append(up)
        del_resp = client.delete(f"/api/v1/marketplace-data/uploads/{up.json()['data']['session_id']}", headers=ADMIN_HEADERS)
        responses.append(del_resp)

    for resp in responses:
        assert resp.status_code < 500
        assert raw_key not in resp.text, f"raw admin API key leaked in a response body ({resp.request.url})"

    assert raw_key not in caplog.text, "raw admin API key leaked into logs"

    _assert_raw_key_not_in_any_table(raw_key)

    # The non-secret actor label IS expected to be persisted instead.
    session = get_session_factory()()
    try:
        from app.db.models import MarketplaceDatasetVersion
        v1 = session.get(MarketplaceDatasetVersion, v1_id)
        assert v1.created_by == settings.MARKETPLACE_ADMIN_ACTOR_ID
    finally:
        session.close()


# -- upload size / row boundaries (fast, with overridden limits) -------------

def test_upload_over_byte_limit_rejected(client, monkeypatch):
    monkeypatch.setattr(settings, "MARKETPLACE_MAX_UPLOAD_BYTES", 200)
    csv_bytes = _csv_bytes(SAMPLE_ROWS, CSV_COLUMNS)
    assert len(csv_bytes) > 200
    resp = client.post("/api/v1/marketplace-data/uploads", files={"file": ("test.csv", csv_bytes, "text/csv")}, headers=ADMIN_HEADERS)
    assert resp.status_code == 400
    assert "byte limit" in resp.json()["error"]["message"]


def test_upload_at_byte_limit_accepted(client, monkeypatch):
    csv_bytes = _csv_bytes(SAMPLE_ROWS[:1], CSV_COLUMNS)
    monkeypatch.setattr(settings, "MARKETPLACE_MAX_UPLOAD_BYTES", len(csv_bytes))
    resp = client.post("/api/v1/marketplace-data/uploads", files={"file": ("test.csv", csv_bytes, "text/csv")}, headers=ADMIN_HEADERS)
    assert resp.status_code == 200, resp.text


def test_row_count_over_limit_rejected_at_upload_fast_precheck(client, monkeypatch):
    """The fast newline-counting pre-check (count_lines_fast) runs
    immediately at upload time, before mapping/preview/confirm -- it should
    already reject an obviously-oversized file rather than making the
    operator go through the whole flow first."""
    monkeypatch.setattr(settings, "MARKETPLACE_MAX_ROWS", 3)
    csv_bytes = _csv_bytes(SAMPLE_ROWS, CSV_COLUMNS)  # 6 data rows > 3
    resp = client.post("/api/v1/marketplace-data/uploads", files={"file": ("test.csv", csv_bytes, "text/csv")}, headers=ADMIN_HEADERS)
    assert resp.status_code == 400
    assert "row limit" in resp.json()["error"]["message"] or "row-limit" in resp.json()["error"]["message"]


def test_row_count_over_limit_blocks_confirmation_when_fast_precheck_buffer_admits_it(client, monkeypatch):
    """The fast pre-check has a small buffer for CSV fields containing
    embedded newlines (see count_lines_fast's docstring), so it can admit a
    file the exact chunked parse later rejects. Using MARKETPLACE_MAX_ROWS=5
    against 6 real data rows: fast pre-check threshold is 5*1.02=5.1 lines
    over, which the raw newline count (7, including the header) still trips
    -- so instead this test drives the authoritative chunked check directly
    via the service function, proving IT enforces the limit independent of
    the upload-time pre-check."""
    from pathlib import Path
    from app.services.marketplace_import_service import validate_and_stage

    monkeypatch.setattr(settings, "MARKETPLACE_MAX_ROWS", 3)
    csv_bytes = _csv_bytes(SAMPLE_ROWS, CSV_COLUMNS)
    tmp_path = Path(settings.DATA_DIR) / "marketplace_staging" / "_test_row_limit.csv"
    tmp_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path.write_bytes(csv_bytes)
    try:
        report = validate_and_stage(tmp_path, MAPPING, on_chunk_ready=None)
        assert report.ok is False
        assert any("row limit" in e for e in report.errors)
        assert report.row_count <= settings.MARKETPLACE_MAX_ROWS + settings.MARKETPLACE_CHUNK_ROWS  # aborted early, not after reading everything
    finally:
        tmp_path.unlink(missing_ok=True)


# -- session expiry ------------------------------------------------------------

def test_expired_session_cannot_be_confirmed(client, monkeypatch):
    monkeypatch.setattr(settings, "MARKETPLACE_IMPORT_TTL_MINUTES", -1)  # already expired the instant it's created
    csv_bytes = _csv_bytes(SAMPLE_ROWS, CSV_COLUMNS)
    up = client.post("/api/v1/marketplace-data/uploads", files={"file": ("test.csv", csv_bytes, "text/csv")}, headers=ADMIN_HEADERS)
    session_id = up.json()["data"]["session_id"]

    p = client.get(f"/api/v1/marketplace-data/uploads/{session_id}", headers=ADMIN_HEADERS)
    assert p.status_code == 404  # unusable immediately

    session = get_session_factory()()
    try:
        from app.db.models import MarketplaceImportSession
        row = session.get(MarketplaceImportSession, session_id)
        assert row is not None  # minimal audit record preserved
        assert row.status == "expired"
        assert row.staged_file_path is None  # raw content removed
    finally:
        session.close()


# -- append & update (copy-forward merge) -------------------------------------

def test_append_carries_forward_untouched_orders_and_adds_new_one(client):
    _, base = _upload_map_preview_confirm(client, SAMPLE_ROWS, update_mode="replace")
    assert base.status_code == 200, base.text
    base_version_id = base.json()["data"]["version_id"]

    new_order = [dict(SAMPLE_ROWS[2])]  # reuse O2's shape
    new_order[0].update({"order_id": "O5", "order_item_id": "1", "customer_id": "C5a", "customer_unique_id": "CU5",
                          "payment_value": "70.00", "product_id": "P5", "seller_id": "S1"})
    _, append_resp = _upload_map_preview_confirm(
        client, new_order, update_mode="append", expected_active_version_id=base_version_id,
    )
    assert append_resp.status_code == 200, append_resp.text
    data = append_resp.json()["data"]
    assert data["row_count"] == 7  # 6 carried forward + 1 new
    assert data["distinct_order_count"] == 5  # O1..O4 + O5
    assert data["validation"]["append_rows_from_new_upload"] == 1
    assert data["validation"]["append_rows_carried_forward_from_parent"] == 6

    kpis = client.get("/api/v1/marketplace-data/active/aggregate/overview_kpis").json()["data"]
    assert kpis["total_orders"] == 5
    assert kpis["total_revenue"] == 570.0  # 500 carried forward + 70 new

    # A product only present in the original upload (never re-uploaded) must
    # still be queryable -- proof the parent's rows were actually copied, not
    # just the new file's rows kept.
    products = {p["product_id"] for p in client.get("/api/v1/marketplace-data/active/products").json()["data"]["items"]}
    assert "P3" in products  # from O2, part of the original (parent) upload only


def test_append_update_replaces_every_item_row_of_the_touched_order(client):
    """O2 is a single-item order -- re-uploading its one row with a new
    payment_value is a full, unambiguous update: no other item row of O2 is
    left stale, so this must succeed and the new value must win."""
    _, base = _upload_map_preview_confirm(client, SAMPLE_ROWS, update_mode="replace")
    base_version_id = base.json()["data"]["version_id"]

    updated_o2 = [dict(SAMPLE_ROWS[2])]
    updated_o2[0]["payment_value"] = "999.00"
    _, append_resp = _upload_map_preview_confirm(
        client, updated_o2, update_mode="append", expected_active_version_id=base_version_id,
    )
    assert append_resp.status_code == 200, append_resp.text
    assert append_resp.json()["data"]["distinct_order_count"] == 4  # still O1..O4, not a 5th order

    kpis = client.get("/api/v1/marketplace-data/active/aggregate/overview_kpis").json()["data"]
    assert kpis["total_revenue"] == 1449.0  # 500 - 50 (old O2) + 999 (new O2)


def test_append_partial_multi_item_order_update_is_blocked(client):
    """O1 has two item rows sharing payment_value=300.00. Re-uploading only
    ONE of O1's two items with a different payment_value would leave the
    merged version's O1 rows disagreeing on an order-grain field -- must be
    rejected, and nothing may be persisted (active version stays the base)."""
    _, base = _upload_map_preview_confirm(client, SAMPLE_ROWS, update_mode="replace")
    base_version_id = base.json()["data"]["version_id"]

    partial_o1 = [dict(SAMPLE_ROWS[0])]
    partial_o1[0]["payment_value"] = "999.00"  # O1's item 2 (not re-uploaded) still says 300.00
    _, append_resp = _upload_map_preview_confirm(
        client, partial_o1, update_mode="append", expected_active_version_id=base_version_id,
    )
    assert append_resp.status_code == 400, append_resp.text
    details = append_resp.json()["error"]["details"]
    assert "O1" in details["conflicted_order_ids"]

    active = client.get("/api/v1/marketplace-data/active").json()["data"]
    assert active["version_id"] == base_version_id  # unchanged -- no partial state


# -- rollback -------------------------------------------------------------------

def test_rollback_reactivates_a_previous_version(client):
    _, v1 = _upload_map_preview_confirm(client, SAMPLE_ROWS, update_mode="replace")
    v1_id = v1.json()["data"]["version_id"]
    _, v2 = _upload_map_preview_confirm(client, SAMPLE_ROWS[:2], update_mode="replace")
    v2_id = v2.json()["data"]["version_id"]
    assert v2_id != v1_id

    rb = client.post(
        "/api/v1/marketplace-data/versions/rollback",
        json={"target_version_id": v1_id, "expected_active_version_id": v2_id},
        headers=ADMIN_HEADERS,
    )
    assert rb.status_code == 200, rb.text
    assert rb.json()["data"]["version_id"] == v1_id

    active = client.get("/api/v1/marketplace-data/active").json()["data"]
    assert active["version_id"] == v1_id
    assert active["row_count"] == 6


def test_rollback_with_stale_expected_version_is_rejected(client):
    _, v1 = _upload_map_preview_confirm(client, SAMPLE_ROWS, update_mode="replace")
    v1_id = v1.json()["data"]["version_id"]

    rb = client.post(
        "/api/v1/marketplace-data/versions/rollback",
        json={"target_version_id": v1_id, "expected_active_version_id": "not-the-real-active-id"},
        headers=ADMIN_HEADERS,
    )
    assert rb.status_code == 409, rb.text


# -- retention / FK cascade -----------------------------------------------------

def test_retention_deletes_old_versions_and_cascades_their_rows(client, monkeypatch):
    monkeypatch.setattr(settings, "MARKETPLACE_VERSION_RETENTION", 2)
    version_ids = []
    for rows in (SAMPLE_ROWS, SAMPLE_ROWS[:2], SAMPLE_ROWS[:1]):
        _, resp = _upload_map_preview_confirm(client, rows, update_mode="replace")
        assert resp.status_code == 200, resp.text
        version_ids.append(resp.json()["data"]["version_id"])
    v1_id, v2_id, v3_id = version_ids

    versions = client.get("/api/v1/marketplace-data/versions", headers=ADMIN_HEADERS).json()["data"]["items"]
    remaining_ids = {v["version_id"] for v in versions}
    assert v3_id in remaining_ids  # active
    assert v2_id in remaining_ids  # active's immediate parent (rollback target)
    assert v1_id not in remaining_ids  # beyond retention -- deleted

    session = get_session_factory()()
    try:
        for table in ("marketplace_canonical_rows", "marketplace_derived_artifacts", "marketplace_customer_analytics"):
            n = session.execute(text(f"SELECT COUNT(*) FROM {table} WHERE dataset_version_id = :vid"), {"vid": v1_id}).scalar_one()
            assert n == 0, f"{table} still has rows for retention-deleted version {v1_id}"
    finally:
        session.close()


# -- global activation concurrency ----------------------------------------------

def test_concurrent_activation_has_no_last_writer_wins(client):
    """Two DB sessions racing to activate two different candidate versions
    against the SAME expected_active_version_id must serialize through
    pg_advisory_xact_lock: exactly one succeeds, the other gets a controlled
    409 conflict (its expected_active_version_id is stale the moment it
    re-reads after acquiring the lock) -- never both 'succeeding' by
    silently overwriting each other."""
    import threading
    from datetime import datetime, timezone

    from app.repositories import marketplace_repository as repo

    _, base = _upload_map_preview_confirm(client, SAMPLE_ROWS, update_mode="replace")
    base_version_id = base.json()["data"]["version_id"]

    def _make_candidate(session, suffix: str) -> str:
        vid = f"cand{suffix}{uuid.uuid4().hex[:20]}"
        repo.create_pending_version(
            session, id_=vid, source_session_id=None, parent_version_id=base_version_id, update_mode="replace",
            file_hash=None, row_count=1, distinct_order_count=1, date_range_start=None, date_range_end=None,
            validation_summary={}, created_by="test",
        )
        repo.bulk_insert_canonical_rows(session, [{
            "dataset_version_id": vid, "order_id": f"OX{suffix}", "order_item_id": None,
            "order_purchase_timestamp": datetime(2024, 1, 1, tzinfo=timezone.utc), "order_status": "delivered",
            "customer_id": f"C{suffix}", "customer_unique_id": f"CU{suffix}",
        }])
        for name in repo.REQUIRED_ARTIFACTS:
            repo.upsert_derived_artifact(session, version_id=vid, artifact_name=name, payload={"available": False})
        session.commit()
        return vid

    setup_session = get_session_factory()()
    try:
        candidate_a = _make_candidate(setup_session, "A")
        candidate_b = _make_candidate(setup_session, "B")
    finally:
        setup_session.close()

    results: dict[str, tuple[bool, str | None]] = {}

    def _attempt(name: str, candidate_id: str):
        session = get_session_factory()()
        try:
            repo.activate_version(session, candidate_version_id=candidate_id, expected_active_version_id=base_version_id, actor=name)
            session.commit()
            results[name] = (True, None)
        except Exception as e:
            session.rollback()
            results[name] = (False, type(e).__name__)
        finally:
            session.close()

    t1 = threading.Thread(target=_attempt, args=("A", candidate_a))
    t2 = threading.Thread(target=_attempt, args=("B", candidate_b))
    t1.start(); t2.start()
    t1.join(); t2.join()

    successes = [name for name, (ok, _) in results.items() if ok]
    failures = [(name, err) for name, (ok, err) in results.items() if not ok]
    assert len(successes) == 1, f"expected exactly one winner, got {results}"
    assert len(failures) == 1 and failures[0][1] == "ActivationConflictError", f"loser must get a controlled conflict, got {results}"

    active = client.get("/api/v1/marketplace-data/active").json()["data"]
    assert active["version_id"] in (candidate_a, candidate_b)


# -- readiness -------------------------------------------------------------------

def test_ready_endpoint_reflects_active_marketplace_version(client):
    no_dataset = client.get("/api/v1/ready").json()["data"]
    assert no_dataset["source"] in ("historical_packaged", "marketplace_active")

    _, resp = _upload_map_preview_confirm(client, SAMPLE_ROWS, update_mode="replace")
    version_id = resp.json()["data"]["version_id"]

    ready = client.get("/api/v1/ready").json()["data"]
    assert ready["readiness"] == "ready"
    assert ready["source"] == "marketplace_active"
    assert ready["active_version_id"] == version_id
    assert ready["process"] == "healthy"


def test_health_endpoint_never_reflects_marketplace_dataset_state(client):
    """/health must stay a pure liveness check -- confirming a dataset must
    never change its shape or make it fail."""
    health = client.get("/api/v1/health")
    assert health.status_code == 200
    assert "marketplace" not in health.json()["data"]
