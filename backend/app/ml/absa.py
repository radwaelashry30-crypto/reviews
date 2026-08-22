"""Optional, EXPERIMENTAL aspect-based sentiment analysis (sentiment-given-aspect).

Notebook §13 (cell 147) runs `yangheng/deberta-v3-base-absa-v1.1` via the
`text-classification` pipeline with `text_pair=<aspect>` over a fixed
candidate aspect list. Olist reviews have NO ground-truth aspect labels, so
this scores sentiment GIVEN a predefined aspect, not full automatic aspect
extraction. Does not download the model at import time.

CONFIRMED BUG (found via live testing, fixed here): `yangheng/deberta-v3-base-
absa-v1.1` is an Aspect-Term SENTIMENT model, not an aspect DETECTOR -- it was
trained on datasets (SemEval Laptop/Restaurant, MAMS) where the queried aspect
was always genuinely present in the sentence, so it has no "not mentioned"
class and will confidently hallucinate a sentiment for any aspect you force it
to score. Verified empirically: for the review "The delivery guy was super
friendly and dropped it off right on time." (only about delivery), the model
returned "product quality: Positive 75.1%" -- a class of product never
mentioned. For "This laptop is garbage, completely broke after two days."
(only about the product itself), it returned Negative for delivery/price/
customer service/packaging, none of which appear in the text (customer
service scored 98.8% confidence). The prior code queried all 5 fixed aspects
on every review regardless of content.

Fix: `_aspect_mentioned()` gates each aspect behind a presence check before
the model is ever called for it. If the aspect doesn't appear to be
discussed, it's reported as "Not mentioned" without a model call, instead of
a hallucinated Positive/Negative/Neutral.

The presence check itself is `aspect_extraction.aspect_mentioned()` (see
app/ml/aspect_extraction.py): RAKE extracts the review's own salient phrases
directly from its text (domain-general, no per-domain configuration needed),
then those extracted phrases are matched against the aspect category by
stemmed word overlap. ASPECT_KEYWORDS below is no longer a raw-text substring
search -- it's an optional, small `extra_seeds` list per category (a
precision boost for recovering aspects discussed without using the category's
own name, e.g. "flimsy"/"broke" for "product quality") layered on top of the
domain-general extraction step, not a requirement for it to work. A brand
new domain (restaurants, hotels, ...) needs only new category names to get a
working gate; the seed lists are an optional, much smaller addition on top.

This is still a heuristic, not a perfect detector -- it can miss aspects
phrased in ways RAKE doesn't surface as salient (a false negative just means
that aspect is skipped, no worse than the un-gated behavior) and can
occasionally admit an unrelated phrase that happens to share a stem with the
category (a false positive falls back to the original model-scored
behavior). It directly eliminates the confirmed failure mode above: neither
"quality" nor "customer service" is extracted from the delivery-only
example, so those calls are skipped entirely rather than guessed.

SECOND CHANGE (this section): `yangheng/deberta-v3-base-absa-v1.1` is ~738MB
-- a real memory risk on Render's 512MB free tier, the same class of problem
Technical Review found for BERT (see MODEL_CARD.md). Two external
replacements were evaluated and rejected before this one: a SetFit-based
model (`tomaarsen/setfit-absa-bge-small-en-v1.5-restaurants-polarity`,
134MB weights) pulls in `sentence-transformers` -> `setfit`, which installed
a full TensorFlow dependency (500MB+) as a transitive requirement -- a net
INCREASE in footprint despite smaller model weights, confirmed by actually
installing it. Several small DistilBERT-based ABSA models exist on the Hub
in the right domain (Amazon/laptop reviews, ~269MB) but each has single-
digit download counts and no independent verification -- exactly the
"unverified label semantics" risk this project already got burned by once
(see app/ml/fake_review_detection.py's history). Verifying one properly
would mean repeating the multi-day training/stability investigation done
for the fake-review detector, disproportionate for a secondary feature.

Fix: sentiment-given-aspect is now computed by finding the SENTENCE(s) of
the review that discuss the aspect (`aspect_extraction.extract_aspect_sentence`,
the same RAKE-based mechanism as the presence gate above, applied per-
sentence) and scoring just that clause with CNN2D -- the project's own
binary sentiment classifier, already fully trained, evaluated, and loaded
in memory for Task 1. Zero additional model weights, zero new dependencies.
Honest tradeoff: clause-level sentiment is an approximation of aspect-level
sentiment, not a purpose-trained ABSA model -- stated explicitly in
`methodology_note` below.

THIRD CHANGE (found via live testing after shipping the fix above): CNN2D
was trained on full review texts, not short isolated clauses -- on a
genuinely correctly-isolated but very short clause ("but the packaging was
crushed.", 5 words), its confidence landed at 50.3% Positive, a near-random
call it presented with the same confident-looking label as a 98% call.
`_Cnn2dAspectSentiment` now reports "Neutral" for any prediction within
`UNCERTAIN_MARGIN` of 0.5, the same honest-uncertainty pattern used for the
fake-review ensemble's UNCERTAIN band (see fake_review_detection.py) --
this also fills the "no Neutral class" gap the binary model otherwise has,
rather than just disclaiming it.
"""
from __future__ import annotations

