from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class MappingRequest(BaseModel):
    # {csv_column_name: canonical_field_name}
    mapping: dict[str, str] = Field(..., min_length=1)


class ConfirmRequest(BaseModel):
    update_mode: Literal["append", "replace"]
    # The active version id the client saw at preview time -- see
    # marketplace_repository.activate_version()'s stale-preview check.
    # Pass null/omit if no version was active yet (first-ever upload).
    expected_active_version_id: str | None = None


class RollbackRequest(BaseModel):
    target_version_id: str
    expected_active_version_id: str | None = None
