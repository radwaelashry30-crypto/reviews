"""SQLAlchemy ORM models for the optional persistence layer.

Scope note: this project has no authentication, no user accounts, and no
"create/edit review" journey anywhere -- the Olist orders/customers/reviews
data is a static analytics dataset (parquet/JSON), not something users CRUD.
So there are deliberately no Users/Orders/Products/Auth tables here. The one
genuine persistence gap this fills: AI predictions from /predict, /pipeline,
and /explain were never saved at all, and batch-upload results
(upload_store.py) were saved as local JSON files that don't survive a
redeploy on Render's ephemeral disk. This layer covers exactly that.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    JSON, Boolean, DateTime, Float, ForeignKey, Index, Integer, Numeric, SmallInteger, String, Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def _new_id() -> str:
    """32-char hex id, matching the format upload_store.py already used
    (uuid.uuid4().hex) -- keeps the upload_id API contract unchanged."""
    return uuid.uuid4().hex


class SentimentAnalysis(Base):
    __tablename__ = "sentiment_analyses"
    __table_args__ = (UniqueConstraint("idempotency_key", name="ux_analyses_idempotency_key"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_new_id)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    cleaned_text: Mapped[str] = mapped_column(Text, nullable=False)
    label: Mapped[str] = mapped_column(String(16), nullable=False)
    class_id: Mapped[int] = mapped_column(Integer, nullable=False)
    probability_positive: Mapped[float] = mapped_column(Float, nullable=False)
    probability_negative: Mapped[float] = mapped_column(Float, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    model_name: Mapped[str] = mapped_column(String(16), nullable=False)
    source_language: Mapped[str] = mapped_column(String(8), nullable=False)
    translated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Client-supplied (Idempotency-Key header on POST /predict) so a client
    # retry after a timeout -- where the server actually finished the write
    # but the response never made it back -- replays the saved result
    # instead of creating a second history row for the same logical request.
    # Nullable + unique: most callers won't send one, and NULLs don't
    # collide under a unique constraint in Postgres/SQLite.
    idempotency_key: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    aspects: Mapped[list["SentimentAnalysisAspect"]] = relationship(back_populates="analysis", cascade="all, delete-orphan")
    feedback: Mapped[list["PredictionFeedback"]] = relationship(back_populates="analysis", cascade="all, delete-orphan")


class SentimentAnalysisAspect(Base):
    __tablename__ = "sentiment_analysis_aspects"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_new_id)
    analysis_id: Mapped[str] = mapped_column(String(32), ForeignKey("sentiment_analyses.id", ondelete="CASCADE"), nullable=False, index=True)
    aspect: Mapped[str] = mapped_column(String(64), nullable=False)
    sentiment: Mapped[str] = mapped_column(String(16), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)

    analysis: Mapped["SentimentAnalysis"] = relationship(back_populates="aspects")


class PredictionFeedback(Base):
    """User-supplied thumbs-up/down on a prediction. Not tied to any account
    (this project has none) -- purely a signal for later review."""
    __tablename__ = "prediction_feedback"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_new_id)
    analysis_id: Mapped[str] = mapped_column(String(32), ForeignKey("sentiment_analyses.id", ondelete="CASCADE"), nullable=False, index=True)
    is_correct: Mapped[bool] = mapped_column(Boolean, nullable=False)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    analysis: Mapped["SentimentAnalysis"] = relationship(back_populates="feedback")


class BatchUploadJob(Base):
    """Durable replacement for upload_store.py's JSON-file records. Stores
    the full classify_review_file() result as JSON rather than fully
    normalizing every row into its own table -- this project's actual
    documented pain point is "results vanish on redeploy," not "we need to
    filter/query individual rows across uploads," so a JSON blob per job is
    the smallest change that fixes the real problem."""
    __tablename__ = "batch_upload_jobs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_new_id)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    model_name: Mapped[str] = mapped_column(String(16), nullable=False)
    text_column_used: Mapped[str] = mapped_column(String(128), nullable=False)
    rows_processed: Mapped[int] = mapped_column(Integer, nullable=False)
    n_positive: Mapped[int] = mapped_column(Integer, nullable=False)
    n_negative: Mapped[int] = mapped_column(Integer, nullable=False)
    result_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)


# ============================================================================
# Marketplace CSV data management (Checkpoint C). PostgreSQL-only: uses
# JSONB and a partial unique index (postgresql_where=...) that only compiles
# against the postgresql dialect. See app/db/marketplace_base.py::
# require_postgres() -- callers must confirm a real Postgres DATABASE_URL
# before touching any table below; the SQLite dev.db fallback used for the
# tables above does NOT support this feature.
#
# Canonical grain: one row per order item, with item-less orders (canceled/
# unavailable before fulfillment) kept as exactly one row with null item
# fields -- see Checkpoint A's reconciliation (775 item-less orders in the
# historical dataset; omitting them undercounts orders by that many).
# ============================================================================


class MarketplaceImportSession(Base):
    """One uploaded file, in progress toward becoming a dataset version.
    Deleted (raw staged content) or expired well before it could ever be
    confirmed as an active version -- see MARKETPLACE_IMPORT_TTL_MINUTES."""
    __tablename__ = "marketplace_import_sessions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_new_id)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)  # sha256 hex
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    # 'uploaded' -> 'mapped' -> 'previewed' -> 'confirmed' | 'expired' | 'deleted'
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="uploaded")
    update_mode: Mapped[str | None] = mapped_column(String(16), nullable=True)  # 'append' | 'replace'
    mapping_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    grain_report_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    validation_report_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    row_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Path to the bounded temp staging file on local disk, cleared (set NULL)
    # the moment the session is confirmed, expired, or deleted -- never kept
    # around longer than necessary, never committed/logged with real content.
    staged_file_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    created_by: Mapped[str | None] = mapped_column(String(128), nullable=True)

    __table_args__ = (
        Index("ix_import_sessions_status", "status"),
    )


class MarketplaceDatasetVersion(Base):
    """One complete, atomically-activatable snapshot of marketplace data.
    At most one row may have is_active=true at any time -- enforced by the
    partial unique index below, backed by the transaction-scoped advisory
    lock in marketplace_version_service.py (the index alone is a backstop,
    not the sole guarantee -- see that module's docstring)."""
    __tablename__ = "marketplace_dataset_versions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_new_id)
    source_session_id: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("marketplace_import_sessions.id", ondelete="RESTRICT"), nullable=True,
    )
    # SET NULL, not RESTRICT: retention (retire_eligible_versions) deletes
    # versions beyond the retention window while always keeping the active
    # version and its immediate parent -- the oldest RETAINED version's own
    # parent_version_id necessarily still points at an older version that IS
    # being deleted. RESTRICT would make every retention pass beyond depth 2
    # fail with a foreign-key violation; SET NULL just truncates the lineage
    # pointer once its target is gone, same pattern as MarketplaceImportAudit
    # below.
    parent_version_id: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("marketplace_dataset_versions.id", ondelete="SET NULL"), nullable=True,
    )
    update_mode: Mapped[str] = mapped_column(String(16), nullable=False)  # 'append' | 'replace' | 'seed'
    file_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    row_count: Mapped[int] = mapped_column(Integer, nullable=False)
    distinct_order_count: Mapped[int] = mapped_column(Integer, nullable=False)
    date_range_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    date_range_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    validation_summary_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False, index=True)
    created_by: Mapped[str | None] = mapped_column(String(128), nullable=True)

    __table_args__ = (
        Index(
            "ux_marketplace_one_active_version", "is_active",
            unique=True, postgresql_where=(is_active == True),  # noqa: E712
        ),
    )


