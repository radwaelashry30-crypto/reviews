"""CSV/Excel review-file upload: parse, auto-detect the review-text column,
classify every row with the chosen sentiment model, return per-row results
plus a summary. Runs synchronously (no task queue) -- bounded by
MAX_FILE_ROWS so a very large upload doesn't block the server indefinitely.
"""
from __future__ import annotations

import io

import pandas as pd

from app.core.config import settings
from app.core.exceptions import InvalidRequestError
from app.services import sentiment_service
from app.services.model_registry import ModelRegistry

MAX_FILE_ROWS = 2000

# Checked in order; first match wins. Covers this project's own Olist-style
# columns (review_comment_message_en, review_comment_message) as well as
# common generic names, so an arbitrary review export just works.
TEXT_COLUMN_CANDIDATES = [
    "review_comment_message_en",
    "review_comment_message",
    "review_text",
    "text",
    "review",
    "comment",
    "comments",
    "message",
]


def _detect_text_column(df: pd.DataFrame) -> str:
    lower_map = {c.lower(): c for c in df.columns}
    for candidate in TEXT_COLUMN_CANDIDATES:
        if candidate in lower_map:
            return lower_map[candidate]
    # Fall back to the first column with object/string dtype and non-trivial average length.
    for col in df.columns:
        if df[col].dtype == object:
            sample = df[col].dropna().astype(str).head(20)
            if len(sample) and sample.str.len().mean() > 15:
                return col
    raise InvalidRequestError(
        "Could not find a review-text column. Expected one of: "
        f"{', '.join(TEXT_COLUMN_CANDIDATES)}, or any text column with reasonably long values.",
        details={"columns_found": list(df.columns)},
    )


def parse_review_file(filename: str, content: bytes) -> pd.DataFrame:
    lower = filename.lower()
    try:
        if lower.endswith(".csv"):
            df = pd.read_csv(io.BytesIO(content))
        elif lower.endswith((".xlsx", ".xls")):
            df = pd.read_excel(io.BytesIO(content))
        else:
            raise InvalidRequestError("Unsupported file type. Upload a .csv or .xlsx file.")
    except InvalidRequestError:
        raise
    except Exception as e:
        raise InvalidRequestError(f"Could not parse the uploaded file: {e}") from e

    if df.empty:
        raise InvalidRequestError("The uploaded file has no rows.")
    return df


def classify_review_file(
    registry: ModelRegistry, filename: str, content: bytes, model_name: str = "bert",
) -> dict:
    df = parse_review_file(filename, content)
    text_col = _detect_text_column(df)

    total_rows = len(df)
    if total_rows > MAX_FILE_ROWS:
        df = df.head(MAX_FILE_ROWS)
    truncated = total_rows > MAX_FILE_ROWS

    texts = df[text_col].fillna("").astype(str)
    valid_mask = texts.str.strip() != ""
    valid_indices = df.index[valid_mask].tolist()

    results = []
    n_positive = 0
    n_negative = 0
    n_skipped = int((~valid_mask).sum())

    for idx in valid_indices:
        text = texts.loc[idx]
        try:
            prediction = sentiment_service.predict_sentiment(registry, text, model_name=model_name)
            if prediction["label"] == "Positive":
                n_positive += 1
            else:
                n_negative += 1
            results.append({
                "row": int(idx) + 1,
                "text": text[:300],
                "label": prediction["label"],
                "confidence": prediction["confidence"],
                "probability_positive": prediction["probability_positive"],
                "probability_negative": prediction["probability_negative"],
            })
        except Exception as e:
            n_skipped += 1
            results.append({"row": int(idx) + 1, "text": text[:300], "label": "ERROR", "error": str(e)})

    n_classified = n_positive + n_negative
    return {
        "filename": filename,
        "text_column_used": text_col,
        "model_name": model_name,
        "total_rows_in_file": total_rows,
        "rows_processed": len(df),
        "truncated": truncated,
        "max_rows_supported": MAX_FILE_ROWS,
        "n_classified": n_classified,
        "n_positive": n_positive,
        "n_negative": n_negative,
        "n_skipped_empty_or_error": n_skipped,
        "positive_pct": round(n_positive / n_classified * 100, 2) if n_classified else 0.0,
        "negative_pct": round(n_negative / n_classified * 100, 2) if n_classified else 0.0,
        "results": results,
    }
