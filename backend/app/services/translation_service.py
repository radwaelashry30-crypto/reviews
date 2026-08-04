"""Translation availability check + on-demand single-string translation.

The translation model is never loaded at import time or at API startup — only
when a request actually needs it (and only if ENABLE_TRANSLATION=true).
"""
from __future__ import annotations

from app.core.config import settings


def translation_available() -> bool:
    if not settings.ENABLE_TRANSLATION:
        return False
    try:
        import sentencepiece  # noqa: F401
        import transformers  # noqa: F401
        return True
    except ImportError:
        return False