class MarketplaceCanonicalRow(Base):
    """Source-of-truth canonical rows for one dataset version. Deleted
    (CASCADE) automatically when its owning version is retired by retention
    -- these rows belong exclusively to one version, unlike audit history."""
    __tablename__ = "marketplace_canonical_rows"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dataset_version_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("marketplace_dataset_versions.id", ondelete="CASCADE"), nullable=False,
    )
    order_id: Mapped[str] = mapped_column(String(64), nullable=False)
    order_item_id: Mapped[int | None] = mapped_column(Integer, nullable=True)  # NULL = item-less order row
    order_purchase_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    order_delivered_customer_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    order_estimated_delivery_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    order_status: Mapped[str] = mapped_column(String(32), nullable=False)
    customer_id: Mapped[str] = mapped_column(String(64), nullable=False)
    customer_unique_id: Mapped[str] = mapped_column(String(64), nullable=False)
    customer_city: Mapped[str | None] = mapped_column(String(128), nullable=True)
    customer_state: Mapped[str | None] = mapped_column(String(8), nullable=True)
    payment_value: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    main_payment_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    payment_installments: Mapped[int | None] = mapped_column(Integer, nullable=True)
    review_score: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    review_comment_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    seller_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    product_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    product_category_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    price: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    freight_value: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    seller_city: Mapped[str | None] = mapped_column(String(128), nullable=True)
    seller_state: Mapped[str | None] = mapped_column(String(8), nullable=True)

    __table_args__ = (
        Index(
            "ux_canonical_item_key", "dataset_version_id", "order_id", "order_item_id",
            unique=True, postgresql_nulls_not_distinct=True,
        ),
        Index("ix_canonical_version_order", "dataset_version_id", "order_id"),
        Index(
            "ix_canonical_version_seller", "dataset_version_id", "seller_id",
            postgresql_where=(seller_id.isnot(None)),
        ),
        Index(
            "ix_canonical_version_product", "dataset_version_id", "product_id",
            postgresql_where=(product_id.isnot(None)),
        ),
    )


