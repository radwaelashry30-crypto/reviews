from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, Path, Query, Request, UploadFile
from starlette.concurrency import run_in_threadpool

from app.core.exceptions import InvalidRequestError, ResourceNotFoundError
from app.core.rate_limit import limiter
from app.db.base import db_configured
from app.dependencies import get_model_registry
from app.schemas.common import envelope
from app.schemas.sentiment import (
    BatchPredictionRequest, ExplainRequest, FeedbackRequest, FullPipelineRequest, ModelName, SentimentPredictionRequest,
)
from app.services import advanced_sentiment_service, file_batch_service, persistence_service, sentiment_service, upload_store
from app.services.model_registry import ModelRegistry

router = APIRouter(prefix="/sentiment", tags=["sentiment"])

# Read uploads in bounded chunks rather than a single `await file.read()` --
# an unbounded read buffers the entire request body in memory before
# file_batch_service.MAX_FILE_ROWS ever gets a chance to truncate it, which on
# a 512MB deployment is a real resource-exhaustion vector for a large/malicious
# upload. 5MB comfortably covers 2,000 rows of review text (the app's own
# row cap) with headroom.
MAX_UPLOAD_BYTES = 5 * 1024 * 1024
_UPLOAD_CHUNK_SIZE = 1024 * 1024


async def _read_upload_bounded(file: UploadFile, max_bytes: int = MAX_UPLOAD_BYTES) -> bytes:
    """Reads `file` in chunks, aborting before buffering more than `max_bytes`."""
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(_UPLOAD_CHUNK_SIZE)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise InvalidRequestError(
                f"Uploaded file exceeds the {max_bytes // (1024 * 1024)}MB limit."
            )
        chunks.append(chunk)
    return b"".join(chunks)


@router.post("/predict")
@limiter.limit("30/minute")
def predict(request: Request, payload: SentimentPredictionRequest, registry: ModelRegistry = Depends(get_model_registry)):
    result = sentiment_service.predict_sentiment(
        registry, payload.text, model_name=payload.model_name,
        source_language=payload.source_language, translate=payload.translate,
    )
    analysis_id = persistence_service.try_save_analysis(payload.text, result)
    return envelope({**result, "analysis_id": analysis_id}, model_version=payload.model_name)


@router.post("/predict-batch")
@limiter.limit("15/minute")
def predict_batch(request: Request, payload: BatchPredictionRequest, registry: ModelRegistry = Depends(get_model_registry)):
    items = [{"id": item.id, "text": item.text} for item in payload.items]
    results = sentiment_service.predict_sentiment_batch(registry, items, model_name=payload.model_name)
    return envelope({"results": results, "n_items": len(results)}, model_version=payload.model_name)


@router.post("/pipeline")
@limiter.limit("20/minute")
def full_pipeline(request: Request, payload: FullPipelineRequest, registry: ModelRegistry = Depends(get_model_registry)):
    """Task 1 (sentiment) -> Task 2 (fake-vs-real, only if Negative) -> Task 3 (aspects, always).

    Task 2/3 depend on large external models (256MB / 706MB) not loaded at
    startup. On a RAM-constrained deployment they report
    `"available": false` inside their own result object rather than failing
    the whole request -- Task 1's sentiment result is always returned.
    """
    result = advanced_sentiment_service.run_full_pipeline(
        registry, payload.text, model_name=payload.model_name,
        source_language=payload.source_language, translate=payload.translate,
        aspects=payload.aspects,
    )
    aspects_for_db = result["aspects"]["aspects"] if result["aspects"].get("available") else None
    analysis_id = persistence_service.try_save_analysis(payload.text, result["sentiment"], aspects_for_db)
    return envelope({**result, "analysis_id": analysis_id}, model_version=payload.model_name)


@router.post("/explain")
@limiter.limit("10/minute")
def explain(request: Request, payload: ExplainRequest, registry: ModelRegistry = Depends(get_model_registry)):
    """SHAP token-level explanation for the fine-tuned BERT model (BERT only --
    CNN2D's embeddings aren't set up for SHAP's text masker). Explains the
    exact text the caller submits; not restricted to the stored test split
    (that restriction applies only to the audit/reproduction script)."""
    from app.ml.explainability import explain_single_review

    if registry.bert_model is None:
        return envelope({"available": False, "reason": "BERT model not available on this deployment"})

    explainer = registry.get_shap_explainer()
    if explainer is None:
        status = registry.statuses.get("shap")
        return envelope({"available": False, "reason": status.error if status else "not available"})

    result = explain_single_review(explainer, registry.bert_model, payload.text)
    return envelope(result, model_version="bert")


