"""Domain-general aspect-term extraction, used to gate `absa.py`'s
sentiment-given-aspect model without hand-curated per-domain keyword lists.

Why this exists: the original fix for the ABSA hallucination bug (see
absa.py's module docstring) gated each fixed aspect behind an exhaustive,
hand-written keyword list (~15-20 phrase variants per aspect). That works,
but it only works for the exact domain (Olist/e-commerce) someone sat down
and wrote those lists for -- porting it to a new domain (restaurants,
hotels, movies...) means re-authoring a whole new list of keyword variants
by hand, per aspect, per domain.

This module replaces the "search the raw text for known keywords" step with
an extract-then-match pipeline that needs no training data and no per-domain
keyword authoring:

  1. RAKE (Rapid Automatic Keyword Extraction; Rose et al. 2010) pulls out
     the review's own salient candidate phrases directly from its text --
     this step is 100% domain-general: it works from word co-occurrence
     statistics within the given text plus a generic English stopword list,
     not a fixed aspect vocabulary. Pure Python, no model weights, no
     network call -- safe to run on every request regardless of hosting
     memory limits (the ABSA sentiment model itself already can't fit
     alongside BERT on Render's free 512MB tier; this adds no new model).
  2. A candidate phrase is matched against an aspect CATEGORY (e.g. "product
     quality", "food quality", "ambiance") by stemmed word overlap. The only
     input required to add a new domain is the category's own name -- no
     keyword list. An optional short `extra_seeds` list (a handful of core
     synonyms, not an exhaustive phrase list) can be layered on to recover
     cases where the category is discussed without ever using its own name
     (e.g. "flimsy" / "broke" for "product quality") -- this is a precision
     boost, not a requirement; the pipeline still runs and still generalizes
     without it.

Empirically validated on both e-commerce and non-e-commerce (restaurant,
hotel) example reviews -- see scripts/aspect_extraction_demo.py. Two honest,
measured findings from that validation, not assumed:

- The extraction step (RAKE, stemmed overlap against the category name +
  a small seed list) is reliable and needs no retraining to move to a new
  domain -- only a handful of seed synonyms per new category, a small
  fraction of the old approach's exhaustive per-aspect keyword lists.
- A fully zero-seed version (category name alone, no seeds at all) was also
  tested with an added semantic-embedding layer (`load_similarity_model`,
  `aspect_mentioned(..., semantic_model=...)`) to catch synonyms sharing no
  word root (e.g. "spotless" for "cleanliness"). Measured directly: with a
  small, deployment-safe embedding model (~90MB), cosine similarity does NOT
  cleanly separate true aspect matches from unrelated short phrases -- e.g.
  "beach" scored higher against "amenities" (0.45) than "location" (0.41)
  with one model, and "room" outscored the actual "cleanliness" match
  against "location" and "amenities" with another. This is a known limit of
  short-phrase similarity with small embedding models, not a bug in this
  module -- a materially larger model or a fine-tuned aspect-category
  classifier would likely close it, at a memory cost this project's 512MB
  free-tier hosting can't absorb (see DEPLOYMENT.md). The semantic layer is
  therefore shipped as an optional, explicitly opt-in recall boost with a
  documented precision tradeoff, not the default path.
"""
from __future__ import annotations

import re

# Generic English stopwords (not domain-specific) -- used only to find
# candidate-phrase boundaries, exactly as in the original RAKE paper.
_STOPWORDS = frozenset({
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and", "any", "are",
    "aren't", "as", "at", "be", "because", "been", "before", "being", "below", "between", "both",
    "but", "by", "can't", "cannot", "could", "couldn't", "did", "didn't", "do", "does", "doesn't",
    "doing", "don't", "down", "during", "each", "few", "for", "from", "further", "had", "hadn't",
    "has", "hasn't", "have", "haven't", "having", "he", "he'd", "he'll", "he's", "her", "here",
    "here's", "hers", "herself", "him", "himself", "his", "how", "how's", "i", "i'd", "i'll",
    "i'm", "i've", "if", "in", "into", "is", "isn't", "it", "it's", "its", "itself", "let's",
    "me", "more", "most", "mustn't", "my", "myself", "no", "nor", "not", "of", "off", "on",
    "once", "only", "or", "other", "ought", "our", "ours", "ourselves", "out", "over", "own",
    "same", "shan't", "she", "she'd", "she'll", "she's", "should", "shouldn't", "so", "some",
    "such", "than", "that", "that's", "the", "their", "theirs", "them", "themselves", "then",
    "there", "there's", "these", "they", "they'd", "they'll", "they're", "they've", "this",
    "those", "through", "to", "too", "under", "until", "up", "very", "was", "wasn't", "we",
    "we'd", "we'll", "we're", "we've", "were", "weren't", "what", "what's", "when", "when's",
    "where", "where's", "which", "while", "who", "who's", "whom", "why", "why's", "with",
    "won't", "would", "wouldn't", "you", "you'd", "you'll", "you're", "you've", "your", "yours",
    "yourself", "yourselves", "very", "really", "just", "also", "get", "got", "im",
})

