# Migrations

Alembic migrations for the optional database persistence layer (sentiment-analysis history,
feedback, durable batch-upload records). See [`DATABASE_SETUP.md`](../../DATABASE_SETUP.md) at
the project root for setup, and [`app/db/models.py`](../app/db/models.py) for the schema.

This app runs correctly without any of this configured — `DATABASE_URL` unset means no
persistence, not a crash. Analytics KPIs/dashboards (`app/repositories/analytics_repository.py`)
are unrelated and still served from cached Parquet/JSON files, not this database.

```bash
alembic upgrade head          # apply all migrations
alembic revision --autogenerate -m "description"   # generate a new migration after changing app/db/models.py
```

`env.py` reads the connection string from `app.core.config.settings.DATABASE_URL` (never
hardcoded in `alembic.ini`), falling back to a local `dev.db` SQLite file when unset, so
migrations can be generated/tested without a real Postgres connection available.