import pandas as pd

from app.ml.aspect_extraction import aspect_mentioned as _extraction_aspect_mentioned
from app.ml.aspect_extraction import extract_aspect_sentence

ABSA_ASPECTS = ["delivery", "product quality", "price", "customer service", "packaging"]
DEFAULT_SAMPLE_SIZE = 200
ABSA_METHOD_DESCRIPTION_CNN = "CNN2D sentiment over the RAKE-located aspect sentence (see app/ml/absa.py module docstring)"
ABSA_METHOD_DESCRIPTION_DEBERTA = "yangheng/deberta-v3-base-absa-v1.1 (Aspect-Based Sentiment Analysis model)"
ABSA_MODEL_DEBERTA = "yangheng/deberta-v3-base-absa-v1.1"

NOT_MENTIONED_LABEL = "Not mentioned"

# Optional seed synonyms per built-in aspect -- layered on top of the
# domain-general RAKE extraction in aspect_extraction.py, not a substitute
# for it. A new domain needs none of this to get a working gate (see
# aspect_extraction.py's module docstring); these exist only to recover
# e-commerce phrasings that never use the category's own name.
ASPECT_KEYWORDS: dict[str, list[str]] = {
    "delivery": [
        "deliver", "delivery", "delivered", "delivering", "shipping", "shipped", "ship",
        "arrive", "arrived", "arriving", "courier", "package", "parcel", "postal", "post",
        "mail", "tracking", "late", "on time", "dispatch",
    ],
    "product quality": [
        "quality", "material", "materials", "durable", "durability", "broke", "broken",
        "defect", "defective", "sturdy", "flimsy", "cheaply made", "well made", "craftsmanship",
        "fabric", "build quality", "fell apart", "damaged", "faulty", "works well", "worked well",
    ],
    "price": [
        "price", "priced", "pricing", "cost", "costly", "expensive", "cheap", "cheaper",
        "affordable", "value for money", "worth", "money", "overpriced", "pricey", "discount",
        "cost-effective", "cheapest", "budget",
    ],
    "customer service": [
        "customer service", "support", "representative", "staff", "helpline", "response",
        "responded", "refund", "return policy", "complaint", "assistance", "help desk",
        "customer care", "agent", "call center",
    ],
    "packaging": [
        "packaging", "package box", "box", "boxed", "wrapped", "wrapping", "bubble wrap",
        "seal", "sealed", "container", "damaged box", "crushed box",
    ],
}


def _aspect_mentioned(text: str, aspect: str) -> bool:
    """Domain-general presence check -- see module docstring for why this
    gate exists and how it works. `aspect` needs no pre-registered keyword
    list to be checked; ASPECT_KEYWORDS only supplies optional extra seeds
    for the built-in e-commerce categories."""
    return _extraction_aspect_mentioned(text, aspect, extra_seeds=ASPECT_KEYWORDS.get(aspect))


def is_absa_model_available() -> bool:
    """No separate model to check for anymore -- ABSA runs on CNN2D, which
    Task 1 already requires. Kept for API compatibility with callers written
    against the old (separate-model) version."""
    return True


