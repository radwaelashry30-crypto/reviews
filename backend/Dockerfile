# Multi-stage build: the builder stage installs dependencies (needs pip's
# resolver, wheel-building toolchain, etc.); the final stage only copies the
# installed packages + source, not the build tooling. Also installs the
# CPU-only torch wheel (~200MB) instead of the default CUDA-bundled one
# (~2GB+) -- this app never touches a GPU (self.device defaults to "cpu" in
# production; see app/services/model_registry.py), so the CUDA runtime was
# pure dead weight. Both changes were deliberately deferred earlier (see
# CHANGELOG.md / Technical Review #20) until there was a real Docker build
# to verify them against -- this is now verified through the CI docker job
# (build + boot + /api/v1/health check) before being merged to main, not
# shipped straight to the live Render deployment unverified.
FROM python:3.11-slim AS builder

WORKDIR /build
COPY backend/requirements.txt .
RUN pip install --no-cache-dir --prefix=/install \
    --extra-index-url https://download.pytorch.org/whl/cpu \
    -r requirements.txt

FROM python:3.11-slim

RUN useradd --create-home --uid 10001 appuser
COPY --from=builder /install /usr/local

WORKDIR /app
COPY --chown=appuser:appuser backend /app/backend
COPY --chown=appuser:appuser models /app/models
COPY --chown=appuser:appuser artifacts /app/artifacts
COPY --chown=appuser:appuser config /app/config
COPY --chown=appuser:appuser data/processed /app/data/processed
COPY --chown=appuser:appuser results /app/results
USER appuser

WORKDIR /app/backend
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=90s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/api/v1/health').status==200 else 1)"

# Fails clearly at startup if a REQUIRED artifact is missing (see app/services/model_registry.py);
# optional artifacts degrade to a documented "unavailable" status instead of crashing the app.
# --proxy-headers/--forwarded-allow-ips: this always runs behind a reverse
# proxy (Render). Without this, uvicorn ignores X-Forwarded-For entirely and
# app.core.rate_limit's client_identity() falls back to the proxy's own
# address for every request -- see Technical Review #15.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", \
     "--proxy-headers", "--forwarded-allow-ips", "*"]
