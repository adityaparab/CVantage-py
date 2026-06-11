# CVantage

AI-powered resume analysis for job seekers. Candidates create or upload a resume,
analyze it against a job description, and get an ATS/match score with prioritized,
one-click-applyable suggestions and tailored interview questions. Admins manage users
and AI-model credentials — and **never** see resume or analysis content.

- **Backend:** Python 3.11 · FastAPI · MongoDB + Beanie (Pydantic v2) · LangChain · uv
- **Frontend:** React 19 · TypeScript · Vite · Tailwind v4 · TanStack Query · pnpm
- **Single-server production:** FastAPI serves the built SPA (`frontend/dist`) on one port.

> Build constraints and the working agreement live in [CLAUDE.md](CLAUDE.md); the
> functional spec in [PROMPT.md](PROMPT.md); the implementation plan in [PLAN.md](PLAN.md);
> progress in [STATUS.md](STATUS.md). Architecture: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).
> Operations: [docs/RUNBOOK.md](docs/RUNBOOK.md).

---

## Prerequisites

| Tool | Version | Notes |
|------|---------|-------|
| Python | 3.11 | pinned via `.python-version` |
| [uv](https://docs.astral.sh/uv/) | latest | Python package/dependency manager |
| Node.js | 22 LTS | enable Corepack: `corepack enable` |
| pnpm | 10 | provided via Corepack |
| Docker | latest | for local MongoDB |

## Quick start (clone → running in ~10 minutes)

```bash
# 1. Local MongoDB
docker compose --profile db up -d          # healthy mongo on localhost:27017

# 2. Backend (from server/)
cd server
cp ../.env.example .env                     # fill in secrets as needed (see below)
uv sync
uv run uvicorn app.main:app --reload        # http://localhost:8000  (docs: /api/docs)

# 3. Frontend (from frontend/, in a second terminal)
cd frontend
pnpm install
pnpm dev                                     # http://localhost:5173, proxies /api → :8000
```

Open <http://localhost:5173>. On first boot the server seeds an admin user from
`ADMIN_EMAIL` / `ADMIN_PASSWORD` if set. With no `OPENAI_API_KEY` and no configured AI
model, analyses run against the **deterministic fake LLM provider**, so the full flow
works offline.

## Configuration

All config is environment-driven and validated at boot by a `pydantic-settings` model
(fail-fast). [`.env.example`](.env.example) is the exhaustive, in-sync reference. Key groups:

- **Core:** `ENVIRONMENT`, `PORT`, `LOG_LEVEL`, `CORS_ORIGINS`.
- **Auth/secrets:** `AUTH_ACCESS_TOKEN_SECRET`, `MASTER_ENCRYPTION_KEY` (AES-256-GCM for
  provider keys), `ADMIN_EMAIL`/`ADMIN_PASSWORD`.
- **AI:** `OPENAI_API_KEY` (optional fallback; models are normally managed in the admin UI).
- **SPA serving:** `SERVE_SPA` (on by default in production), `SPA_DIST_DIR`.
- **Observability (all env-gated, zero overhead when unset):** `SENTRY_DSN`,
  `OTEL_ENABLED` + `OTEL_EXPORTER_OTLP_ENDPOINT`, `LANGSMITH_TRACING`.

## Common commands

```bash
# Backend (from server/)
uv run uvicorn app.main:app --reload         # dev server
uv run ruff check . && uv run ruff format .  # lint + format
uv run mypy .                                # types (strict)
uv run pytest --cov                          # tests + coverage (≥80%)

# Frontend (from frontend/)
pnpm dev                                     # Vite dev server
pnpm lint && pnpm typecheck                  # lint + types
pnpm test                                    # Vitest + RTL + MSW
pnpm build && pnpm perf:budget               # production build + JS budget check
pnpm e2e                                     # Playwright E2E (run pnpm e2e:install once)
pnpm audit                                   # high+ dependency audit
```

## Project structure

```
server/app/        one package per domain (auth, users, resumes, analyses, ai, admin,
                   notifications, exports, …); router/service/schemas per domain
server/tests/      pytest suite mirroring the package layout (mongomock fixtures)
frontend/src/      api/ · components/ui · features/ · lib/ · app/ (router, guards)
frontend/e2e/      Playwright specs
database/          canonical Beanie model reference
docs/              ARCHITECTURE.md, RUNBOOK.md
```

## API documentation

Interactive OpenAPI docs are served at **`/api/docs`** (Swagger) and **`/api/redoc`**
in non-production environments. Every endpoint ships typed response models per status
code, examples, and auth markers; a convention test fails CI if a route is
under-documented. The frontend consumes types generated from the OpenAPI spec.

## Testing & quality gates

`ruff` · `mypy --strict` · `pytest` (≥80% coverage; ≥85% auth/admin) · `eslint` ·
`tsc` · `vitest` (≥80% on api/lib/components-ui) · `playwright` · automated `axe`
accessibility checks · a gzipped-JS bundle budget. Pre-commit hooks + conventional
commits (commitizen) are enforced — see [CONTRIBUTING.md](CONTRIBUTING.md).

## Deployment

Single container: a multi-stage build compiles the SPA and serves it from FastAPI on
one port. See [docs/RUNBOOK.md](docs/RUNBOOK.md) for build, deploy, rollback, backup,
restore, and incident procedures.

## Security

argon2id password hashing · JWT access + rotating refresh tokens (httpOnly cookies,
reuse detection) · RBAC + resource-ownership checks · provider keys encrypted at rest ·
strict CORS allowlist · rate limiting · CSP/HSTS security headers · structured logs with
secret redaction. **Admins see resume metadata only — never content.** Auth review notes:
[SECURITY_REVIEW_AUTH.md](SECURITY_REVIEW_AUTH.md).
