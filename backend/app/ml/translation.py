"""Portuguese -> English review translation.

The notebook's Configuration cell (cell 3) sets
`TRANSLATION_MODEL = "Helsinki-NLP/opus-mt-pt-en"`, but the translation cell
that actually ran (cell 49, immediately before loading the model) overwrites
it:

    TRANSLATION_MODEL = "Helsinki-NLP/opus-mt-ROMANCE-en"

and the execution log in cell 50 confirms `opus-mt-ROMANCE-en` is the model
that was actually loaded and used to produce `reviews_translated.csv`
("Loading translation model on cpu: Helsinki-NLP/opus-mt-ROMANCE-en"). This
module defaults to the model that was actually used, not the one in the
Configuration cell, and records the choice explicitly in the manifest rather
than silently picking one (per the audit requirement in the task spec).
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

ACTUAL_TRANSLATION_MODEL = "Helsinki-NLP/opus-mt-ROMANCE-en"
CONFIGURED_BUT_UNUSED_MODEL = "Helsinki-NLP/opus-mt-pt-en"

DEFAULT_CACHE_PATH = "data/interim/reviews_translated.csv"
TRANSLATED_COLUMN = "review_comment_message_en"


@dataclass
class TranslationManifest:
    model: str
    model_revision: str | None
    source_language: str
    target_language: str
    batch_size: int
    max_length: int
    rows_translated: int
    rows_failed: int
    source_artifact: str
    created_at: str

    def to_dict(self) -> dict:
        return {
            "model": self.model,
            "model_revision": self.model_revision,
            "source_language": self.source_language,
            "target_language": self.target_language,
            "batch_size": self.batch_size,
            "max_length": self.max_length,
            "rows_translated": self.rows_translated,
            "rows_failed": self.rows_failed,
            "source_artifact": self.source_artifact,
            "created_at": self.created_at,
        }


def load_existing_translation_cache(path: str | Path = DEFAULT_CACHE_PATH) -> pd.DataFrame | None:
    """Reuse an existing translated-review checkpoint if present. Never retranslates rows that already have text."""
    path = Path(path)
    if not path.is_file():
        return None
    return pd.read_csv(path)


def translate_reviews(
    reviews: pd.DataFrame,
    model_name: str = ACTUAL_TRANSLATION_MODEL,
    batch_size: int = 32,
    max_length: int = 512,
    checkpoint_path: str | Path = DEFAULT_CACHE_PATH,
    checkpoint_every_batches: int = 50,
    device: str | None = None,
) -> tuple[pd.DataFrame, TranslationManifest]:
    """Batch-translate `review_comment_message` -> `review_comment_message_en`.

    Reproduces the notebook's incremental-checkpoint behavior (cell 50): skips
    rows that already have non-empty translated text, saves progress to disk
    every `checkpoint_every_batches` batches so an interrupted run can resume,
    and logs failed batches instead of aborting. Does NOT import torch/transformers
    at module import time — only inside this function, so importing this module
    never triggers a model download.
    """
    import torch
    from transformers import MarianMTModel, MarianTokenizer

    checkpoint_path = Path(checkpoint_path)
    if checkpoint_path.is_file():
        reviews = pd.read_csv(checkpoint_path)
    else:
        reviews = reviews.copy()

    if TRANSLATED_COLUMN not in reviews.columns:
        reviews[TRANSLATED_COLUMN] = ""

    to_translate_mask = (
        (reviews["review_comment_message"] != "No Message")
        & (reviews[TRANSLATED_COLUMN].isna() | (reviews[TRANSLATED_COLUMN].astype(str).str.strip() == ""))
    )
    indices = reviews[to_translate_mask].index.tolist()
    total_remaining = len(indices)
    failures = 0

    if total_remaining > 0:
        torch_device = torch.device(device or ("cuda" if torch.cuda.is_available() else "cpu"))
        tokenizer = MarianTokenizer.from_pretrained(model_name)
        model = MarianMTModel.from_pretrained(model_name).to(torch_device)
        model.eval()

        n_batches = (total_remaining + batch_size - 1) // batch_size
        with torch.no_grad():
            for batch_idx in range(n_batches):
                start_i = batch_idx * batch_size
                end_i = min(start_i + batch_size, total_remaining)
                batch_indices = indices[start_i:end_i]
                batch_texts = reviews.loc[batch_indices, "review_comment_message"].fillna("").astype(str).tolist()
                safe_batch = [t if t.strip() else "." for t in batch_texts]
                try:
                    inputs = tokenizer(
                        safe_batch, return_tensors="pt", padding=True,
                        truncation=True, max_length=max_length,
                    ).to(torch_device)
                    generated = model.generate(**inputs, max_length=max_length)
                    decoded = tokenizer.batch_decode(generated, skip_special_tokens=True)
                    reviews.loc[batch_indices, TRANSLATED_COLUMN] = decoded
                except Exception:
                    failures += len(batch_indices)
                    reviews.loc[batch_indices, TRANSLATED_COLUMN] = ""

                if (batch_idx + 1) % checkpoint_every_batches == 0 or (batch_idx + 1) == n_batches:
                    checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
                    reviews.to_csv(checkpoint_path, index=False)

        del model, tokenizer

    manifest = TranslationManifest(
        model=model_name,
        model_revision=None,
        source_language="pt",
        target_language="en",
        batch_size=batch_size,
        max_length=max_length,
        rows_translated=total_remaining - failures,
        rows_failed=failures,
        source_artifact=str(checkpoint_path),
        created_at=pd.Timestamp.utcnow().isoformat(),
    )
    return reviews, manifest


def build_translation_manifest_from_existing_cache(
    reviews: pd.DataFrame,
    checkpoint_path: str | Path = DEFAULT_CACHE_PATH,
    model_name: str = ACTUAL_TRANSLATION_MODEL,
) -> TranslationManifest:
    """Build a manifest describing an already-produced translation checkpoint,
    without loading any translation model. Used by export_artifacts.py / run_pipeline.py
    when a valid `reviews_translated.csv` already exists on disk."""
    non_empty = reviews[TRANSLATED_COLUMN].fillna("").astype(str).str.strip()
    should_have_text = reviews["review_comment_message"] != "No Message"
    rows_failed = int((should_have_text & (non_empty == "")).sum())
    return TranslationManifest(
        model=model_name,
        model_revision=None,
        source_language="pt",
        target_language="en",
        batch_size=32,
        max_length=512,
        rows_translated=int((non_empty != "").sum()),
        rows_failed=rows_failed,
        source_artifact=str(checkpoint_path),
        created_at=pd.Timestamp.utcnow().isoformat(),
    )
