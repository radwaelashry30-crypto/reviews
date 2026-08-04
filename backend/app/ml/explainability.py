"""SHAP explainability for the fine-tuned BERT sentiment model. Notebook cells 141-143.

Does not import `shap`/`transformers.pipeline` at module import time, and
never explains an untrained model — the caller must pass an already-loaded
fine-tuned `model`/`tokenizer` (e.g. from `models.load_fine_tuned_bert`).
"""
from __future__ import annotations

DEFAULT_XAI_SAMPLE_SIZE = 8


def is_shap_available() -> bool:
    try:
        import shap  # noqa: F401
        return True
    except ImportError:
        return False


def explain_bert_predictions(
    model, tokenizer, texts: list[str], sample_size: int = DEFAULT_XAI_SAMPLE_SIZE, device: int = -1,
) -> dict:
    """Run SHAP's PartitionExplainer over up to `sample_size` texts.

    `texts` must come from the stored split manifest's test set (see
    preprocessing.load_split_manifest) — never from arbitrary unlogged rows —
    so explanations are traceable to a specific evaluation split.
    Returns a plain-text top-token summary (no HTML widget dependency), plus a
    clear 'unavailable' payload if `shap` isn't installed or explanation fails.
    """
    if not is_shap_available():
        return {"available": False, "reason": "shap package not installed"}

    import shap
    from transformers import pipeline

    sample_texts = texts[:sample_size]
    try:
        clf_pipeline = pipeline(
            "text-classification", model=model, tokenizer=tokenizer, device=device, top_k=None,
        )
        explainer = shap.Explainer(clf_pipeline)
        shap_values = explainer(sample_texts)

        id2label = {int(k): v for k, v in model.config.id2label.items()}
        pos_idx = list(id2label.values()).index("Positive")

        per_review = []
        for i, text in enumerate(sample_texts):
            tokens = shap_values[i].data
            token_values = shap_values[i].values[:, pos_idx]
            ranked = sorted(zip(tokens, token_values), key=lambda t: abs(t[1]), reverse=True)
            top_tokens = [{"token": str(tok), "shap_value": float(val)} for tok, val in ranked[:5] if str(tok).strip()]
            per_review.append({"text": text, "top_tokens_toward_positive": top_tokens})

        return {"available": True, "sample_size": len(sample_texts), "explanations": per_review}
    except Exception as e:
        return {"available": False, "reason": f"SHAP explanation failed: {e}"}
