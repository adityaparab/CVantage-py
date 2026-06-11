# Operations Runbook

Operational procedures for CVantage: build, deploy, roll back, back up, restore, and
respond to incidents. The app ships as a **single container** — FastAPI serving the built
SPA on one port — backed by MongoDB.

## Health checks

| Probe | Path | Meaning |
|-------|------|---------|
| Liveness | `GET /api/v1/health/live` | process is up |
| Readiness | `GET /api/v1/health/ready` | dependencies (Mongo, disk, memory) OK |

Point the platform's health check at the readiness probe. A non-200 readiness pulls the
instance out of rotation.

## Configuration

All config is environment variables, validated at boot (the process **fails fast** on a
bad/missing required value). Keep production env in the platform's secret store, mirrored
against [`.env.example`](../.env.example). Required in production:

- `ENVIRONMENT=production`, `MONGODB_URI`, `MONGODB_DB_NAME`
- `AUTH_ACCESS_TOKEN_SECRET` (strong random), `MASTER_ENCRYPTION_KEY` (32-byte base64)
- `CORS_ORIGINS` (the deployed web origin), `AUTH_COOKIE_SECURE=true`
- `ADMIN_EMAIL` / `ADMIN_PASSWORD` (seeds the first admin), optional `OPENAI_API_KEY`
- Optional: `SENTRY_DSN`, `OTEL_ENABLED` + `OTEL_EXPORTER_OTLP_ENDPOINT`

In production `SERVE_SPA` defaults on and Swagger is disabled.

## Build & deploy

The image is built by the multi-stage `Dockerfile`: stage 1 builds the SPA (`pnpm build`),
stage 2 installs backend deps (`uv sync`) and copies `frontend/dist` in, then runs
gunicorn with uvicorn workers.

```bash
docker build -t cvantage:$(git rev-parse --short HEAD) .
docker run -p 8000:8000 --env-file .env.production cvantage:<tag>
```

Deploy (platform, e.g. Railway):

1. Push to the deploy branch / trigger the pipeline; CI must be green (lint, types, tests,
   build, audits).
2. The platform builds the image and starts it with the production env.
3. Wait for the **readiness** probe to pass, then confirm the SPA loads and
   `GET /api/v1/health/ready` is 200.
4. Tag the release (the commit SHA is the image tag) for traceability.

## Rollback

Releases are immutable images tagged by commit SHA.

1. Identify the last-known-good tag (previous successful deploy).
2. Redeploy that image tag on the platform (or `docker run` it).
3. Verify readiness + a smoke check (login, dashboard, run one analysis).

No schema migrations are destructive by default (soft deletes, additive fields), so a code
rollback is safe. If a release added a new required env var, restore the prior env too.

## Backup & restore (MongoDB)

**Backup** (schedule daily; before any risky change):

```bash
mongodump --uri "$MONGODB_URI" --gzip --archive=cvantage-$(date +%F).gz
```

**Restore** (into a fresh/standby DB first, verify, then cut over):

```bash
mongorestore --uri "$MONGODB_URI" --gzip --archive=cvantage-YYYY-MM-DD.gz --drop
```

Store archives off-host (object storage) with retention. Test a restore periodically.

## Incident response

1. **Triage** — check readiness probe, recent deploys, and error volume (Sentry if
   `SENTRY_DSN` set). Correlate by `X-Request-ID` (every response carries one; logs are
   keyed by it).
2. **Stabilize** — if a recent release is implicated, **roll back** first, investigate
   after. If a dependency (Mongo) is down, readiness will fail and traffic drains.
3. **Logs** — structured JSON with secret redaction. Filter by `request_id`, `path`,
   `status_code`.
4. **Rate-limit / abuse** — limits are configurable via `RATE_LIMIT_*`; tighten and
   redeploy if under abuse.
5. **Postmortem** — record cause, fix, and prevention; add a regression test.

## Routine maintenance

- **Dependency audits:** `uvx pip-audit` (server) and `pnpm audit --audit-level high`
  (frontend) — wired into CI; patch high/critical promptly.
- **Reconcile job:** the Mongo-backed job runner reconciles cascade state periodically;
  confirm it is scheduled in production.
- **Key rotation:** rotate `AUTH_ACCESS_TOKEN_SECRET` (invalidates sessions) and provider
  API keys (admin UI → AI models → rotate) on a schedule or after suspected exposure.