class _Cnn2dAspectSentiment:
    """Callable matching the shape ModelRegistry's HF pipelines used to
    return (`pipe(text, text_pair=aspect, truncation=True) -> [{"label",
    "score"}]`), so analyze_aspects_single/run_absa needed no call-site
    changes. Internally: locate the aspect's sentence (RAKE), score it with
    the already-loaded CNN2D model -- see module docstring."""

    # Below this margin around 0.5, CNN2D's confidence on a short isolated
    # clause is close enough to a coin flip that presenting it as a
    # confident Positive/Negative would overstate it. Found by testing this
    # exact scenario live: "but the packaging was crushed." (a real,
    # correctly-isolated clause -- not a splitting bug) scored 50.3% Positive,
    # a near-random call on a 5-word clause CNN2D was never trained on in
    # isolation (its training data is full review texts, not single short
    # clauses). Reported as Neutral instead -- an honest use for the class
    # CNN2D otherwise has no direct signal for, not a guess either way.
    UNCERTAIN_MARGIN = 0.08

    def __init__(self, cnn_model, cnn_tokenizer, device):
        self.cnn_model = cnn_model
        self.cnn_tokenizer = cnn_tokenizer
        self.device = device

    def __call__(self, text: str, text_pair: str | None = None, truncation: bool = True):
        import torch

        from app.ml.datasets import encode_texts_for_cnn

        aspect = text_pair or ""
        clause = extract_aspect_sentence(text, aspect, extra_seeds=ASPECT_KEYWORDS.get(aspect)) or text
        self.cnn_model.eval()
        with torch.no_grad():
            seq = encode_texts_for_cnn([clause], self.cnn_tokenizer, max_len=100)
            tensor = torch.tensor(seq, dtype=torch.long, device=self.device)
            prob_positive = float(torch.sigmoid(self.cnn_model(tensor))[0])

        if abs(prob_positive - 0.5) < self.UNCERTAIN_MARGIN:
            return [{"label": "Neutral", "score": prob_positive}]
        label = "Positive" if prob_positive >= 0.5 else "Negative"
        score = prob_positive if label == "Positive" else 1.0 - prob_positive
        return [{"label": label, "score": score}]


def load_absa_pipeline(cnn_model=None, cnn_tokenizer=None, device: str = "cpu"):
    """Returns a CNN2D-backed sentiment-given-aspect callable -- see
    _Cnn2dAspectSentiment. Requires the caller (ModelRegistry) to already
    have CNN2D loaded; raises if it isn't, same as any other "prerequisite
    not available" path in this project."""
    if cnn_model is None or cnn_tokenizer is None:
        raise RuntimeError("CNN2D model must be loaded before the ABSA pipeline (ENABLE_CNN2D=false?)")
    return _Cnn2dAspectSentiment(cnn_model, cnn_tokenizer, device)


def load_deberta_absa_pipeline(device: int = -1):
    """Loads the heavy DeBERTa-v3 ABSA model."""
    from transformers import pipeline
    return pipeline(
        "text-classification",
        model=ABSA_MODEL_DEBERTA,
        device=device,
    )


