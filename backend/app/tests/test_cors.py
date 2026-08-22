"""CORS preflight coverage for POST endpoints.

Regression test for a real bug found during the Phase 3B frontend audit: the
frontend sends a custom `Idempotency-Key` header on every POST (see
frontend/src/api/client.ts), but `allow_headers` in app/main.py only listed
`Content-Type` and `X-API-Key`. The browser's CORS preflight for that header
combination then failed and no POST request from the frontend ever reached
the backend -- confirmed by tracing a real `net::ERR_FAILED` in a headless
browser while a direct `curl` to the same endpoint succeeded. Fixed by adding
`Idempotency-Key` to `allow_headers`; this test pins that behavior so it
can't silently regress.
"""

FRONTEND_ORIGIN = "http://localhost:5173"
UNAUTHORIZED_ORIGIN = "http://evil.example.com"

REQUESTED_HEADERS = "content-type, x-api-key, idempotency-key"


def _preflight(client, origin: str):
    return client.options(
        "/api/v1/sentiment/predict",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": REQUESTED_HEADERS,
        },
    )


def test_legitimate_origin_receives_cors_permission(client):
    resp = _preflight(client, FRONTEND_ORIGIN)
    assert resp.status_code in (200, 204)
    assert resp.headers.get("access-control-allow-origin") == FRONTEND_ORIGIN


def test_post_method_is_allowed(client):
    resp = _preflight(client, FRONTEND_ORIGIN)
    allowed_methods = {m.strip().upper() for m in resp.headers.get("access-control-allow-methods", "").split(",")}
    assert "POST" in allowed_methods


def test_required_headers_are_allowed(client):
    resp = _preflight(client, FRONTEND_ORIGIN)
    allowed_headers = {h.strip().lower() for h in resp.headers.get("access-control-allow-headers", "").split(",")}
    assert "content-type" in allowed_headers
    assert "x-api-key" in allowed_headers
    assert "idempotency-key" in allowed_headers


def test_unauthorized_origin_is_not_granted_cors_access(client):
    resp = _preflight(client, UNAUTHORIZED_ORIGIN)
    # Starlette's CORSMiddleware still answers the OPTIONS request itself
    # (no origin check gates that), but must not echo back an
    # Access-Control-Allow-Origin the browser would accept as permission --
    # that's the actual security-relevant assertion, not the status code.
    assert resp.headers.get("access-control-allow-origin") != UNAUTHORIZED_ORIGIN
