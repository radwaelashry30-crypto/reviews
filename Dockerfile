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
#
# NOTE: this root-level Dockerfile is a duplicate of backend/Dockerfile, kept
# in sync manually, ONLY because Hugging Face Spaces' Docker SDK requires a
# Dockerfile at the repository root. Local/docker-compose development should
# keep using backend/Dockerfile via docker-compose.yml.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