_SPLIT_ON = re.compile(r"[.!?,;:()\[\]\"'\n]+")
_WORD_RE = re.compile(r"[a-z]+")

# Deliberately tiny, rule-based -- not a full Porter stemmer, just enough to
# fold obvious plural/verb-form variants together (e.g. "arrived"/"arrive",
# "quality"/"qualities") so stemmed overlap isn't defeated by inflection.
# "ies"/"ied" replace with "y" rather than deleting outright, so
# "delivery"/"deliveries" and "try"/"tried" land on the same stem instead of
# the singular and plural forms silently diverging.
_Y_SUFFIXES = ("ies", "ied")
_SUFFIXES = ("ing", "edly", "ed", "es", "ly", "s")


def _stem(word: str) -> str:
    for suf in _Y_SUFFIXES:
        if word.endswith(suf) and len(word) - len(suf) >= 3:
            return word[: -len(suf)] + "y"
    for suf in _SUFFIXES:
        if word.endswith(suf) and len(word) - len(suf) >= 3:
            return word[: -len(suf)]
    return word


def _candidate_phrases(text: str) -> list[list[str]]:
    """Splits text into candidate phrases at stopword/punctuation boundaries,
    per the RAKE algorithm -- a run of consecutive non-stopword words."""
    phrases: list[list[str]] = []
    for chunk in _SPLIT_ON.split(text.lower()):
        current: list[str] = []
        for word in chunk.split():
            word = "".join(_WORD_RE.findall(word))
            if not word:
                continue
            if word in _STOPWORDS:
                if current:
                    phrases.append(current)
                    current = []
            else:
                current.append(word)
        if current:
            phrases.append(current)
    return phrases


def extract_candidate_terms(text: str, max_terms: int = 15) -> list[str]:
    """RAKE keyphrase extraction: returns up to `max_terms` candidate aspect
    phrases from `text`, ranked by RAKE's word-degree/word-frequency score.
    Domain-general -- works on any English text, no training or per-domain
    configuration needed."""
    phrases = _candidate_phrases(text)
    if not phrases:
        return []

    freq: dict[str, int] = {}
    degree: dict[str, int] = {}
    for phrase in phrases:
        co_degree = len(phrase) - 1
        for word in phrase:
            freq[word] = freq.get(word, 0) + 1
            degree[word] = degree.get(word, 0) + co_degree
    word_score = {w: (degree[w] + freq[w]) / freq[w] for w in freq}

    seen: set[str] = set()
    scored: list[tuple[str, float]] = []
    for phrase in phrases:
        key = " ".join(phrase)
        if key in seen:
            continue
        seen.add(key)
        scored.append((key, sum(word_score.get(w, 0.0) for w in phrase)))

    scored.sort(key=lambda item: item[1], reverse=True)
    return [term for term, _ in scored[:max_terms]]


