# Architecture

CVantage is a single-deployable web application: a FastAPI backend that also serves the
built React SPA, backed by MongoDB.

## High level

```
Browser ──HTTPS──▶ FastAPI (one port)
                     ├── /api/v1/**  → REST API (domain routers → services → Beanie/Mongo)
                     └── /*          → SPA shell (frontend/dist), deep-link fallback
                              │
                              ├── MongoDB (Beanie ODM, Pydantic v2)
                              ├── LLM provider (real openai | deterministic fake)  via LangChain
                              ├── Storage (local | s3)        — behind a Protocol
                              ├── Mail (console | smtp)       — behind a Protocol
                              └── Job runner (Mongo-backed)   — behind a Protocol
```

## Backend layout

One package per domain under `server/app/` — `auth`, `users`, `resumes`, `analyses`,
`ai`, `jobs`, `admin`, `notifications`, `exports`, `health`. Each domain typically has:

- `router.py` — thin HTTP layer: tags, summaries, typed `response_model` per status code,
  examples, auth markers, error envelopes.
- `service.py` — business logic; the only layer that touches the database.
- `schemas.py` — Pydantic request/response DTOs (the privacy boundary).
- `dependencies.py` — `Depends(...)` for the current user, RBAC, pagination, config.

Cross-cutting modules: `config/` (the single `Settings` source of truth), `common/`
(error envelope + handlers), `security/` (rate limiting), `observability/`
(structlog + env-gated Sentry/OTel), `spa/` (static serving), `database/` (models + init).

## Request lifecycle

A middleware assigns a request id, enforces the body-size limit and graceful-shutdown
draining, then attaches security headers (CSP, HSTS in prod, `nosniff`, frame/permission
policies). Errors are returned as a problem-details-style JSON envelope. List endpoints
paginate; mutable aggregates use Beanie revision-based optimistic concurrency.

## Data discipline & privacy

- Placeholder/empty values are pruned before persistence (mirrors the Beanie pre-validate
  event); soft deletes (`deleted_at`) are excluded from all queries.
- Secrets (`password_hash`, `api_key_encrypted`, `token_hash`) are kept out of responses
  by the DTO layer; provider API keys are encrypted at rest (AES-256-GCM).
- **Admins see resume metadata only** — never resume or analysis content. Enforced in the
  service/DTO layer; audit logs store redacted metadata only.
- No multi-document Mongo transactions (target Mongo is standalone): atomic `$inc`,
  idempotent ordered cascades, and a periodic reconcile job.

## Analysis pipeline

`POST /analyses` runs an ordered pipeline — compare resume↔JD, generate suggestions,
prepare interview questions — recording per-step status and token usage, behind a
per-user concurrency guard. The LLM provider is chosen by env: the deterministic **fake**
provider makes the whole flow runnable offline and in tests.

## Frontend layout

`src/api/` (axios client with single-flight refresh, typed endpoints, query keys),
`src/components/ui` (themeable kit), `src/features/*` (landing, auth, dashboard, upload,
resume, analysis, admin, notifications), `src/lib/*` (auth context, theme, forms, hooks),
`src/app/` (router with lazy per-route chunks + auth/role guards). State/server-cache via
TanStack Query; forms via react-hook-form + zod.

## Observability

Structured JSON logs (structlog) with request-id correlation and secret redaction are
always on. Sentry (errors), OpenTelemetry (traces), and LangSmith/Langfuse (LLM) are
**env-gated** — zero overhead unless configured.