@router.post("/upload-file")
@limiter.limit("10/minute")
async def upload_file(
    request: Request,
    file: UploadFile = File(...),
    model_name: ModelName = Form("bert"),
    advanced: bool = Form(False),
    registry: ModelRegistry = Depends(get_model_registry),
):
    """Batch-classify every review row in an uploaded CSV/XLSX file.

    Auto-detects the review-text column (see file_batch_service.TEXT_COLUMN_CANDIDATES).
    Processes synchronously, capped at file_batch_service.MAX_FILE_ROWS rows.

    `advanced=true` additionally runs fake-review screening and aspect-based
    sentiment over a bounded sample of rows (file_batch_service.ADVANCED_SAMPLE_SIZE)
    -- slower, so it's opt-in rather than the default.
    """
    if not file.filename or not file.filename.lower().endswith((".csv", ".xlsx", ".xls")):
        raise InvalidRequestError("Upload a .csv or .xlsx file.")

    content = await _read_upload_bounded(file)
    if not content:
        raise InvalidRequestError("The uploaded file is empty.")

    # classify_review_file is synchronous and CPU-heavy (up to 2,000 BERT
    # forward passes) -- calling it directly here would block this async
    # endpoint's event loop for minutes, stalling every other request on the
    # process (including /health) until it returns. run_in_threadpool moves
    # it off the event loop onto FastAPI's worker thread pool instead.
    result = await run_in_threadpool(
        file_batch_service.classify_review_file, registry, file.filename, content,
        model_name=model_name, advanced=advanced,
    )
    upload_id = upload_store.save_upload_result(result)
    return envelope({**result, "upload_id": upload_id, "retention_days": upload_store.RETENTION_DAYS}, model_version=model_name)


UPLOAD_ID_PATTERN = r"^[0-9a-f]{32}$"  # uuid4().hex, exactly -- nothing else


@router.get("/upload-file/{upload_id}")
def get_uploaded_result(upload_id: str = Path(..., pattern=UPLOAD_ID_PATTERN)):
    """Retrieves a previously classified file's results (kept for 7 days), so
    reloading the page or coming back later doesn't require re-uploading."""
    saved = upload_store.load_upload_result(upload_id)
    if saved is None:
        raise ResourceNotFoundError(f"No saved upload found for id '{upload_id}' (not found, or its 7-day retention expired).")
    return envelope({**saved["result"], "upload_id": saved["upload_id"], "created_at": saved["created_at"], "expires_at": saved["expires_at"]})


def _require_db():
    """Endpoints that are explicitly about DB-backed history should fail
    clearly (503) rather than silently return empty results when no
    database is configured -- unlike /predict and /pipeline, which persist
    best-effort and always return a prediction regardless."""
    if not db_configured():
        from app.core.exceptions import ModelUnavailableError

        raise ModelUnavailableError("Analysis history is not available: no database is configured on this deployment.")


def _analysis_to_dict(row) -> dict:
    return {
        "analysis_id": row.id,
        "text": row.text,
        "cleaned_text": row.cleaned_text,
        "label": row.label,
        "class_id": row.class_id,
        "probability_positive": row.probability_positive,
        "probability_negative": row.probability_negative,
        "confidence": row.confidence,
        "model_name": row.model_name,
        "source_language": row.source_language,
        "translated": row.translated,
        "created_at": row.created_at.isoformat(),
        "aspects": [{"aspect": a.aspect, "sentiment": a.sentiment, "confidence": a.confidence} for a in row.aspects],
    }


@router.get("/analyses")
def list_analyses(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    label: str | None = Query(None, pattern="^(Positive|Negative)$"),
    model_name: ModelName | None = None,
):
    """Paginated history of persisted /predict and /pipeline analyses. 503 if
    no database is configured on this deployment (see DATABASE_SETUP.md)."""
    _require_db()
    from app.db.base import get_session_factory
    from app.repositories import sentiment_repository

    session = get_session_factory()()
    try:
        rows, total = sentiment_repository.list_analyses(session, limit=limit, offset=offset, label=label, model_name=model_name)
        return envelope({"items": [_analysis_to_dict(r) for r in rows], "total": total, "limit": limit, "offset": offset})
    finally:
        session.close()


@router.get("/analyses/{analysis_id}")
def get_analysis(analysis_id: str):
    _require_db()
    from app.db.base import get_session_factory
    from app.repositories import sentiment_repository

    session = get_session_factory()()
    try:
        row = sentiment_repository.get_analysis(session, analysis_id)
        if row is None:
            raise ResourceNotFoundError(f"No saved analysis found for id '{analysis_id}'.")
        return envelope(_analysis_to_dict(row))
    finally:
        session.close()


@router.post("/analyses/{analysis_id}/feedback")
@limiter.limit("30/minute")
def submit_feedback(request: Request, analysis_id: str, payload: FeedbackRequest):
    """Thumbs-up/down on a saved prediction. Anonymous -- this project has no
    user accounts."""
    _require_db()
    from app.db.base import get_session_factory
    from app.repositories import sentiment_repository

    session = get_session_factory()()
    try:
        row = sentiment_repository.save_feedback(session, analysis_id=analysis_id, is_correct=payload.is_correct, comment=payload.comment)
        if row is None:
            raise ResourceNotFoundError(f"No saved analysis found for id '{analysis_id}'.")
        return envelope({"feedback_id": row.id, "analysis_id": row.analysis_id, "is_correct": row.is_correct})
    finally:
        session.close()