class MarketplaceDerivedArtifact(Base):
    """Small, chart-ready aggregate payloads (Overview KPIs, monthly trends,
    review/payment distribution, RFM segment summary, availability matrix,
    dataset metadata) -- deliberately NOT where Customer/Seller/Product
    entity rows live (see the typed tables below); those are ~96,000+ rows
    and belong in queryable/paginable tables, not one large JSON blob."""
    __tablename__ = "marketplace_derived_artifacts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dataset_version_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("marketplace_dataset_versions.id", ondelete="CASCADE"), nullable=False,
    )
    artifact_name: Mapped[str] = mapped_column(String(64), nullable=False)
    payload_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    schema_version: Mapped[str] = mapped_column(String(16), nullable=False, default="1.0")
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("dataset_version_id", "artifact_name", name="ux_one_artifact_per_version"),
    )


class MarketplaceCustomerAnalytics(Base):
    """One row per customer_unique_id per dataset version -- queried through
    a paginated repository endpoint, never loaded whole into memory or sent
    to the frontend in one response (see Checkpoint B correction #3)."""
    __tablename__ = "marketplace_customer_analytics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dataset_version_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("marketplace_dataset_versions.id", ondelete="CASCADE"), nullable=False,
    )
    customer_unique_id: Mapped[str] = mapped_column(String(64), nullable=False)
    order_count: Mapped[int] = mapped_column(Integer, nullable=False)
    total_spend: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    average_order_value: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    first_order_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_order_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    recency: Mapped[float | None] = mapped_column(Float, nullable=True)
    frequency: Mapped[float | None] = mapped_column(Float, nullable=True)
    monetary: Mapped[float | None] = mapped_column(Float, nullable=True)
    rfm_segment: Mapped[str | None] = mapped_column(String(64), nullable=True)
    rfm_out_of_distribution: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    customer_city: Mapped[str | None] = mapped_column(String(128), nullable=True)
    customer_state: Mapped[str | None] = mapped_column(String(8), nullable=True)

    __table_args__ = (
        UniqueConstraint("dataset_version_id", "customer_unique_id", name="ux_customer_analytics_key"),
        Index("ix_customer_analytics_version_spend", "dataset_version_id", "total_spend"),
        Index("ix_customer_analytics_version_segment", "dataset_version_id", "rfm_segment"),
    )


class MarketplaceSellerAnalytics(Base):
    """One row per seller_id per dataset version."""
    __tablename__ = "marketplace_seller_analytics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dataset_version_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("marketplace_dataset_versions.id", ondelete="CASCADE"), nullable=False,
    )
    seller_id: Mapped[str] = mapped_column(String(64), nullable=False)
    order_count: Mapped[int] = mapped_column(Integer, nullable=False)
    item_count: Mapped[int] = mapped_column(Integer, nullable=False)
    item_revenue: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    average_item_value: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    late_delivery_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    product_count: Mapped[int] = mapped_column(Integer, nullable=False)
    category_count: Mapped[int] = mapped_column(Integer, nullable=False)
    seller_city: Mapped[str | None] = mapped_column(String(128), nullable=True)
    seller_state: Mapped[str | None] = mapped_column(String(8), nullable=True)

    __table_args__ = (
        UniqueConstraint("dataset_version_id", "seller_id", name="ux_seller_analytics_key"),
        Index("ix_seller_analytics_version_revenue", "dataset_version_id", "item_revenue"),
        Index("ix_seller_analytics_version_late", "dataset_version_id", "late_delivery_rate"),
    )


class MarketplaceProductAnalytics(Base):
    """One row per (product_id, product_category_name) per dataset version.

    associated_single_category_order_review_average is intentionally NOT
    named 'product review score' -- see Checkpoint B correction #5. It is
    the mean review_score of orders that (a) contained this product and (b)
    were single-category orders, i.e. review attribution to this product's
    category is unambiguous. associated_review_excluded_order_count records
    how many of this product's orders were excluded (multi-category or
    item-less) so the limitation is always visible alongside the number."""
    __tablename__ = "marketplace_product_analytics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dataset_version_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("marketplace_dataset_versions.id", ondelete="CASCADE"), nullable=False,
    )
    product_id: Mapped[str] = mapped_column(String(64), nullable=False)
    product_category_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    item_count: Mapped[int] = mapped_column(Integer, nullable=False)
    item_revenue: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    average_item_price: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    freight_value: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    associated_single_category_order_review_average: Mapped[float | None] = mapped_column(Float, nullable=True)
    associated_review_order_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    associated_review_excluded_order_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    __table_args__ = (
        UniqueConstraint("dataset_version_id", "product_id", name="ux_product_analytics_key"),
        Index("ix_product_analytics_version_revenue", "dataset_version_id", "item_revenue"),
        Index("ix_product_analytics_version_category", "dataset_version_id", "product_category_name"),
    )


class MarketplaceImportAudit(Base):
    """Append-only event log. Never cascade-deleted by version retention --
    session_id/version_id are SET NULL if their target is later removed, so
    the audit trail itself always survives."""
    __tablename__ = "marketplace_import_audit"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    session_id: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("marketplace_import_sessions.id", ondelete="SET NULL"), nullable=True,
    )
    version_id: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("marketplace_dataset_versions.id", ondelete="SET NULL"), nullable=True,
    )
    actor: Mapped[str | None] = mapped_column(String(128), nullable=True)
    detail_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False, index=True)
