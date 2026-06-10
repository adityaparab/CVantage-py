# CVantage Server

FastAPI backend scaffold for CVantage.

## Ops Commands

- Seed admin user (idempotent):
	- `uv run python -m app.cli seed-admin`
- Verify/sync Beanie indexes:
	- `uv run python -m app.cli sync-indexes`
