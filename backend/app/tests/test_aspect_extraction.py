"""Tests for app/ml/aspect_extraction.py -- the domain-general RAKE-based
extraction gate that replaced raw-text keyword search in absa.py. Covers the
reliable path (extraction + stemmed overlap against category name / seeds);
the semantic-embedding layer is exercised separately in
scripts/aspect_extraction_demo.py since it needs a real (optional,
download-gated) model and has a documented, measured precision tradeoff --
not asserted here as a hard pass/fail."""
from app.ml.aspect_extraction import aspect_mentioned, extract_candidate_terms


def test_extract_candidate_terms_returns_salient_phrases():
    text = "The delivery guy was super friendly and dropped it off right on time."
    terms = extract_candidate_terms(text)
    assert "delivery guy" in terms


def test_extract_candidate_terms_empty_for_blank_text():
    assert extract_candidate_terms("") == []
    assert extract_candidate_terms("   ") == []


def test_aspect_mentioned_true_via_category_name_alone():
    """No seeds at all -- the extracted phrase literally shares a stem with
    the category name, which should always work with zero configuration."""
    assert aspect_mentioned("The price was way too high for what you get.", "price")


def test_aspect_mentioned_false_when_absent():
    text = "The delivery guy was super friendly and dropped it off right on time."
    assert not aspect_mentioned(text, "product quality")
    assert not aspect_mentioned(text, "customer service")


def test_aspect_mentioned_true_via_seed_synonym():
    """The category name itself ('product quality') never appears, but a
    seed synonym ('flimsy') does -- this is the documented, small-seed path
    for extending to a new domain without an exhaustive keyword list."""
    text = "The material feels flimsy and cheaply made."
    assert not aspect_mentioned(text, "product quality")  # no seeds: correctly misses it
    assert aspect_mentioned(text, "product quality", extra_seeds=["flimsy", "material", "durable"])


def test_aspect_mentioned_generalizes_to_new_domain_with_small_seeds():
    """Same mechanism, unrelated domain (restaurant), proving this isn't
    e-commerce-specific: only a category name + a few seed words are needed,
    not a new keyword list authored from scratch."""
    text = "The pasta was bland and overcooked, but our waiter was incredibly attentive."
    assert aspect_mentioned(text, "food quality", extra_seeds=["taste", "bland", "delicious"])
    assert aspect_mentioned(text, "service", extra_seeds=["waiter", "waitress", "server"])
    assert not aspect_mentioned(text, "ambiance", extra_seeds=["decor", "atmosphere", "lighting"])


def test_aspect_mentioned_stemming_handles_inflection():
    assert aspect_mentioned("The delivery arrived a week late.", "delivery")
    assert aspect_mentioned("Deliveries here are always delayed.", "delivery")
