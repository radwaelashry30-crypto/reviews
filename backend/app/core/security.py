"""Minimal security scaffolding.

No authentication is enforced today (this is a local/academic deployment).
`get_optional_api_key` is wired into `dependencies.py` so real API-key
enforcement can be added later by raising inside it, without touching every
endpoint.
"""
from __future__ import annotations

from fastapi import Header


async def get_optional_api_key(x_api_key: str | None = Header(default=None)) -> str | None:
    """Placeholder for future auth. Currently accepts any value, including None."""
    return x_api_key
