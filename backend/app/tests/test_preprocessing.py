import pandas as pd

from app.ml.preprocessing import (
    SimpleVocabTokenizer, build_sentiment_dataframe, normalize_review_text,
    pad_sequences_np, remove_duplicate_reviews, split_sentiment_dataset,
)


def _synthetic_reviews():
    return pd.DataFrame({
        "review_id": [f"r{i}" for i in range(12)],
        "review_score": [1, 2, 3, 4, 5, 1, 4, 5, 1, 4, 1, 4],
        "review_comment_message": [
            "ruim", "ruim", "ok", "bom", "otimo", "No Message", "bom", "otimo",
            "Terrible product", "Great product", "Terrible product", "Great product",
        ],
        "review_comment_message_en": [
            "bad", "bad", "ok", "good", "great", "", "good", "great",
            "Terrible product", "Great product", "Terrible product", "Great product",
        ],
    })


def test_neutral_reviews_excluded():
    raw = _synthetic_reviews()
    df = build_sentiment_dataframe(raw)
    # the one 3-star ("ok") row must not survive into the labeled dataset
    assert "ok" not in df["text"].str.lower().values
    assert (df["label"].isin([0, 1])).all()
    kept_review_ids = set(df["review_id"])
    neutral_review_ids = set(raw.loc[raw["review_score"] == 3, "review_id"])
    assert kept_review_ids.isdisjoint(neutral_review_ids)


def test_empty_review_text_excluded():
    df = build_sentiment_dataframe(_synthetic_reviews())
    # row with review_score=1 and review_comment_message == "No Message" must be excluded
    assert "" not in df["text"].values


def test_label_mapping_correct():
    df = build_sentiment_dataframe(_synthetic_reviews())
    negatives = df[df["label"] == 0]
    positives = df[df["label"] == 1]
    assert set(negatives["text"].str.lower()) <= {"bad", "terrible product"}
    assert set(positives["text"].str.lower()) <= {"good", "great", "great product"}


def test_duplicate_removal_before_split():
    df = build_sentiment_dataframe(_synthetic_reviews())
    deduped, report = remove_duplicate_reviews(df)
    assert report.rows_after <= report.rows_before
    assert deduped["normalized_text"].is_unique


def test_normalize_review_text_case_and_whitespace_insensitive():
    assert normalize_review_text("Great   Product") == normalize_review_text("great product")


def _synthetic_reviews_large(n_per_class: int = 30) -> pd.DataFrame:
    """A larger, all-unique-text synthetic dataset -- large enough for a
    stratified 70/10/20 split (the 5-row set in _synthetic_reviews() is too
    small for sklearn's stratification to place >=1 sample per class in
    every split)."""
    rows = []
    for i in range(n_per_class):
        rows.append({"review_id": f"neg{i}", "review_score": 1, "review_comment_message": f"bad product {i}", "review_comment_message_en": f"bad product {i}"})
        rows.append({"review_id": f"pos{i}", "review_score": 5, "review_comment_message": f"great product {i}", "review_comment_message_en": f"great product {i}"})
    return pd.DataFrame(rows)


def test_split_reproducible_with_seed():
    df = build_sentiment_dataframe(_synthetic_reviews_large())
    deduped, _ = remove_duplicate_reviews(df)
    split_a = split_sentiment_dataset(deduped, seed=42)
    split_b = split_sentiment_dataset(deduped, seed=42)
    assert list(split_a.train["review_id"]) == list(split_b.train["review_id"])


def test_split_has_no_text_overlap():
    df = build_sentiment_dataframe(_synthetic_reviews_large())
    deduped, _ = remove_duplicate_reviews(df)
    split = split_sentiment_dataset(deduped, seed=42)
    overlap = split.overlap_report()
    assert all(v == 0 for v in overlap["normalized_text_overlap"].values())
    assert all(v == 0 for v in overlap["index_overlap"].values())


def test_tokenizer_reserves_padding_and_oov_indices():
    tok = SimpleVocabTokenizer(num_words=100)
    tok.fit_on_texts(["good product", "bad product", "good service"])
    assert tok.word_index[tok.oov_token] == 1
    assert 0 not in tok.word_index.values()  # 0 is reserved for padding, never assigned to a real word


def test_tokenizer_fit_only_on_provided_texts():
    tok = SimpleVocabTokenizer(num_words=100)
    tok.fit_on_texts(["alpha beta"])
    seqs = tok.texts_to_sequences(["alpha gamma"])  # 'gamma' unseen -> must map to OOV
    oov_idx = tok.word_index[tok.oov_token]
    assert seqs[0][1] == oov_idx


def test_pad_sequences_post_padding_and_truncation():
    seqs = [[1, 2, 3], [1]]
    padded = pad_sequences_np(seqs, maxlen=5, padding="post", truncating="post")
    assert padded.shape == (2, 5)
    assert list(padded[0]) == [1, 2, 3, 0, 0]
    assert list(padded[1]) == [1, 0, 0, 0, 0]

    long_seq = [[1, 2, 3, 4, 5, 6]]
    truncated = pad_sequences_np(long_seq, maxlen=4, padding="post", truncating="post")
    assert list(truncated[0]) == [1, 2, 3, 4]  # keeps the FIRST 4 (post-truncation drops the tail)
