"""Sentiment inference service. No FastAPI imports here — pure business logic
over an already-loaded `ModelRegistry`, callable from endpoints, scripts, or tests.

BERT path: text -> tokenizer -> padding/truncation -> model -> logits -> softmax
ONCE -> label. CNN2D path: text -> SimpleVocabTokenizer -> pad -> LongTensor ->
model -> logit -> sigmoid ONCE -> threshold -> label. Both use model.eval() +
torch.no_grad(); neither ever reloads the model or refits a tokenizer per call.
"""
from __future__ import annotations

from app.core.config import settings
from app.core.exceptions import InvalidRequestError
from app.services.model_registry import ModelRegistry

LABEL_NAMES = {0: "Negative", 1: "Positive"}


def _validate_text(text: str) -> str:
    if text is None or not text.strip():
        raise InvalidRequestError("Review text must not be empty or whitespace-only.")
    if len(text) > settings.MAX_REVIEW_LENGTH:
        raise InvalidRequestError(f"Review text exceeds MAX_REVIEW_LENGTH={settings.MAX_REVIEW_LENGTH} characters.")
    return text


def _maybe_translate(text: str, source_language: str, translate: bool) -> tuple[str, bool]:
    """Translate Portuguese input to English if requested and enabled. English input is never translated."""
    if not translate or source_language != "pt":
        return text, False
    if not settings.ENABLE_TRANSLATION:
        raise InvalidRequestError("Translation is disabled on this deployment (ENABLE_TRANSLATION=false).")
    from app.ml.translation import ACTUAL_TRANSLATION_MODEL
    from transformers import MarianMTModel, MarianTokenizer
    import torch

    tokenizer = MarianTokenizer.from_pretrained(ACTUAL_TRANSLATION_MODEL)
    model = MarianMTModel.from_pretrained(ACTUAL_TRANSLATION_MODEL)
    model.eval()
    with torch.no_grad():
        inputs = tokenizer([text], return_tensors="pt", padding=True, truncation=True, max_length=512)
        generated = model.generate(**inputs, max_length=512)
        translated = tokenizer.batch_decode(generated, skip_special_tokens=True)[0]
    return translated, True


def predict_sentiment(
    registry: ModelRegistry, text: str, model_name: str = "bert",
    source_language: str = "en", translate: bool = False,
) -> dict:
    """Predict sentiment for a single review. Raises InvalidRequestError / ModelUnavailableError."""
    import torch

    text = _validate_text(text)
    cleaned_text, translated = _maybe_translate(text, source_language, translate)

    if model_name == "bert":
        model, tokenizer = registry.require_bert()
        model.eval()
        with torch.no_grad():
            encoded = tokenizer(cleaned_text, max_length=128, padding="max_length", truncation=True, return_tensors="pt")
            encoded = {k: v.to(registry.device) for k, v in encoded.items()}
            logits = model(**encoded).logits
            probs = torch.softmax(logits, dim=1)[0]
        prob_negative, prob_positive = float(probs[0]), float(probs[1])
    elif model_name == "cnn2d":
        model, tokenizer = registry.require_cnn()
        from app.ml.datasets import encode_texts_for_cnn

        model.eval()
        with torch.no_grad():
            seq = encode_texts_for_cnn([cleaned_text], tokenizer, max_len=100)
            tensor = torch.tensor(seq, dtype=torch.long, device=registry.device)
            logit = model(tensor)
            prob_positive = float(torch.sigmoid(logit)[0])
        prob_negative = 1.0 - prob_positive
    else:
        raise InvalidRequestError(f"Unknown model_name '{model_name}'. Expected 'bert' or 'cnn2d'.")

    class_id = 1 if prob_positive >= 0.5 else 0
    return {
        "label": LABEL_NAMES[class_id],
        "class_id": class_id,
        "probability_positive": round(prob_positive, 4),
        "probability_negative": round(prob_negative, 4),
        "confidence": round(max(prob_positive, prob_negative), 4),
        "model_name": model_name,
        "source_language": source_language,
        "translated": translated,
        "cleaned_text": cleaned_text,
    }


def predict_sentiment_batch(
    registry: ModelRegistry, items: list[dict], model_name: str = "bert",
) -> list[dict]:
    """Predict sentiment for a batch. Each item is {"id": str, "text": str}. Preserves input IDs."""
    if len(items) > settings.MAX_BATCH_SIZE:
        raise InvalidRequestError(f"Batch size {len(items)} exceeds MAX_BATCH_SIZE={settings.MAX_BATCH_SIZE}.")
    if not items:
        raise InvalidRequestError("Batch must contain at least one item.")

    results = []
    for item in items:
        prediction = predict_sentiment(registry, item["text"], model_name=model_name)
        results.append({"id": item["id"], **prediction})
    return results