def analyze_aspects_single(pipe, text: str, aspects: list[str] | None = None, absa_method: str = "cnn2d") -> dict:
    """Score one review across each aspect with an already-loaded pipeline.
    Used by the live inference pipeline (Task 3).

    Each aspect is gated behind `_aspect_mentioned()` first -- see module
    docstring. Aspects with no keyword match are reported as "Not mentioned"
    without ever calling the model, instead of a hallucinated verdict."""
    aspects = aspects or ABSA_ASPECTS
    records = []
    for aspect in aspects:
        if not _aspect_mentioned(text, aspect):
            records.append({"aspect": aspect, "sentiment": NOT_MENTIONED_LABEL, "confidence": 0.0})
            continue
        try:
            pred = pipe(text, text_pair=aspect, truncation=True)[0]
            records.append({"aspect": aspect, "sentiment": pred["label"], "confidence": round(float(pred["score"]), 4)})
        except Exception as e:
            records.append({"aspect": aspect, "sentiment": "UNKNOWN", "confidence": 0.0, "error": str(e)})
    methodology = (
        "Sentiment-given-aspect over a fixed candidate aspect list. An aspect is only scored "
        "if RAKE keyphrase extraction finds the review's own text actually discussing it "
        "(domain-general presence check, not a fixed keyword search); otherwise it's reported "
        "as \"Not mentioned\" rather than guessed. "
    )
    if absa_method == "deberta":
        methodology += "The score itself comes from a purpose-trained ABSA model (DeBERTa-v3)."
        model_desc = ABSA_METHOD_DESCRIPTION_DEBERTA
    else:
        methodology += (
            "The score itself comes from CNN2D (the project's own binary sentiment classifier) "
            "run over just the located clause, not a purpose-trained ABSA model. Predictions close to CNN2D's 50% "
            "decision boundary are reported as \"Neutral\"."
        )
        model_desc = ABSA_METHOD_DESCRIPTION_CNN

    return {
        "available": True,
        "model": model_desc,
        "aspects": records,
        "methodology_note": methodology,
    }


def run_absa(
    reviews: pd.DataFrame,
    text_column: str = "review_comment_message_en",
    review_id_column: str = "review_id",
    aspects: list[str] | None = None,
    sample_size: int = DEFAULT_SAMPLE_SIZE,
    seed: int = 42,
    device: int = -1,
    absa_method: str = "cnn2d",
) -> dict:
    """Score `sample_size` reviews x each aspect for sentiment-given-aspect.

    Returns a long-format record list: {review_id, aspect, sentiment, confidence}.
    """
    from app.core.config import settings
    from app.ml.models import load_cnn2d_model
    from app.ml.utils import get_device

    aspects = aspects or ABSA_ASPECTS
    pool = reviews[reviews[text_column].fillna("").astype(str).str.strip() != ""]
    sample = pool.sample(min(sample_size, len(pool)), random_state=seed)

    try:
        if absa_method == "deberta":
            pipe = load_deberta_absa_pipeline(device=device)
        else:
            import pickle
            import __main__ as main_module

            from app.ml.preprocessing import SimpleVocabTokenizer

            main_module.SimpleVocabTokenizer = SimpleVocabTokenizer
            torch_device = get_device(prefer_gpu=device >= 0)
            cnn_model = load_cnn2d_model(settings.CNN_CHECKPOINT_PATH, device=torch_device)
            with open(settings.CNN_TOKENIZER_PATH, "rb") as f:
                cnn_tokenizer = pickle.load(f)
            pipe = load_absa_pipeline(cnn_model, cnn_tokenizer, device=torch_device)
    except Exception as e:
        return {"available": False, "reason": f"Could not load ABSA model ({absa_method}): {e}"}

    results = []
    for aspect in aspects:
        for review_id, text in zip(sample[review_id_column], sample[text_column]):
            if not _aspect_mentioned(text, aspect):
                results.append({
                    "review_id": review_id, "aspect": aspect,
                    "sentiment": NOT_MENTIONED_LABEL, "confidence": 0.0,
                })
                continue
            try:
                pred = pipe(text, text_pair=aspect, truncation=True)[0]
            except Exception:
                pred = {"label": "UNKNOWN", "score": 0.0}
            results.append({
                "review_id": review_id, "aspect": aspect,
                "sentiment": pred["label"], "confidence": float(pred["score"]),
            })

    model_desc = ABSA_METHOD_DESCRIPTION_DEBERTA if absa_method == "deberta" else ABSA_METHOD_DESCRIPTION_CNN
    
    return {
        "available": True,
        "model": model_desc,
        "aspects": aspects,
        "sample_size": len(sample),
        "n_predictions": len(results),
        "records": results,
        "methodology_note": (
            "This is sentiment-given-aspect over a fixed candidate aspect list. Each aspect is "
            "gated behind RAKE-based keyphrase extraction. The score comes from "
            + ("DeBERTa-v3." if absa_method == "deberta" else "CNN2D over the located aspect clause.")
        ),
    }
