"""CSV/Excel review-file upload: parse, auto-detect the review-text column,
classify every row with the chosen sentiment model, return per-row results
plus a summary. Runs synchronously (no task queue) -- bounded by
MAX_FILE_ROWS so a very large upload doesn't block the server indefinitely.

Beyond the base Positive/Negative pass (cheap, runs over every row), this
module offers an opt-in `advanced` mode that adds fake-review screening and
aspect-based sentiment via `advanced_sentiment_service.run_full_pipeline`.
That pipeline costs ~6-7 model forward passes per row (1 sentiment + up to 5
ABSA aspect passes + 1 fake-check for negatives), so -- same pattern already
used by `app/ml/absa.py::run_absa` (DEFAULT_SAMPLE_SIZE=200) and
`app/ml/explainability.py` (DEFAULT_XAI_SAMPLE_SIZE=8) -- it only runs on a
bounded sample of rows, never the full upload, and says so via a
methodology_note.

"Most influential words" is deliberately NOT per-row SHAP (far too slow at
batch scale); it's fast lexical frequency analysis over words that
disproportionately appear in Positive vs Negative reviews, so it can run over
every row for free.
"""
from __future__ import annotations

import io
import re
from collections import Counter

import pandas as pd
from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS

from app.core.config import settings
from app.core.exceptions import InvalidRequestError
from app.services import advanced_sentiment_service, sentiment_service
from app.services.model_registry import ModelRegistry

MAX_FILE_ROWS = 2000

# Rows the (expensive) advanced pipeline runs on, out of all valid rows -- see
# module docstring for why this is sampled rather than run on everything.
ADVANCED_SAMPLE_SIZE = 100

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

DATE_COLUMN_CANDIDATES = [
    "review_creation_date",
    "review_answer_timestamp",
    "date",
    "created_at",
    "timestamp",
    "review_date",
]

_WORD_RE = re.compile(r"\b[a-zA-Z]{3,}\b")
TOP_WORDS_PER_CLASS = 15


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


def _detect_date_column(df: pd.DataFrame) -> str | None:
    """Best-effort match against common review-date column names. Returns
    None (not a raised error) when absent -- a missing date column just means
    the time-trend feature reports itself unavailable, it's not a bad upload."""
    lower_map = {c.lower(): c for c in df.columns}
    for candidate in DATE_COLUMN_CANDIDATES:
        if candidate in lower_map:
            return lower_map[candidate]
    return None


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


def _extract_top_words(results: list[dict]) -> dict:
    """Words ranked by how disproportionately they appear in one class vs the
    other (count in this class minus count in the other), not raw frequency --
    otherwise generic words like "order"/"product" that show up constantly in
    both classes would drown out words that actually distinguish them."""
    counters = {"Positive": Counter(), "Negative": Counter()}
    for r in results:
        label = r.get("label")
        if label not in counters:
            continue
        words = {w.lower() for w in _WORD_RE.findall(r.get("text", "")) if w.lower() not in ENGLISH_STOP_WORDS}
        counters[label].update(words)

    def _top(label: str, other: str) -> list[dict]:
        this_counter, other_counter = counters[label], counters[other]
        scored = [
            (word, count, count - other_counter.get(word, 0))
            for word, count in this_counter.items()
        ]
        scored.sort(key=lambda w: (w[2], w[1]), reverse=True)
        return [{"word": word, "count": count} for word, count, _distinctiveness in scored[:TOP_WORDS_PER_CLASS]]

    return {
        "top_positive_words": _top("Positive", "Negative"),
        "top_negative_words": _top("Negative", "Positive"),
    }


def _build_time_trend(df: pd.DataFrame, date_col: str | None, label_by_index: dict) -> dict:
    """Weekly Positive-rate trend, over rows that both parsed a valid date and
    got classified (skipped/errored rows have no label to trend)."""
    if date_col is None:
        return {"available": False, "reason": "no date column detected"}

    parsed_dates = pd.to_datetime(df[date_col], errors="coerce")
    trend_df = pd.DataFrame({
        "date": parsed_dates,
        "label": [label_by_index.get(idx) for idx in df.index],
    }).dropna(subset=["date", "label"])

    if trend_df.empty:
        return {
            "available": False,
            "reason": f"'{date_col}' column found but no rows had both a valid date and a classified label",
        }

    trend_df = trend_df.copy()
    trend_df["period"] = trend_df["date"].dt.to_period("W").astype(str)
    points = []
    for period, group in trend_df.groupby("period"):
        n = len(group)
        n_positive = int((group["label"] == "Positive").sum())
        points.append({"period": period, "n": n, "positive_pct": round(n_positive / n * 100, 2)})
    points.sort(key=lambda p: p["period"])

    return {"available": True, "granularity": "week", "date_column_used": date_col, "points": points}


