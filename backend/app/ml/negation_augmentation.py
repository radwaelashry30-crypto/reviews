"""Negation-aware training-data augmentation for CNN2D.

CNN2D (a bag-of-n-grams convolutional model, filter sizes 2-5) systematically
misclassifies short negated phrases -- verified: "the product is not bad" ->
Negative at 97.2% confidence, while the fine-tuned BERT model correctly reads
it as Positive (83.2%). BERT's attention mechanism generalizes negation from
its pretraining; CNN2D only learns it from patterns actually present in its
OWN training data, and negation cues are underrepresented in the Olist
training split.

This module pulls a small, negation-rich sample from a larger, different-
domain review corpus and mixes it into CNN2D's training data at a
configurable negated/ordinary ratio, so the model sees enough real
"not X" / "isn't X" / "n't X" examples -- of BOTH polarities -- to learn
that negation flips sentiment, rather than learning "negation cue -> always
negative". Two source corpora are supported:

1. Datafiniti's Amazon Consumer Reviews dataset (`load_amazon_reviews` +
   `build_sentiment_labels`, ~45K rows, star ratings). Small: only 1,841 of
   44,824 rows are negative-labeled, capping any negated-negative sample at
   ~987 rows -- an earlier iteration using only this source measurably
   improved CNN2D's negation calibration but did not fully fix idioms like
   "not bad" (verified: p_positive moved 0.028 -> 0.116, still < 0.5).
2. The Amazon Reviews Polarity dataset (`load_amazon_polarity_dataset`,
   Xiang Zhang et al. 2015, via its HuggingFace mirror
   `fancyzhx/amazon_polarity` -- the same corpus as
   kaggle.com/datasets/kritanjalijain/amazon-reviews), already binary-
   labeled and NOT skewed: one 900K-row shard alone has ~300K negated-
   negative rows, ~300x more than Datafiniti. Used for the second,
   substantially larger-scale retraining attempt.

Only the small derived augmentation sample this module actually trains on
is saved to `data/interim/negation_augmentation_sample.csv` -- the full
source corpora are not redistributed in this repo.

The Olist validation/test splits are NEVER touched by this augmentation --
only the CNN2D TRAIN partition is augmented, so reported test metrics remain
a clean read on the target domain.
"""
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

NEGATION_PATTERN = re.compile(
    r"\b(not|no|never|n't|cannot|nothing|nobody|nowhere|neither|nor|without|hardly|barely|scarcely)\b",
    re.IGNORECASE,
)


def detect_negation(text: str) -> bool:
    return bool(NEGATION_PATTERN.search(str(text)))


def load_amazon_reviews(paths: list[str | Path]) -> pd.DataFrame:
    """Load and concatenate one or more Datafiniti-schema Amazon review CSVs
    (`reviews.text`, `reviews.rating` columns), deduplicated by review text."""
    frames = []
    for p in paths:
        p = Path(p)
        if not p.is_file():
            continue
        df = pd.read_csv(p, usecols=["reviews.text", "reviews.rating"])
        frames.append(df)
    if not frames:
        raise FileNotFoundError(f"None of the provided Amazon review CSV paths exist: {paths}")
    combined = pd.concat(frames, ignore_index=True)
    combined = combined.rename(columns={"reviews.text": "text", "reviews.rating": "rating"})
    combined = combined.dropna(subset=["text", "rating"])
    combined = combined.drop_duplicates(subset=["text"]).reset_index(drop=True)
    return combined


def load_amazon_polarity_dataset(paths: list[str | Path]) -> pd.DataFrame:
    """Load one or more `fancyzhx/amazon_polarity` parquet shards (columns:
    label [0=negative, 1=positive], title, content). Already binary-labeled
    and near-perfectly class-balanced -- no star-rating conversion needed."""
    frames = []
    for p in paths:
        p = Path(p)
        if not p.is_file():
            continue
        df = pd.read_parquet(p, columns=["label", "content"])
        frames.append(df)
    if not frames:
        raise FileNotFoundError(f"None of the provided Amazon Polarity parquet paths exist: {paths}")
    combined = pd.concat(frames, ignore_index=True)
    combined = combined.rename(columns={"content": "text"})
    combined = combined.dropna(subset=["text", "label"])
    combined = combined[combined["text"].astype(str).str.strip().str.len() > 0]
    combined = combined.drop_duplicates(subset=["text"]).reset_index(drop=True)
    return combined[["text", "label"]]


def build_sentiment_labels(amazon_df: pd.DataFrame) -> pd.DataFrame:
    """Same binary scheme as the Olist task: 1-2 stars -> 0, 4-5 stars -> 1, drop 3-star."""
    df = amazon_df[amazon_df["rating"].isin([1, 2, 4, 5])].copy()
    df["label"] = df["rating"].apply(lambda r: 0 if r in (1, 2) else 1)
    df = df[df["text"].astype(str).str.strip().str.len() > 0].reset_index(drop=True)
    return df[["text", "label"]]


def build_negation_augmented_sample(
    amazon_df: pd.DataFrame, n_total: int = 10_000, negation_ratio: float = 0.6, seed: int = 42,
) -> pd.DataFrame:
    """Sample from `amazon_df` (already labeled via `build_sentiment_labels`)
    at roughly `negation_ratio` negated / (1-negation_ratio) ordinary,
    BALANCED ACROSS LABEL within each pool.

    Raw Amazon consumer reviews are overwhelmingly positive (verified: only
    1,841 of 44,824 labeled rows are negative -- a naive random sample at
    negation_ratio alone comes out ~93% positive, which would make CNN2D's
    negative-class calibration WORSE, not better). Negative-labeled reviews
    are the rare resource here, so each pool takes ALL available negative
    examples and matches them with an equal-sized positive sample -- the
    final augmentation set is label-balanced (~50/50) regardless of the
    source corpus's skew, and `n_total`/`negation_ratio` become soft targets
    bounded by how much negative-labeled data actually exists.
    """
    df = amazon_df.copy()
    df["is_negated"] = df["text"].map(detect_negation)

    def _balanced_pool(pool: pd.DataFrame, target_size: int) -> pd.DataFrame:
        neg = pool[pool["label"] == 0]
        pos = pool[pool["label"] == 1]
        n_per_class = min(target_size // 2, len(neg))  # neg is always the scarcer class here
        neg_sample = neg.sample(n_per_class, random_state=seed) if n_per_class > 0 else neg.iloc[0:0]
        pos_sample = pos.sample(min(n_per_class, len(pos)), random_state=seed) if n_per_class > 0 else pos.iloc[0:0]
        return pd.concat([neg_sample, pos_sample], ignore_index=True)

    negated_sample = _balanced_pool(df[df["is_negated"]], int(n_total * negation_ratio))
    ordinary_sample = _balanced_pool(df[~df["is_negated"]], n_total - int(n_total * negation_ratio))

    out = pd.concat([negated_sample, ordinary_sample], ignore_index=True)
    return out.sample(frac=1.0, random_state=seed).reset_index(drop=True)  # shuffle
