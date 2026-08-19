FROM python:3.11-slim

WORKDIR /app

COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

COPY backend /app/backend
COPY models /app/models
COPY artifacts /app/artifacts
COPY config /app/config
COPY data/processed /app/data/processed
COPY results /app/results

# Runs as a non-root user rather than the container default (root) --
# reduces the blast radius of a dependency RCE. See Technical Review #20.
# (A multi-stage build + CPU-only torch wheel were also identified as
# worthwhile size/attack-surface reductions, but were deliberately NOT
# applied here: this Dockerfile is what Render actually builds from for the
# live deployment, and this environment has no running Docker daemon to
# verify a rewritten multi-stage build actually produces a working image
# before it would go live -- not a change to ship unverified.)
RUN useradd --create-home --uid 10001 appuser \
    && chown -R appuser:appuser /app
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
