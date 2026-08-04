def test_health_endpoint(client):
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["status"] == "healthy"
    assert "request_id" in body["meta"]


def test_openapi_available(client):
    resp = client.get("/openapi.json")
    assert resp.status_code == 200
    assert resp.json()["info"]["title"]


def test_docs_available(client):
    resp = client.get("/docs")
    assert resp.status_code == 200


def test_cors_headers_present(client):
    resp = client.options(
        "/api/v1/health",
        headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "GET"},
    )
    assert resp.status_code in (200, 204)
    assert "access-control-allow-origin" in {k.lower() for k in resp.headers.keys()}


def test_unknown_route_returns_404(client):
    resp = client.get("/api/v1/does-not-exist")
    assert resp.status_code == 404
