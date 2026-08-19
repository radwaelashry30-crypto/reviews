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

WORKDIR /app/backend
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

# Fails clearly at startup if a REQUIRED artifact is missing (see app/services/model_registry.py);
# optional artifacts degrade to a documented "unavailable" status instead of crashing the app.
# --proxy-headers/--forwarded-allow-ips: this always runs behind a reverse
# proxy (Render). Without this, uvicorn ignores X-Forwarded-For entirely and
# app.core.rate_limit's client_identity() falls back to the proxy's own
# address for every request -- see Technical Review #15.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", \
     "--proxy-headers", "--forwarded-allow-ips", "*"]
