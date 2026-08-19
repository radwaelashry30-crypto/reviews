"""Regression test for a real path-traversal vulnerability (Technical Review
#13): upload_id went straight from the request path into a filesystem path
with no validation, and Starlette's percent-decoding-after-routing behavior
meant an encoded "../" (e.g. "..%2f..%2f...") could reach the filesystem
layer as a literal path segment. Fixed with a strict pattern at both the API
layer (Path(..., pattern=...)) and the storage layer (upload_store._upload_path),
per defense-in-depth -- this test exercises the actual HTTP layer end to end."""
import pytest


@pytest.mark.parametrize("bad", [
    "..%2f..%2fetc%2fpasswd",
    "../../results/business_kpis",
    "..",
    "a" * 33,
    "ABCDEF0123456789ABCDEF0123456789",  # uppercase hex, not accepted
    "x/y",
    "not-a-valid-id-at-all",
])
def test_malformed_upload_id_is_rejected(client, bad):
    r = client.get(f"/api/v1/sentiment/upload-file/{bad}")
    assert r.status_code in (404, 422), f"path traversal accepted: {bad} -> {r.status_code}"


def test_wellformed_but_unknown_upload_id_returns_404(client):
    r = client.get("/api/v1/sentiment/upload-file/" + "a" * 32)
    assert r.status_code == 404