def aspect_mentioned(
    text: str,
    aspect_category: str,
    extra_seeds: list[str] | None = None,
    semantic_model=None,
    semantic_threshold: float = 0.42,
) -> bool:
    """Domain-general presence check: does `text` actually discuss
    `aspect_category`? Extracts the text's own salient candidate phrases
    (RAKE) and checks:
      1. stemmed word overlap against the category name plus any optional
         seed synonyms (catches exact/inflected mentions, e.g. "quality"),
      2. if `semantic_model` is supplied, embedding cosine similarity between
         each extracted phrase and the category name (catches true synonyms
         with no shared word root, e.g. "spotless" for "cleanliness" or
         "beach" for "location") -- see `load_similarity_model()`.

    Stemmed overlap alone (step 1) is domain-general in the sense that it
    needs no per-domain training, but it was measured empirically (see
    scripts/aspect_extraction_demo.py) to miss true synonyms that share no
    word root with the category name -- step 2 is what actually closes that
    gap. `semantic_model` is optional so this function still works (at
    reduced recall for zero-seed synonyms) on hosts too memory-constrained to
    load it, same graceful-degradation pattern as ENABLE_BERT.
    """
    candidates = extract_candidate_terms(text)
    if not candidates:
        return False
    candidate_stems = {_stem(w) for term in candidates for w in term.split()}

    seed_words = aspect_category.lower().split()
    if extra_seeds:
        for seed in extra_seeds:
            seed_words.extend(seed.lower().split())
    seed_stems = {_stem(w) for w in seed_words}

    if candidate_stems & seed_stems:
        return True

    if semantic_model is not None:
        return _semantic_overlap(semantic_model, candidates, aspect_category, semantic_threshold)
    return False


# Splits on sentence punctuation AND clause-level separators (commas,
# semicolons, coordinating conjunctions). Tested directly against real
# review text and this matters: "Great value for the price, but the
# packaging was crushed when it arrived." has no sentence boundary at all
# (one clause, one comma) -- splitting on periods alone leaves it as a
# single unit, so BOTH "price" and "packaging" would incorrectly get
# whichever sentiment happens to dominate the whole sentence (here,
# "packaging" would wrongly inherit the positive "great value" framing).
# Splitting on the comma isolates "the packaging was crushed" on its own.
_CLAUSE_SPLIT = re.compile(r"(?<=[.!?])\s+|[,;]\s+|\s+\b(?:but|however|although|though|while|yet)\b\s+", re.IGNORECASE)


def extract_aspect_sentence(text: str, aspect_category: str, extra_seeds: list[str] | None = None) -> str | None:
    """Returns the clause(s) of `text` that actually discuss `aspect_category`
    (same stemmed-overlap check as `aspect_mentioned`, applied per-clause
    instead of over the whole review), joined with a space if more than one
    matches. Split on sentence boundaries, commas/semicolons, and
    coordinating conjunctions -- see _CLAUSE_SPLIT's comment for why commas
    matter as much as periods for this specific task. Returns None if no
    clause matches -- callers should fall back to the full text (this
    matches `aspect_mentioned`'s own recall limits: an aspect confirmed
    present in the whole text can occasionally not isolate to one exact
    clause, e.g. a pronoun reference split across clauses).

    Used to narrow a general-purpose sentiment classifier's input down to the
    part of the review actually about the aspect in question, instead of
    scoring the whole review (which conflates sentiment about ALL aspects
    into one signal) -- see app/ml/absa.py."""
    clauses = [c.strip() for c in _CLAUSE_SPLIT.split(text) if c.strip()]
    if len(clauses) <= 1:
        return None
    matches = [c for c in clauses if aspect_mentioned(c, aspect_category, extra_seeds=extra_seeds)]
    return " ".join(matches) if matches else None


SIMILARITY_MODEL_NAME = "sentence-transformers/paraphrase-MiniLM-L3-v2"


def is_semantic_matching_available() -> bool:
    try:
        import sentence_transformers  # noqa: F401
        return True
    except ImportError:
        return False


def load_similarity_model():
    """Loads a small (~61MB, 3-layer) sentence-embedding model once; callers
    (ModelRegistry) should cache and reuse it. Kept separate from the ~700MB
    ABSA sentiment model and never loaded eagerly, so a memory-constrained
    deployment can run the extraction gate at stem-only recall without it."""
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(SIMILARITY_MODEL_NAME)


def _semantic_overlap(model, candidates: list[str], aspect_category: str, threshold: float) -> bool:
    from sentence_transformers.util import cos_sim

    category_emb = model.encode(aspect_category, convert_to_tensor=True)
    candidate_embs = model.encode(candidates, convert_to_tensor=True)
    sims = cos_sim(category_emb, candidate_embs)[0]
    return bool(sims.max().item() >= threshold)