def _build_fake_review_summary(pipeline_results: list[dict]) -> dict:
    """Aggregates fake_check across the advanced-sampled rows. fake_check only
    runs (inside run_full_pipeline) for rows predicted Negative, so this is a
    rate among screened negatives, not among the whole sample."""
    screened = [r["fake_check"] for r in pipeline_results if r.get("fake_check") is not None]
    if not screened:
        return {"available": False, "reason": "no negative reviews in the analyzed sample"}

    available = [f for f in screened if f.get("available")]
    if not available:
        return {"available": False, "reason": screened[0].get("reason", "fake-review model not available on this deployment")}

    n_screened = len(available)
    # "reliable" is True unless the verdict landed in the model's own
    # UNCERTAIN band (see fake_review_detection.py's _verdict) -- excluding
    # those from flagged_pct means an honestly-uncertain call doesn't get
    # silently counted as a confident one.
    reliable = [f for f in available if f.get("reliable", True)]
    n_unreliable = n_screened - len(reliable)
    n_flagged = sum(1 for f in reliable if f.get("is_fake"))
    n_reliable = len(reliable)
    return {
        "available": True,
        "n_screened_negative": n_screened,
        "n_reliable": n_reliable,
        "n_unreliable_excluded": n_unreliable,
        "n_flagged_fake": n_flagged,
        "flagged_pct": round(n_flagged / n_reliable * 100, 2) if n_reliable else 0.0,
        "methodology_note": (
            "Fake-review screening over the negative reviews within the analyzed sample "
            f"(up to {ADVANCED_SAMPLE_SIZE} rows of this file, not the full upload), using an "
            "ensemble trained on a genuinely human-verified deceptive-review corpus (Ott et al., "
            "hotel domain -- a real domain shift from Olist e-commerce, not separately measured). "
            f"{n_unreliable} of {n_screened} screened rows landed in the model's own UNCERTAIN "
            "band and were excluded from flagged_pct rather than forced into a confident guess. "
            "See MODEL_COMPARISON_AUDIT.md for the full validation methodology."
        ),
    }


def _build_aspect_summary(pipeline_results: list[dict], sample_size: int) -> dict:
    """Aggregates per-row ABSA results (sentiment-given-aspect over a fixed
    aspect list) into per-aspect Positive/Neutral/Negative rates.

    Percentages are computed only among rows where the aspect was actually
    mentioned (see app/ml/absa.py's keyword-presence gate) -- folding
    "Not mentioned" rows into the same denominator would silently deflate
    every percentage without explanation whenever an aspect is rarely
    discussed. `n_mentioned` / `mentioned_pct` report that coverage explicitly
    instead."""
    aspect_rows = [r["aspects"] for r in pipeline_results if r.get("aspects") is not None]
    if not aspect_rows:
        return {"available": False, "reason": "no rows analyzed"}
    if not aspect_rows[0].get("available"):
        return {"available": False, "reason": aspect_rows[0].get("reason", "aspect model not available on this deployment")}

    per_aspect_counts: dict[str, Counter] = {}
    for row in aspect_rows:
        for entry in row.get("aspects", []):
            aspect = entry["aspect"]
            sentiment = entry.get("sentiment", "UNKNOWN")
            per_aspect_counts.setdefault(aspect, Counter())[sentiment] += 1

    summary = []
    for aspect, counts in per_aspect_counts.items():
        n_total = sum(counts.values())
        n_not_mentioned = counts.get("Not mentioned", 0)
        n_mentioned = n_total - n_not_mentioned
        summary.append({
            "aspect": aspect,
            "n": n_total,
            "n_mentioned": n_mentioned,
            "mentioned_pct": round(n_mentioned / n_total * 100, 2) if n_total else 0.0,
            "positive_pct": round(counts.get("Positive", 0) / n_mentioned * 100, 2) if n_mentioned else 0.0,
            "neutral_pct": round(counts.get("Neutral", 0) / n_mentioned * 100, 2) if n_mentioned else 0.0,
            "negative_pct": round(counts.get("Negative", 0) / n_mentioned * 100, 2) if n_mentioned else 0.0,
        })

    return {
        "available": True,
        "sample_size": sample_size,
        "per_aspect": summary,
        "methodology_note": (
            "Sentiment-given-aspect over a fixed candidate aspect list, not automatic aspect "
            f"extraction. Based on a sample of up to {ADVANCED_SAMPLE_SIZE} rows of this file."
        ),
    }


def classify_review_file(
    registry: ModelRegistry, filename: str, content: bytes, model_name: str = "bert",
    advanced: bool = False,
) -> dict:
    df = parse_review_file(filename, content)
    text_col = _detect_text_column(df)
    date_col = _detect_date_column(df)

    total_rows = len(df)
    if total_rows > MAX_FILE_ROWS:
        df = df.head(MAX_FILE_ROWS)
    truncated = total_rows > MAX_FILE_ROWS

    texts = df[text_col].fillna("").astype(str)
    valid_mask = texts.str.strip() != ""
    valid_indices = df.index[valid_mask].tolist()

    # First N valid rows get the expensive full pipeline (fake-check + aspects);
    # the rest still get plain sentiment, same as before.
    advanced_indices = set(valid_indices[:ADVANCED_SAMPLE_SIZE]) if advanced else set()

    results = []
    label_by_index: dict = {}
    pipeline_results: list[dict] = []
    n_positive = 0
    n_negative = 0
    n_skipped = int((~valid_mask).sum())

    for idx in valid_indices:
        text = texts.loc[idx]
        try:
            if idx in advanced_indices:
                full = advanced_sentiment_service.run_full_pipeline(registry, text, model_name=model_name)
                prediction = full["sentiment"]
                pipeline_results.append(full)
            else:
                prediction = sentiment_service.predict_sentiment(registry, text, model_name=model_name)

            if prediction["label"] == "Positive":
                n_positive += 1
            else:
                n_negative += 1
            label_by_index[idx] = prediction["label"]
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
    output = {
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
        "top_words": _extract_top_words(results),
        "time_trend": _build_time_trend(df, date_col, label_by_index),
    }

    if advanced:
        output["advanced_sample_size"] = len(advanced_indices)
        output["fake_review_summary"] = _build_fake_review_summary(pipeline_results)
        output["aspect_summary"] = _build_aspect_summary(pipeline_results, len(advanced_indices))

    return output
