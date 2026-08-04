# Migrations

This project currently has no relational database — all data access is via cached Parquet/JSON files loaded once at API startup (`app/repositories/analytics_repository.py`). This directory is a placeholder for future schema migrations (e.g. Alembic) if a database is introduced for persisting predictions, user accounts, or a live-updating analytics store.

When adding a database:
1. Introduce SQLAlchemy models under `app/ml` or a new `app/db/` package.
2. Add Alembic (`pip install alembic`, `alembic init migrations`).
3. Keep migrations here, versioned alongside the code that depends on them.
