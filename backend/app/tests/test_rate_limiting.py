"""Regression test for the rate-limiting fix: the public API previously had
no per-IP request limit anywhere, making it trivially cheap to hammer the
free-tier deployment. See app/core/rate_limit.py."""


def test_explain_endpoint_rate_limits_after_repeated_requests(client):
    """/explain is capped at 10/minute. The 11th request from the same
    (test) client within the window must be rejected with 429, not silently
    processed -- this is what "no rate limiting" looked like before the fix."""
    payload = {"text": "The product works great."}
    responses = [client.post("/api/v1/sentiment/explain", json=payload) for _ in range(11)]

    statuses = [r.status_code for r in responses]
    assert 429 in statuses, f"Expected a 429 among 11 rapid requests to a 10/minute-limited endpoint, got {statuses}"

    limited = next(r for r in responses if r.status_code == 429)
    body = limited.json()
    assert body["success"] is False
    assert body["error"]["code"] == "RATE_LIMITED"
