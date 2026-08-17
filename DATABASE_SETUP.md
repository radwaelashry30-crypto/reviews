# Database Setup

Baseera's database layer is **entirely optional**. The app runs correctly with no database at all:
predictions still work, and batch-upload results fall back to a local 7-day JSON-file store (`data/uploads/`).
Set `DATABASE_URL` to unlock durable persistence instead.

## What it adds

| Without a database | With `DATABASE_URL` set |
|---|---|
| `/predict`, `/pipeline`, `/explain` return a result, nothing is saved | Same result, plus a durable `analysis_id` you can look up later |
| Batch-upload results live in `data/uploads/*.json` for 7 days — **lost on redeploy** on hosts with ephemeral disk (e.g. Render) | Batch-upload results live in the database for 7 days — **survive redeploys** |
| No history, no feedback | `GET /sentiment/analyses` (paginated, filterable), `GET /sentiment/analyses/{id}`, `POST /sentiment/analyses/{id}/feedback` |

Deliberately **not** added: user accounts, authentication, or Orders/Products/Users tables. This project has none of those today (no login, no "create a review" journey — the Olist dataset is static analytics data, not something users CRUD), so a generic schema template would just be dead weight. If auth is added later, `prediction_feedback` is where a `user_id` column would naturally go.

## Schema

```
sentiment_analyses (id, text, cleaned_text, label, class_id, probability_positive,
                     probability_negative, confidence, model_name, source_language,
                     translated, created_at)
  ├── sentiment_analysis_aspects (id, analysis_id FK→CASCADE, aspect, sentiment, confidence)
  └── prediction_feedback        (id, analysis_id FK→CASCADE, is_correct, comment, created_at)

batch_upload_jobs (id, filename, model_name, text_column_used, rows_processed,
                    n_positive, n_negative, result_json, created_at, expires_at)
```

`batch_upload_jobs` stores the full classification result as a JSON column rather than
normalizing every row into its own table — the actual, documented pain point this closes is
"results vanish on redeploy," not "query individual rows across every past upload." That keeps
the schema small and matches how `upload_store.py` already worked (one JSON blob per upload),
just moved from a file to a database row.

## Local setup (Docker, recommended for development)

```bash
docker compose up db
```

Then set in your local `.env` (backend/, or project root — either is picked up):

```
DATABASE_URL=postgresql://baseera:baseera@localhost:5432/baseera
```

## Local setup (no Docker)

Any PostgreSQL 14+ works. Create a database and user, then set `DATABASE_URL`:

```
DATABASE_URL=postgresql://<user>:<password>@localhost:5432/<dbname>
```

SQLite also works for quick local testing (no server to run) — the test suite uses it internally:

```
DATABASE_URL=sqlite:///./dev.db
```

## Running migrations

```bash
cd backend
pip install -r requirements.txt   # includes alembic + psycopg
alembic upgrade head
```

This creates all 4 tables. Safe to re-run (Alembic tracks the applied revision in `alembic_version`).

## Production (Render)

1. Create a PostgreSQL instance (Render's dashboard: **New +** → **PostgreSQL**, free tier is enough for this workload).
2. Copy its **Internal Database URL** (not External — the backend and database both run inside Render's network, so the internal URL is faster and doesn't leave Render's infrastructure).
3. On the **backend web service**, add an environment variable: `DATABASE_URL` = that internal URL.
4. Redeploy. The app will start up and log whether the database is configured (see `/health`'s `data.database` field).
5. Run the migration once, from a shell with network access to that database (Render's dashboard has a **Shell** tab for the web service, or run it locally against the **External** URL):
   ```bash
   DATABASE_URL="<connection string>" alembic upgrade head
   ```

## Verifying it's working

```bash
curl https://your-backend/api/v1/health
# data.database.configured: true, data.database.connected: true
```

```bash
curl -X POST https://your-backend/api/v1/sentiment/predict \
  -H "Content-Type: application/json" \
  -d '{"text": "Great product, fast delivery.", "model_name": "bert"}'
# data.analysis_id will be a 32-character id (not null) when the database is reachable
```

## Reverting to no database

Unset `DATABASE_URL` (or don't set it in the first place). Nothing else needs to change — every
call site checks `db_configured()` first and degrades to its pre-database behavior automatically.
