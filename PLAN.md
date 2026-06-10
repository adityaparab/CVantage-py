# CVantage — End-to-End Implementation Plan

> **Status: DRAFT — awaiting approval.** Nothing is implemented and no GitHub issues are created until this plan is approved.
>
> Repo: <https://github.com/adityaparab/CVantage> (currently empty) · Owner: Adi (mradityaparab@gmail.com)

---

## 1. Overview

CVantage is an AI-powered resume analysis platform for job seekers (per `PROMPT.md`):

- **Candidates** register/login (email + Google/LinkedIn OAuth), create resumes via a full json-resume-schema editor or upload PDF/DOC/DOCX files that are AI-parsed into json-resume format, run JD-vs-resume analyses (3-step AI pipeline: compare → suggestions → interview questions), view scored results, apply suggestions field-by-field, and export to PDF/DOCX.
- **Admins** (same login, backend RBAC) manage users, view platform stats, manage resumes (metadata only — never content), and manage AI models/API keys.

**Stack (per `CLAUDE.md`):** NestJS + MongoDB/Mongoose (schema already designed in `database/nestjs-mongoose/schemas.ts`) · React + TypeScript + Vite + Tailwind + TanStack Query (`frontend/`) · LangChain + langchain-openai · zod everywhere · Yarn classic workspaces (latest 1.x) as package manager — no corepack · server serves `frontend/dist` as SPA · precommit hooks + commit message validation.

**Deployment targets:** local (non-Docker), local (Docker Compose), Railway (Docker image + Railway Mongo service).

## 2. Source Documents

| File                                  | Role                                                                |
| ------------------------------------- | ------------------------------------------------------------------- |
| `CLAUDE.md`                           | Build constraints (stack, architecture rules)                       |
| `PROMPT.md`                           | Functional requirements (candidate + admin features)                |
| `cvantage-mockup.html`                | Visual reference (Pinecone-like, light/dark, responsive)            |
| `database/nestjs-mongoose/schemas.ts` | Canonical data model (7 collections) — ported as-is into the server |

## 3. Key Decisions & Assumptions

| #   | Decision                                                                                                                                                                                                                                                                                                | Rationale                                                                                                                      |
| --- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------ |
| D1  | **Monorepo with Yarn workspaces**: `server/`, `frontend/`, `shared/` (+ root tooling)                                                                                                                                                                                                                   | Shared zod schemas (json-resume, DTOs) used by both sides; single hook/CI config                                               |
| D2  | **Yarn classic, latest 1.x (currently 1.22.22), workspaces = package manager; Node 22 LTS = runtime. No corepack** — Yarn installed conventionally (bundled with `node` Docker images and GitHub runners; locally `npm i -g yarn`); version constrained via `engines.yarn: "^1.22.0"` + `engine-strict` | Per `CLAUDE.md`; classic node_modules resolution — fully supported by NestJS CLI/Vite, zero PnP surface                        |
| D3  | **Issues created via GitHub REST API** with a fine-grained PAT you provide (Issues + Contents r/w). Epics as parent issues, tasks linked via the sub-issues API                                                                                                                                         | Confirmed with you; fully automated, traceable                                                                                 |
| D4  | **OAuth (Google/LinkedIn) feature-flagged**: fully implemented, a provider activates only when its keys exist in `.env`; frontend discovers enabled providers via `GET /api/v1/auth/providers`                                                                                                          | Confirmed with you                                                                                                             |
| D5  | **MongoDB**: local Mongo via `.env` locally; Railway Mongo service in production. URI is always env-driven                                                                                                                                                                                              | Confirmed with you                                                                                                             |
| D6  | **Extras in scope**: Swagger (exhaustive, example-rich — see 1.9 + global DoD), SSE live progress, Sentry, Playwright E2E, structured logging, OpenTelemetry (traces/metrics), LLM observability (LangSmith env-native; optional Langfuse)                                                              | Confirmed with you                                                                                                             |
| D7  | **Background jobs: Mongo-backed job runner** (atomic claim via `findOneAndUpdate`, heartbeat, recovery on boot, retry ≤ 5 w/ backoff) behind a `JobRunner` interface so BullMQ/Redis can be swapped in later                                                                                            | Schema already has the worker-queue index; avoids a Redis dependency on Railway; still configurable/extensible per `CLAUDE.md` |
| D8  | **File storage behind `StorageService` interface**: `local` driver (disk / Railway volume) default; `s3` driver (any S3-compatible) optional via env                                                                                                                                                    | Schema stores `storageKey`, never bytes in Mongo; Railway needs a volume                                                       |
| D9  | **LLM provider resolution**: admin-managed `aimodels` collection (AES-256-GCM-encrypted keys) → fallback to `.env` (`OPENAI_API_KEY`, `OPENAI_BASE_URL`, model names per usage). `LLM_PROVIDER=fake` gives a deterministic provider for tests/E2E                                                       | Satisfies admin Settings feature + works before any model is configured; OpenAI-compatible `baseURL` covers OpenRouter etc.    |
| D10 | **Text extraction**: PDF via LangChain `PDFLoader`; `.docx` via mammoth (per `CLAUDE.md`); legacy `.doc` via `word-extractor` fallback (mammoth does not support binary `.doc`)                                                                                                                         | Honors `CLAUDE.md` while actually supporting `.doc` as `PROMPT.md` requires                                                    |
| D11 | **Resume export**: DOCX via `docx` package; PDF via Puppeteer (HTML print template; Chromium baked into the Docker image)                                                                                                                                                                               | Highest-fidelity output matching the in-app resume view                                                                        |
| D12 | **Auth**: argon2id password hashing; short-lived JWT access token + rotating refresh token in httpOnly cookies; refresh tokens stored hashed in `authtokens` (TTL) with reuse detection                                                                                                                 | Matches `authtokens` schema; production-grade session security                                                                 |
| D13 | **Email**: `MailService` abstraction — `console` driver (default, logs the email) / `smtp` driver via env                                                                                                                                                                                               | Password reset & verification work locally with zero setup                                                                     |
| D14 | **Realtime**: SSE endpoints for analysis progress + notifications, heartbeats every 15s; TanStack Query polling as automatic fallback                                                                                                                                                                   | Confirmed with you; SSE survives Railway's proxy with heartbeats                                                               |
| D15 | **No multi-document Mongo transactions** (Railway Mongo = standalone, no replica set). Counters maintained with atomic `$inc` + a periodic reconcile job; cascades done as ordered idempotent operations                                                                                                | Transactions require a replica set; design must not depend on it                                                               |
| D16 | **Admin bootstrap via seed**: first admin created by a seed script from `ADMIN_EMAIL`/`ADMIN_PASSWORD` env (PROMPT forbids an admin registration flow)                                                                                                                                                  | Otherwise no admin can ever exist                                                                                              |
| D17 | Server testing: Jest (+ supertest, mongodb-memory-server). Frontend: Vitest + RTL + MSW. E2E: Playwright against Docker Compose with `LLM_PROVIDER=fake`                                                                                                                                                | Ecosystem defaults; deterministic AI for E2E                                                                                   |
| D18 | API style: REST under `/api/v1`, problem-details-style error envelope, cursor/offset pagination on all list endpoints                                                                                                                                                                                   | `CLAUDE.md` global prefix; consistency                                                                                         |

## 4. Production-Readiness Baseline — _absolutely necessary_ (all in scope)

**Security**

- Secrets only via env (`.env` git-ignored, `.env.example` maintained); fail-fast zod validation of all env at boot
- AuthN/AuthZ on every endpoint: JWT + refresh rotation, RBAC guards, resource-ownership checks (no IDOR — users can only reach their own resumes/analyses)
- Input validation at every boundary (zod DTOs, file size/MIME/magic-byte checks), output sanitization (secrets `select:false`, masked keys, no stack traces in prod)
- Password hashing (argon2id), encrypted-at-rest provider API keys (AES-256-GCM), hashed tokens
- helmet security headers, strict CORS allowlist, rate limiting (global + tight buckets on auth/upload/analysis), request body limits, secure/httpOnly/SameSite cookies
- Dependency audit + secret scanning (gitleaks) in CI

**Reliability**

- Health endpoints (`/health/live`, `/health/ready` incl. Mongo ping) wired to Docker/Railway healthchecks
- Graceful shutdown (SIGTERM: stop intake, drain jobs, close Mongo)
- Timeouts + bounded retries with backoff on all LLM/external calls; job recovery after crash/restart (no stuck `in_progress`)
- Idempotent, resumable background jobs; optimistic concurrency on mutable aggregates (already in schema)
- Defined error taxonomy + consistent error envelope; user-visible failure states (upload parse failed, analysis failed → retry)

**Observability**

- Structured JSON logs (pino) with request-id correlation, redaction of secrets/PII; log levels via env
- Error tracking (Sentry, client + server, env-gated)
- OpenTelemetry traces + metrics (OTLP, env-gated): HTTP, Mongoose, job runner, per-LLM-step spans; trace-id injected into logs
- LLM observability: LangSmith (env-native) / optional Langfuse — prompt, latency, token usage per chain

**Quality & Delivery**

- CI gates on every PR: lint, typecheck, unit tests, API e2e, build, docker build, audit; Playwright on main
- Precommit hooks (lint+fix, related tests) + conventional-commit message validation (per `CLAUDE.md`)
- Reproducible builds (lockfile, pinned base images, multi-stage Docker, non-root user)
- Seed + index-sync scripts (admin bootstrap, deterministic indexes in prod where `autoIndex` is off)

**Data**

- All indexes from the schema actually created & verified; TTL collections working (tokens, notifications, audit logs)
- Soft delete honored everywhere (every query excludes `deletedAt != null`); audit log on sensitive/admin actions
- Pagination on every list endpoint; bounded payload sizes (JD ≤ 50k chars, resume text ≤ 200k)
- Backup/restore documented for Railway Mongo volume (and `mongodump` runbook)

**Documentation & Ops**

- README setup matrix (local, Docker, Railway), `.env.example` with every variable documented, ops runbook (deploy, rollback, rotate keys, restore), exhaustive API docs (Swagger — every endpoint with schemas + request/response examples)

## 5. Good-to-Have (catalogued; ✅ = promoted into scope by you)

- ✅ Swagger/OpenAPI UI · ✅ SSE realtime · ✅ Sentry · ✅ Playwright E2E · ✅ OpenTelemetry tracing/metrics · ✅ LLM observability
- Redis + BullMQ queue (interface-ready via D7) · response caching layer · CDN for static assets
- Preview environments per PR; blue/green deploys; staging environment
- Load testing (k6) + performance budgets in CI beyond Lighthouse
- Upload antivirus scanning (ClamAV) · stricter CSP with nonces · WAF
- Feature-flag service (config-driven flags are in scope; a flag _service_ is not)
- i18n/l10n · Storybook for the component library · visual regression tests
- Renovate/Dependabot auto-updates · release automation (release-please/changesets)
- Secrets manager (Doppler/Vault) instead of raw env · multi-region/HA Mongo (Atlas)
- LLM response caching & A/B prompt experiments; queue-level cost budgets per user/day

## 6. Claude Skills — recommendations for this build

| Skill                              | Status                | Use                                                                                                                                                                          |
| ---------------------------------- | --------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `review` (PR review)               | already available     | Run on every phase's PR before merge                                                                                                                                         |
| `security-review`                  | already available     | Run at Phase 2 (auth), Phase 6 (admin), and Phase 10 hardening                                                                                                               |
| `skill-creator`                    | already available     | Use it to create the two custom skills below                                                                                                                                 |
| **Custom: `cvantage-conventions`** | recommended to create | Encodes this repo's module template, naming, test patterns, commit/branch/PR rules, issue workflow — keeps every future session consistent without re-reading the whole plan |
| **Custom: `github-issue-sync`**    | optional              | Wraps the GitHub REST/sub-issue API calls + label/milestone conventions used here for reuse in other projects                                                                |

Document-format skills (docx/pdf/pptx/xlsx) are not needed — the app's own PDF/DOCX export is application code (D11), not a Claude skill concern.

## 7. Architecture

### 7.1 Repository layout

```
CVantage/
├── PLAN.md  PROMPT.md  CLAUDE.md  cvantage-mockup.html
├── package.json              # yarn 1.x workspaces: server, frontend, shared; root scripts; engines.yarn ^1.22.0
├── docker-compose.yml        # profiles: db (mongo only) | full (app + mongo)
├── Dockerfile                # multi-stage: yarn build → node:22-slim + chromium
├── railway.json              # healthcheck path, restart policy, build config
├── .github/workflows/        # ci.yml, e2e.yml
├── .husky/                   # pre-commit, commit-msg
├── shared/                   # @cvantage/shared — zod: json-resume schema, DTOs, enums, prune util
├── server/
│   └── src/
│       ├── main.ts           # bootstrap: prefix /api/v1, helmet, cors, otel, swagger, shutdown hooks
│       ├── app.module.ts
│       ├── config/           # zod-validated typed config (fail-fast)
│       ├── database/         # schemas (ported from database/nestjs-mongoose/schemas.ts), seeds, index-sync
│       ├── common/           # filters, interceptors, pipes, decorators, pagination, error envelope
│       ├── observability/    # pino logger, otel sdk, sentry, request-id ALS
│       ├── health/
│       ├── auth/             # local + jwt + refresh rotation + google/linkedin (flagged) + RBAC guards
│       ├── users/
│       ├── mail/             # MailService: console | smtp
│       ├── storage/          # StorageService: local | s3
│       ├── resumes/          # CRUD, upload, extraction (pdf/docx/doc), placeholder pruning
│       ├── ai/               # model registry (encrypted keys), LlmService (langchain), prompts, fake provider
│       ├── jobs/             # Mongo-backed JobRunner (claim/heartbeat/retry/recover)
│       ├── analyses/         # 3-step pipeline, endpoints, SSE progress, suggestion apply
│       ├── notifications/    # bell notifications + SSE stream
│       ├── exports/          # pdf (puppeteer) / docx (docx lib)
│       ├── admin/            # stats, user mgmt, model settings (RBAC: admin)
│       ├── audit/
│       └── spa/              # serve frontend/dist, SPA fallback (non-/api), cache headers
└── frontend/
    └── src/
        ├── app/              # router, providers (query, theme, auth), layouts, guards
        ├── api/              # axios client, refresh-once queue, typed endpoints, query keys
        ├── components/ui/    # Button, Input, Select, Modal, Table, Badge, Toast, Skeleton, …
        ├── features/
        │   ├── landing/  auth/  dashboard/
        │   ├── resume/       # editor (full json-resume form), view + in-place edit, upload review
        │   ├── analysis/     # start, progress (SSE), results, apply-suggestions
        │   ├── notifications/
        │   └── admin/        # dashboard, users, user-details, settings
        ├── hooks/  lib/  styles/ (tailwind tokens, light/dark)
        └── test/             # vitest setup, MSW handlers
```

### 7.2 Core flows

- **Upload → parse**: `POST /resumes/upload` (multer, ≤10 MB, MIME+magic bytes) → store via StorageService → extract text (pdf-loader / mammoth / word-extractor) → create Resume(`source=uploaded`, `uploadParse.status=pending`) → enqueue parse job → LLM structured-output (zod json-resume) → status transitions streamed over SSE → client lands on split-view review screen.
- **Analysis**: `POST /analyses` (name + JD 30–50k chars, resume preselected) → snapshot resume → job runner executes 3 steps, persisting step status + results → SSE progress + bell notification (one active per analysis, replaced in place) → results screen → apply suggestions (per `fieldRef`, marks `applied`) → save → export.
- **AuthZ boundary**: every resume/analysis query is `{ _id, userId: currentUser, deletedAt: null }`. Admin endpoints live under `/admin/**` (role guard) and can never return resume/analysis _content_ — metadata only (PROMPT requirement).
- **SPA serving**: non-`/api` routes → `index.html` (no-cache); hashed assets → immutable cache; unknown `/api/**` → JSON 404.

### 7.3 Environment matrix (`.env.example` will document each)

| Group                           | Variables                                                                                                                                                            |
| ------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Core                            | `NODE_ENV`, `PORT`, `APP_BASE_URL`, `LOG_LEVEL`, `CORS_ORIGINS`, `SWAGGER_ENABLED`                                                                                   |
| Mongo                           | `MONGODB_URI`                                                                                                                                                        |
| Auth                            | `JWT_ACCESS_SECRET`, `JWT_REFRESH_SECRET`, `JWT_ACCESS_TTL=15m`, `JWT_REFRESH_TTL=30d`, `COOKIE_SECRET`                                                              |
| OAuth (optional → feature flag) | `GOOGLE_CLIENT_ID/SECRET`, `LINKEDIN_CLIENT_ID/SECRET`, `OAUTH_CALLBACK_BASE_URL`                                                                                    |
| Crypto                          | `MASTER_ENCRYPTION_KEY` (32-byte base64; encrypts provider API keys)                                                                                                 |
| Seed                            | `ADMIN_EMAIL`, `ADMIN_PASSWORD` (first-admin bootstrap)                                                                                                              |
| Storage                         | `STORAGE_DRIVER=local\|s3`, `UPLOAD_DIR=/data/uploads`, `S3_*` (optional)                                                                                            |
| LLM                             | `LLM_PROVIDER=openai\|fake`, `OPENAI_API_KEY`, `OPENAI_BASE_URL` (optional), `LLM_PARSING_MODEL`, `LLM_ANALYSIS_MODEL`, `LLM_TIMEOUT_MS`, `LLM_MAX_RETRIES`          |
| Mail                            | `MAIL_DRIVER=console\|smtp`, `SMTP_HOST/PORT/USER/PASS/FROM`                                                                                                         |
| Rate limit                      | `THROTTLE_TTL`, `THROTTLE_LIMIT` (+ auth/upload/analysis buckets)                                                                                                    |
| Observability (all optional)    | `SENTRY_DSN`, `VITE_SENTRY_DSN`, `OTEL_EXPORTER_OTLP_ENDPOINT`, `OTEL_SERVICE_NAME`, `LANGSMITH_TRACING`, `LANGSMITH_API_KEY`, `LANGFUSE_PUBLIC_KEY/SECRET_KEY/HOST` |

## 8. Phase Plan

Each phase = one GitHub **milestone** + one **epic issue**; tasks below it are sub-issues. Phases are sequential; tasks inside a phase may interleave. Every phase ends with: all its tests green, lint clean, PR(s) merged, demo-able increment.

| Phase   | Name                             | Goal                                                                                                                                | Exit criteria                                                                                                                                                      |
| ------- | -------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **P0**  | Repository & Tooling Bootstrap   | Monorepo skeleton, quality gates, CI skeleton, GitHub hygiene                                                                       | `yarn install --frozen-lockfile` + `yarn lint`/`yarn test` green at root; hooks block bad commits; CI green; labels/milestones/templates exist                     |
| **P1**  | Backend Foundation               | Runnable NestJS core: config, Mongo, logging, errors, health, security middleware, Swagger, test harness, seeds                     | `GET /api/v1/health/ready` green against local Mongo; invalid env fails boot; Swagger up with examples + convention test active; seed creates admin                |
| **P2**  | AuthN/AuthZ & Users              | Email+password auth, JWT+refresh rotation, RBAC, flagged Google/LinkedIn OAuth, verification + password reset, me-endpoints         | Full auth lifecycle covered by e2e tests incl. abuse paths; providers endpoint reflects env flags                                                                  |
| **P3**  | Resume Domain                    | Resume CRUD + dashboard stats, file upload, storage abstraction, text extraction                                                    | Create/list/edit/soft-delete resumes; upload stores file + extracts text for all 3 formats; placeholder pruning proven by tests                                    |
| **P4**  | AI Platform & Analysis Pipeline  | Model registry (encrypted keys), LlmService, job runner, upload→json-resume parsing, 3-step analysis pipeline, suggestion apply     | With `LLM_PROVIDER=fake`: upload parses end-to-end; analysis completes 3 steps with persisted results; retries/recovery proven; real OpenAI path verified manually |
| **P5**  | Notifications & Realtime         | Bell notifications + SSE streams (progress + notifications)                                                                         | One active notification per analysis enforced; SSE delivers step transitions < 1s; heartbeats keep proxy alive; polling fallback works                             |
| **P6**  | Admin Domain                     | Admin stats, user management, privacy-bounded resume admin, AI model settings                                                       | RBAC denial matrix green; admin cannot read resume content (test-proven); all admin actions audited                                                                |
| **P7**  | Frontend Foundation              | Vite scaffold, Tailwind design system from mockup, light/dark, routing+guards, API client w/ refresh, forms infra, test harness     | App shell renders with theming + auth-guarded routing against real API; MSW test suite green                                                                       |
| **P8**  | Frontend Candidate Experience    | Landing, auth screens, dashboard, upload flow, resume editor + in-place editing, analysis start/progress/results, apply-suggestions | Every PROMPT.md candidate feature usable end-to-end against the real backend (fake LLM ok)                                                                         |
| **P9**  | Frontend Admin + Export          | Admin UI (dashboard, users, settings) + PDF/DOCX export (server) wired to download dropdown                                         | Admin journeys complete; exported PDF/DOCX open correctly and match resume content                                                                                 |
| **P10** | Integration, Quality & Hardening | SPA serving, accessibility + responsive + web-vitals passes, Sentry, OTel, Playwright suite, security hardening, docs               | Single server serves SPA+API; axe/Lighthouse budgets met; Playwright green in CI; security review done; runbook complete                                           |
| **P11** | Docker, CI/CD & Railway          | Multi-stage Dockerfile, compose (db/full profiles), full CI pipeline, Railway deploy + volume + Mongo service, launch checklist     | `docker compose --profile full up` works clean; CI fully gates PRs; production URL live on Railway, smoke test + observability verified                            |

**Sequencing notes**

- P3 ships upload/extraction but parsing waits for P4 (AI). The upload review screen (P8) needs P4.
- P7/P8/P9 (frontend) consume APIs from P2–P6; backend phases are deliberately front-loaded.
- Docker basics (compose `db` profile for local Mongo) are pulled forward into P0 so local dev works from day one; the full app image is P11.

## 9. GitHub Project Structure

**Creation mechanics (after plan approval, before any code):** via GitHub REST API with your fine-grained PAT (scopes: Issues r/w, Contents r/w on `adityaparab/CVantage`). Order: labels → milestones (M0–M11) → 12 epic issues → task issues → link tasks to epics with the **sub-issues API** (`POST /repos/{o}/{r}/issues/{epic}/sub_issues`). Fine-grained subtasks live as checklists inside each task issue (kept small enough to implement in one sitting).

**Labels:** `type:epic` `type:task` · `area:server` `area:client` `area:shared` `area:infra` `area:docs` · `phase:0`…`phase:11` · `priority:P0` (blocking) `P1` (required) `P2` (polish).

**Every issue body contains:** Context (why) · Scope (what's in/out) · Subtasks checklist · Acceptance criteria (testable) · Dependencies (issue refs) · Technical notes.

**Global Definition of Done (applies to every issue, stated once in each epic):** code + tests written and green · lint/typecheck clean · no secrets committed · docs/`.env.example` updated if config changed · conventional commit(s) referencing the issue · PR per task, squash-merged, closes issue via `Closes #N` · **every new/changed endpoint ships exhaustive Swagger annotations** (summary, description, params, request/response schemas with examples, all applicable error codes — per 1.9 contract).

## 10. Issue Catalog

> 85 task issues under 12 epics (97 issues total incl. epics). AC = acceptance criteria (abridged here; full testable wording goes into the GitHub issue bodies).

### E0 · Phase 0 — Repository & Tooling Bootstrap `M0`

**0.1 Initialize monorepo & push** `area:infra P0`
Git init on `main`, remote `adityaparab/CVantage`, latest Yarn 1.x classic (no corepack; `engines.yarn: "^1.22.0"` + `.npmrc engine-strict=true`; install path documented: bundled on CI runners/node images, `npm i -g yarn` locally) with workspaces (`server`, `frontend`, `shared` placeholders), `.gitignore` (incl. `.secrets/`), `.editorconfig`, `.nvmrc`, README stub.
AC: repo pushed; `yarn install` succeeds at root; workspace graph resolves; existing docs (`PROMPT.md`, `CLAUDE.md`, mockup, schemas, `PLAN.md`) committed.

**0.2 Shared lint/format toolchain** `area:infra P0`
ESLint (flat config, typescript-eslint, react plugin for frontend) + Prettier shared at root, per-workspace overrides.
AC: `yarn lint` / `yarn lint:fix` / `yarn format` work at root and per workspace; zero warnings policy (`--max-warnings 0`).

**0.3 Husky pre-commit hook** `area:infra P0`
husky + lint-staged: staged-file lint+fix, typecheck, and related unit tests for both apps (per `CLAUDE.md`).
AC: commit with lint error or failing related test is blocked; clean commit passes in < 60s; hooks auto-install via the root `prepare` script on `yarn install`.

**0.4 Commit message validation** `area:infra P0`
commitlint (conventional commits) on `commit-msg` hook; scopes: `server|frontend|shared|infra|docs|deps`.
AC: `feat(server): …` accepted; `bad message` rejected with helpful error; convention documented in CONTRIBUTING.md.

**0.5 GitHub hygiene: labels, milestones, templates** `area:infra P1`
Create label set + M0–M11 milestones; issue template (the structure in §9) + PR template (checklist incl. tests/docs); CODEOWNERS = @adityaparab.
AC: all labels/milestones exist; new issues/PRs render templates.

**0.6 CI skeleton (GitHub Actions)** `area:infra P0`
`ci.yml`: actions/setup-node (Node 22, `cache: yarn`; runners ship Yarn 1 preinstalled — no corepack) → `yarn install --frozen-lockfile` → lint → typecheck → test → build, matrixed over workspaces; runs on PR + main.
AC: CI green on the empty scaffolds; cache hit on second run; failures block PR merge.

**0.7 Local Mongo via compose (`db` profile)** `area:infra P0`
`docker-compose.yml` with `mongo:7` + named volume + healthcheck under profile `db` (full app profile arrives in P11).
AC: `docker compose --profile db up -d` yields a healthy Mongo on `localhost:27017`; documented in README.

### E1 · Phase 1 — Backend Foundation `M1`

**1.1 NestJS scaffold (`server/`)** `area:server P0`
Nest 11, strict TS, path aliases, global prefix `/api/v1`, URI versioning, `@nestjs/platform-express`.
AC: `yarn dev` boots; `GET /api/v1` 404s with JSON envelope; build emits `dist/`.

**1.2 Typed config module (zod, fail-fast)** `area:server P0`
All env per §7.3 validated at boot; typed `AppConfig` injectable; `.env.example` exhaustive; no `process.env` access outside config.
AC: missing/invalid var → boot fails listing offending keys; unit tests for schema; `.env.example` parity test (every consumed key documented).

**1.3 Mongo integration & schema port** `area:server P0`
DatabaseModule (Mongoose 8, `MongooseModule.forRootAsync`), port `database/nestjs-mongoose/schemas.ts` into `server/src/database/schemas/` (split per collection, keep hooks/indexes/transforms verbatim), `MODEL_DEFINITIONS` registration, connection event logging, `autoIndex` dev-only.
AC: boots against compose Mongo; all 7 models registered; resume prune hook covered by unit test; `toJSON` never leaks `passwordHash`/`apiKeyEncrypted`.

**1.4 Structured logging (pino)** `area:server P0`
nestjs-pino, request-id (ALS) on every log line, redaction (authorization, cookies, passwords, keys, tokens), pretty in dev / JSON in prod, `LOG_LEVEL` env.
AC: each request logs method/path/status/duration/requestId; redaction proven by test; uncaught errors logged once with stack.

**1.5 Error handling & validation contract** `area:server P0`
Global exception filter → problem-details envelope `{statusCode, error, message, details?, requestId, timestamp, path}`; nestjs-zod validation pipe; Mongo duplicate-key → 409; unknown `/api/**` → JSON 404; prod hides internals.
AC: contract snapshot-tested for 400/401/403/404/409/422/429/500; zod `details` lists field paths; no stack traces in prod responses.

**1.6 Health module** `area:server P0`
Terminus: `/api/v1/health/live` (process) and `/health/ready` (Mongo ping, disk, memory thresholds). Unauthenticated, rate-limit-exempt, no internals leaked.
AC: ready flips 503 when Mongo down (e2e with stopped container); response shape stable for Railway/Docker healthchecks.

**1.7 Security middleware baseline** `area:server P0`
helmet, CORS allowlist from env, `@nestjs/throttler` global + named strict buckets (auth/upload/analysis), body size limits, cookie-parser (signed), compression, `trust proxy` for Railway.
AC: security headers asserted in e2e; cross-origin from non-allowlisted origin blocked; 61st auth attempt in window → 429 with envelope.

**1.8 Graceful shutdown & lifecycle** `area:server P0`
`enableShutdownHooks`; SIGTERM → stop accepting, drain job runner (P4 hooks in later), close Mongo; bounded by `SHUTDOWN_TIMEOUT_MS`.
AC: SIGTERM during in-flight request completes it then exits 0; verified in integration test.

**1.9 Swagger/OpenAPI — exhaustive & example-rich** `area:server P0`
`@nestjs/swagger` + zod→OpenAPI bridge at `/api/docs` (UI), with the raw spec **exposed as JSON at `/api/docs-json`** (and YAML at `/api/docs-yaml`) for client generation/tooling; all gated by `SWAGGER_ENABLED` (default on in dev, off in prod), bearer+cookie auth schemes, tag-per-module **with descriptions**. Documentation contract for **every endpoint** (enforced from this phase onward): summary + meaningful description; every path/query/body parameter with types, constraints and enum values; typed response schema **per status code** — success plus every error the endpoint can emit, all using the 1.5 error envelope; at least one realistic request example and one response example per documented status; auth requirement markers; pagination params defined once and `$ref`-erenced. DTO schemas + examples derive from the shared zod schemas (single source of truth) plus named fixtures (e.g., a complete sample json-resume, a full analysis result).
AC: spec validates as OpenAPI 3.1; convention test fails CI if any route lacks operation summary/description, a success-response example, or documented error responses (400/401/403/404/409/422/429 as applicable); `/api/docs` renders runnable examples for auth, resume CRUD, upload, analysis lifecycle, admin and export endpoints as they land; `GET /api/docs-json` returns the complete valid spec with `application/json` content type (e2e-tested, matches the UI spec exactly); `openapi.json` exported as a CI artifact per build (generated via the same endpoint); all docs routes disabled in prod unless flag set.

**1.10 Server test harness** `area:server P0`
Jest + ts-jest config, mongodb-memory-server helper, `supertest` app factory, fixture/factory utilities (user, resume, analysis), coverage thresholds (≥80% lines on `src/**` excluding bootstrap).
AC: example unit + e2e pass; `yarn test`/`test:e2e`/`test:cov` wired into CI and pre-commit (related only).

**1.11 Seed & ops scripts** `area:server P0`
`seed:admin` (from `ADMIN_EMAIL/ADMIN_PASSWORD`, idempotent, argon2id), `db:indexes` (syncIndexes for prod), both runnable via yarn scripts and inside the container.
AC: running twice creates exactly one admin; indexes match schema definitions (verified by listing); documented in runbook.

### E2 · Phase 2 — AuthN/AuthZ & Users `M2`

**2.1 Registration & login (local)** `area:server P0`
`POST /auth/register` (email, fullName, password w/ strength policy) → argon2id hash, audit `user.register`; `POST /auth/login` → audit `user.login`; identical error/timing for unknown email vs wrong password; deactivated accounts blocked.
AC: e2e: register→login→`/users/me`; duplicate email → 409 (case-insensitive per index); weak password → 422 with policy details; timing-safe comparison.

**2.2 JWT access + rotating refresh tokens** `area:server P0`
Access JWT (15m, alg pinned HS256, issuer/audience set) + opaque refresh token (30d) in httpOnly Secure SameSite=Lax cookies; refresh stored as SHA-256 in `authtokens` w/ ip/UA; `POST /auth/refresh` rotates (old consumed); **reuse detection revokes the whole user session family**; `POST /auth/logout` revokes + clears cookies.
AC: e2e: refresh rotates (old one 401s); reuse of consumed token → all sessions revoked + audit; expired access + valid refresh recovers; TTL index expires rows.

**2.3 RBAC & request context** `area:server P0`
`JwtAuthGuard` global (public routes opt-out via `@Public()`), `@Roles(ADMIN)` + guard, `@CurrentUser()`, `ActiveUserGuard` (status check per request), `lastActiveAt` throttled update.
AC: denial matrix tests: anonymous→401, candidate→admin route 403, deactivated→403 even with valid JWT; `lastActiveAt` updates at most once/5min.

**2.4 OAuth: Google + LinkedIn (feature-flagged)** `area:server P1`
Passport OIDC strategies; per-provider enable iff its env keys present; `GET /auth/providers` → `{google: bool, linkedin: bool}`; callback links identity to existing user by verified email or creates account (`emailVerified=true`); unique identity index honored; state+nonce CSRF protection.
AC: with flags off, routes 404 and providers report false; mocked-provider e2e covers new-user, existing-email-link, duplicate-identity conflict; secrets never logged.

**2.5 Email verification & password reset** `area:server P1`
MailModule (`console`/`smtp` drivers); single-use hashed tokens (TTL: verify 24h, reset 1h) in `authtokens`; `POST /auth/verify-email`, `POST /auth/forgot-password` (uniform 202 response — no user enumeration), `POST /auth/reset-password` (revokes all refresh tokens).
AC: full reset e2e via captured console mail; token reuse/expiry → 400; enumeration impossible (same response/timing); reset invalidates sessions.

**2.6 Users module (self-service)** `area:server P0`
`GET /users/me` (sanitized), `PATCH /users/me` (fullName, avatarUrl), `POST /users/me/password` (current password required, revokes other sessions), dashboard counters surfaced (`resumeCount`, `analysisCount`).
AC: contract tests; password change with wrong current → 403; response never contains hash/identities' raw data.

**2.7 Auth abuse protection** `area:server P1`
Strict throttle bucket on register/login/forgot (per-IP + per-email), progressive lockout with backoff after N failures (env-tunable), audit on lockout.
AC: lockout engages and decays per config; 429 envelope correct; legit user can log in after window; covered by e2e.

**2.8 Auth/user test suite & security review** `area:server P0`
Consolidated unit+e2e for 2.1–2.7 (happy, abuse, expiry, rotation paths) + run `security-review` skill on the auth diff.
AC: coverage ≥85% on auth module; security review findings triaged to issues or fixed.

### E3 · Phase 3 — Resume Domain `M3`

**3.1 Shared json-resume zod schemas (`shared/`)** `area:shared P0`
Zod mirror of json-resume-schema (basics/work/volunteer/education/awards/certificates/publications/skills/languages/interests/references/projects/meta), partial-date regex, URL/email refinements, `pruneEmpty` util (mirror of the Mongoose pre-validate hook), API DTO types + enums re-exported for client and server.
AC: zod accepts the official schema's canonical sample resume; property-based tests: `pruneEmpty` never leaves empty strings/arrays/objects; package consumed by both workspaces.

**3.2 Resume CRUD** `area:server P0`
`POST /resumes` (form-created, `source=created`), `GET /resumes` (paginated/sorted table data: name, uploadDate, lastAnalyzedAt, analysisStatus, counts), `GET /resumes/:id`, `PATCH /resumes/:id` (rename + jsonResume updates w/ optimistic concurrency → 409 on version conflict), `DELETE` (soft, audit `resume.delete`), per-user unique live name → 409.
AC: ownership enforced (foreign id → 404 not 403 — no existence leak); placeholder pruning verified end-to-end (placeholder in → absent in DB); version conflict e2e; soft-deleted excluded everywhere incl. name-uniqueness.

**3.3 Dashboard stats & counter integrity** `area:server P1`
`GET /users/me/stats` (resumes created, analyses run); counters via `$inc` on create/delete; nightly reconcile job recomputes from source collections (D15).
AC: stats correct after create/delete churn; reconcile fixes an artificially skewed counter in test.

**3.4 Storage abstraction** `area:server P0`
`StorageService` interface (`put/get/delete/stat`, streaming); `LocalDiskStorage` (UPLOAD_DIR, path-traversal-safe keys, fsync) default; `S3Storage` (any S3-compatible endpoint) env-selected; sha256 computed on store.
AC: driver chosen by env; traversal attempts rejected (unit-tested); local survives restart; S3 driver integration-tested against MinIO in CI (optional job).

**3.5 Upload endpoint** `area:server P0`
`POST /resumes/upload` (multipart): ≤10 MB, extension+MIME+magic-byte agreement (pdf/doc/docx via `file-type`), store original via StorageService, create Resume(`source=uploaded`, `uploadParse=pending`, name from filename w/ dedupe suffix), strict throttle bucket.
AC: oversized → 413; spoofed extension (exe renamed .pdf) → 422; happy path returns resume id + parse status URL; original retrievable by sha256-verified key.

**3.6 Text extraction service** `area:server P0`
`ExtractionService`: PDF → LangChain `PDFLoader`; `.docx` → mammoth; `.doc` → word-extractor fallback (D10); whitespace/encoding normalization; 200k char cap; clear typed errors (encrypted PDF, corrupt file, empty text).
AC: fixture suite (3 formats + corrupt + encrypted + image-only PDF) yields text or the correct typed error; output stored as `originalText`.

**3.7 Resume module test suite** `area:server P0`
Unit + e2e consolidation for 3.1–3.6 incl. concurrency, pruning, upload abuse cases.
AC: coverage ≥80% module-wide; CI green.

### E4 · Phase 4 — AI Platform & Analysis Pipeline `M4`

**4.1 Key encryption service + AI model registry** `area:server P0`
`CryptoService` (AES-256-GCM, key = `MASTER_ENCRYPTION_KEY`, random IV, auth tag stored); `AiModelsService` over `aimodels` (create w/ encrypted key + `apiKeyLast4`, list masked, disable, rotate); resolution order per usage (`resume_parsing`/`analysis`/`fallback`): active DB model → env fallback.
AC: round-trip encrypt/decrypt; tamper → decrypt failure; raw key never in logs/JSON (transform test); resolution order proven with and without DB models.

**4.2 LlmService (LangChain)** `area:server P0`
`ChatOpenAI` built per resolved model (`baseURL` support), `withStructuredOutput(zodSchema)`, timeout + bounded retry w/ exponential backoff + jitter, token usage captured per call, typed errors (timeout/quota/invalid-output); `FakeLlmProvider` (`LLM_PROVIDER=fake`) returns deterministic fixtures for parsing + all 3 analysis steps.
AC: structured output validated against zod (invalid LLM JSON → one repair retry → typed failure); retry/backoff unit-tested with fake timers; fake provider fully deterministic.

**4.3 Mongo-backed job runner** `area:server P0`
`JobRunner` interface + Mongo implementation: atomic claim (`findOneAndUpdate` pending→in_progress w/ owner + heartbeat), heartbeat interval, stale-job recovery on boot and periodically (heartbeat older than T → re-queue w/ `retryCount++`, ≤5 then failed), graceful drain on SIGTERM (ties into 1.8), concurrency limit env-tunable.
AC: two runner instances never double-claim (race test); killed worker's job recovered and completed; exhausted retries → failed with error persisted; drain waits for in-flight job.

**4.4 Resume parsing pipeline (upload → json-resume)** `area:server P0`
Parse job: `originalText` → prompt + structured output (shared zod json-resume) → prune → save `jsonResume`, `uploadParse` transitions pending→processing→completed/failed (+`modelUsed`, timestamps, error), progress events emitted (consumed by SSE in P5); `POST /resumes/:id/reparse` for failed parses.
AC: e2e with fake provider: upload → poll/SSE → completed resume matches fixture; LLM hallucinated fields outside schema are stripped; failure path sets status+error and is retryable; JD-irrelevant: prompt injection in resume text cannot alter system prompt (prompt hardening test with adversarial fixture).

**4.5 Analysis pipeline (3 steps)** `area:server P0`
`POST /analyses` (name, JD 30–50k chars, resumeId) → snapshot resume, create steps, enqueue; steps run sequentially with per-step status/timestamps/errors: ① compare (scores, strong/weak, matching skills, gaps) ② suggestions (grouped per `SuggestionGroup`, each with `fieldRef` + `proposedValue`) ③ interview Q&A; rollups maintained (`resume.analysisStatus`, `lastAnalyzedAt`, counters); failure mid-pipeline keeps prior step results, analysis → failed.
AC: e2e (fake provider): all steps transition correctly and persist results matching schema constraints (scores 0–100, exactly 3 steps); resume rollup transitions verified; step-2 failure leaves step-1 results intact + analysis failed + retry works.

**4.6 Analysis endpoints & suggestion application** `area:server P0`
`GET /analyses` (paginated, filter by resume), `GET /analyses/:id`, `POST /analyses/:id/retry` (failed only), `POST /analyses/:id/cancel` (pending only), `POST /analyses/:id/suggestions/:sid/apply` (applies `proposedValue` at `fieldRef` to the live resume w/ optimistic concurrency, marks applied+appliedAt), `…/dismiss`; ownership on everything.
AC: apply mutates exactly the targeted field (deep-path tests incl. array paths like `work[0].highlights`); apply on deleted resume → 410; dismiss/apply idempotency; cancel/retry state-machine rules enforced.

**4.7 LLM observability & cost guards** `area:server P1`
LangSmith via env passthrough; optional Langfuse callback handler (env-gated); per-step spans (ties into OTel 10.5) with model, latency, prompt/completion tokens; guards: JD + resume size caps, `max_tokens` per step, per-user concurrent-analysis limit (env), token usage persisted on analysis.
AC: with flags off → zero overhead/no network calls; usage numbers persisted and visible via API; concurrent limit returns 429 with clear message.

**4.8 AI platform test suite** `area:server P0`
Consolidated unit+e2e for 4.1–4.7; manual smoke checklist against real OpenAI documented (one resume, one analysis) before phase close.
AC: coverage ≥80%; real-provider smoke run recorded in the epic.

### E5 · Phase 5 — Notifications & Realtime `M5`

**5.1 Notifications module** `area:server P0`
On analysis start/complete/fail: upsert the **single active** notification per analysis (unique partial index honored — progress replaced by completion); `GET /notifications` (active, newest first), `POST /notifications/:id/clear`, auto-clear on `GET /analyses/:id` (visit-clears rule), 30-day TTL.
AC: lifecycle e2e: start→in-progress bell; complete→replaced by completion; visiting details clears; manual clear works; never two active for one analysis (race-tested).

**5.2 SSE streams** `area:server P0`
`GET /api/v1/analyses/:id/events` (step transitions + terminal event) and `GET /api/v1/notifications/events` (bell updates); cookie-authenticated, ownership-checked, 15s heartbeat comments, `Last-Event-ID` replay of current state on reconnect, connection caps per user, proxy-friendly headers (`X-Accel-Buffering: no`, no compression on stream).
AC: integration test consumes stream and sees pending→in_progress→completed within 1s of transition; reconnect mid-analysis receives current snapshot first; unauthenticated → 401; heartbeats observed.

**5.3 Realtime test suite** `area:server P1`
SSE + notification integration tests, polling-fallback contract documented (same data shapes via REST).
AC: CI green incl. SSE tests (no flake across 10 runs).

### E6 · Phase 6 — Admin Domain `M6`

**6.1 Admin stats endpoint** `area:server P0`
`GET /admin/stats`: registered users, total resumes (created+uploaded), total analyses; efficient (countDocuments / cached 60s).
AC: numbers correct vs seeded fixtures; candidate role → 403; response < 200ms with 10k-doc fixtures.

**6.2 Admin user management** `area:server P0`
`GET /admin/users` (search by id/email/name via text+prefix indexes; columns: fullName, email, registrationDate, lastActiveAt, resumeCount, analysisCount; paginated+sorted), `GET /admin/users/:id`, `PATCH` (fullName/email w/ uniqueness), `POST /admin/users/:id/reset-password` (admin sets temp password OR triggers reset mail — both audited), `POST …/deactivate` / `…/reactivate` (deactivation revokes all refresh tokens); admins cannot deactivate/demote themselves.
AC: search by each criterion; email collision → 409; deactivated user's live session 403s on next request (ActiveUserGuard); self-deactivation blocked; every action lands in `auditlogs` with actor/target/redacted meta.

**6.3 Privacy-bounded resume administration** `area:server P0`
`GET /admin/users/:id/resumes` returns **metadata only** (name, createdAt, analysisCount, status — explicit DTO whitelist, no `jsonResume`, no `originalText`, no analysis content anywhere in admin API); `DELETE /admin/resumes/:id` soft-deletes resume + cascades soft-delete to its analyses + clears their notifications (ordered idempotent ops per D15), audit `admin.resume.delete`.
AC: DTO test proves content fields absent; admin requesting candidate resume detail endpoint → 403 by role-scoping; cascade verified incl. notification cleanup; cascade re-run is a no-op (idempotent).

**6.4 AI model settings endpoints** `area:server P0`
`GET /admin/models` (masked `…last4` only), `POST` (validate by live ping with the key before save), `PATCH` (status/usages), `POST /admin/models/:id/rotate-key`, `DELETE` (block deleting the only active model for a usage); audits for add/remove/rotate.
AC: invalid key rejected at create (fake provider hook for tests); masked output everywhere incl. Swagger examples; deleting last active model for a usage → 409; rotation re-encrypts and bumps `apiKeyLast4`.

**6.5 Admin test suite + RBAC matrix** `area:server P0`
Full denial matrix (anon/candidate/deactivated-admin × every admin route), audit assertions, e2e for 6.1–6.4; run `security-review` skill on the admin diff.
AC: matrix table fully green; coverage ≥85% on admin module.

### E7 · Phase 7 — Frontend Foundation `M7`

**7.1 Vite + React + TS scaffold (`frontend/`)** `area:client P0`
Vite 6, React 19, strict TS, path aliases mirroring server style, env handling (`VITE_*`), dev proxy `/api → localhost:3000`.
AC: `yarn dev` HMR works against running server; `yarn build` emits `dist/`; typecheck clean.

**7.2 Design system & theming** `area:client P0`
Tailwind v4 tokens extracted from `cvantage-mockup.html` (palette, radii, spacing, type scale — Pinecone-like); dark/light via `class` strategy + system preference + persisted toggle (no FOUC: inline script); base UI kit: Button, Input, Textarea, Select, Checkbox, DatePartInput (YYYY / YYYY-MM / YYYY-MM-DD), Modal, Drawer, Table (sortable), Badge (status colors), Tabs, Tooltip, Toast system, Skeleton, Spinner, EmptyState, ProgressSteps — all keyboard-accessible with visible focus.
AC: Storybook-less showcase route in dev; axe clean on the kit; theme toggle persists across reload; contrast AA in both themes.

**7.3 Routing & layouts** `area:client P0`
React Router: public (landing, auth), authed candidate shell (top nav w/ bell, user menu), admin shell (admin nav); route guards from auth state incl. role; 404 page; route-level code splitting + suspense fallbacks; document titles per route.
AC: deep-link to guarded route when logged out → login → returns to target; candidate hitting `/admin` → 403 page; lazy chunks verified in build output.

**7.4 API client & query layer** `area:client P0`
Axios instance (`withCredentials`), interceptor: on 401 → single-flight refresh → replay queued requests → logout on refresh failure; error normalization to the server envelope; TanStack Query v5 defaults (retry rules, staleTime), typed endpoint functions + query-key factory per domain; auth context (`me` query) with login/logout/register mutations.
AC: MSW tests: parallel 401s trigger exactly one refresh; refresh failure → logged out + redirected; error envelope surfaced in toasts.

**7.5 Forms infrastructure** `area:client P0`
react-hook-form + zod resolvers from `shared/`; field components bound to the UI kit (label, description, error, aria-invalid/aria-describedby); array-field helpers (add/remove/reorder) for json-resume sections; dirty-state navigation guard.
AC: schema errors render accessibly; array add/remove/reorder round-trips values; leaving dirty form prompts confirmation.

**7.6 Frontend test harness** `area:client P0`
Vitest + RTL + MSW (handlers per domain, fixtures shared with Playwright later), coverage thresholds (≥80% on `lib/api/components-ui`), CI wiring.
AC: example component + hook + API tests green in CI under 2 min.

### E8 · Phase 8 — Frontend Candidate Experience `M8`

**8.1 Landing page** `area:client P1`
Hero (CVantage name + tagline + description), feature sections, how-it-works, CTA → register/login; responsive; light/dark; meets mockup look.
AC: Lighthouse perf/a11y/SEO ≥90 on the page; renders correctly 360px→4k, both orientations.

**8.2 Auth screens** `area:client P0`
Login, register (password strength meter per server policy), forgot/reset password, email-verification states; OAuth buttons rendered from `GET /auth/providers` (hidden when disabled — D4); inline server-error mapping (409 email exists, 429 lockout w/ retry-after).
AC: full flows green against real API in dev + MSW tests; OAuth buttons appear only when flags on; deactivated-account login shows proper message.

**8.3 Candidate dashboard** `area:client P0`
Stats cards (resumes created, analyses run); resume table (name, upload date, last analysis date, status badge unanalyzed/in-progress/completed/failed, actions: analyze/edit/delete w/ confirm modal); Create Resume + Upload Resume entry points; empty state for new users; live status updates (query invalidation on SSE/notification events).
AC: matches mockup table spec; delete confirms then removes row optimistically (rollback on error); status badge flips without manual refresh during a running analysis.

**8.4 Upload flow** `area:client P0`
Dropzone (drag/drop + file picker; accept pdf/doc/docx; client-side size/type pre-check with friendly errors), upload progress bar, then **parse progress state** ("AI is processing your resume…", SSE-driven w/ polling fallback), failure state w/ retry (reparse), success → auto-navigate to upload-review screen.
AC: wrong type/oversize blocked client-side with message; kill-server-mid-parse shows failure + retry works; slow-parse UX (>30s) keeps user informed; e2e-tested with fake LLM.

**8.5 Resume editor (create flow)** `area:client P0`
Full json-resume form — every section and **every field** editable incl. partial dates (basics+location+profiles, work, volunteer, education, awards, certificates, publications, skills, languages, interests, references, projects, meta); placeholders shown for missing fields but **never submitted** (pruneEmpty before submit — D mirror of server); section navigation; zod validation per field; save → `POST /resumes` → resume view.
AC: submitting placeholders-only section stores nothing (verified against API); all 12 sections round-trip correctly; date inputs accept the 3 partial formats and reject invalid; a11y: full keyboard form completion possible.

**8.6 Resume view & in-place editing** `area:client P0`
Formatted resume render (mockup `scr-resume-view`); hover (or focus) on any field shows pencil icon; click → that field alone becomes editable (correct control type incl. arrays/dates) with save/cancel; optimistic update + 409 version-conflict toast w/ reload action; "Analyze Resume" button (enabled once saved).
AC: every rendered field is individually editable and persists; concurrent-edit conflict path tested; pencil affordance keyboard-accessible (focusable, Enter activates).

**8.7 Upload review screen (split view)** `area:client P0`
Left: populated editable json-resume form (8.5 component); right: scrollable `originalText` panel; mockup `scr-upload-review`; correction workflow → save → "Start Analysis" CTA appears.
AC: panels scroll independently; responsive collapse to tabs on small screens; save then analyze navigates with resume preselected.

**8.8 Analysis start screen** `area:client P0`
Context header (selected resume = the one user navigated from); analysis name input + JD textarea (char counter vs 30–50k bounds); Clear button (wipes both fields); Start Analysis button (disabled until valid) → create analysis → progress screen.
AC: clear resets only the two fields; validation messages per bounds; resume context survives refresh (route param).

**8.9 Analysis progress screen + bell notification** `area:client P0`
3 steps (Comparing / Generating Suggestions / Preparing Interview Questions) with pending/in-progress/completed/failed color coding (mockup colors), SSE-driven w/ polling fallback; top-nav bell shows in-progress notification persisting across navigation; completion → visual cue (toast + bell state) ; clicking notification → this screen (or results if done); notification cleared on visiting details or manual clear; failed step → error panel + retry button.
AC: full lifecycle e2e (fake LLM): steps animate through states; navigate away and back — notification persists and routes correctly; completion clears per the two rules; failure path renders retry that works.

**8.10 Analysis results screen** `area:client P0`
Organized results: score gauges (overall, ATS, project score where present), strong/weak points, matching skills vs skill gaps (chips), improvement suggestions **grouped by field/category** with proposedValue previews, interview Q&A accordion; "Apply suggestions to the resume" button → apply screen.
AC: renders complete fake-provider fixture faithfully; empty arrays render graceful empties; deep-link to results works (notification click-through); print-friendly.

**8.11 Apply-suggestions screen** `area:client P0`
Current resume on left; suggestions on right (grouped, with target field highlight on hover); per-suggestion Apply (calls 4.6 endpoint, left pane updates + suggestion marked applied) and Dismiss; Save confirmation; **Download dropdown (PDF / DOCX)** wired to export endpoints (P9 server work — dropdown ships disabled-with-tooltip until 9.4 lands).
AC: applying a suggestion visibly mutates exactly the targeted field; applied/dismissed states persist on reload; dropdown downloads both formats once 9.4 merged.

**8.12 Candidate experience test suite** `area:client P0`
RTL+MSW coverage of 8.2–8.11 critical logic (editor pruning, in-place editing, SSE hook, apply flow).
AC: coverage ≥80% on feature folders; CI green.

### E9 · Phase 9 — Frontend Admin + Resume Export `M9`

**9.1 Admin navigation & dashboard** `area:client P0`
Admin top nav (Dashboard, Users, Settings) per PROMPT; dashboard cards: registered users, total resumes (created+uploaded), analyses run.
AC: admin login lands here; candidate cannot reach it (guard test); numbers match `GET /admin/stats`.

**9.2 Admin users list & user details** `area:client P0`
Users table (Full Name, email, registration date, last active, resume count, analysis count; search by id/email/name; pagination/sort; actions: Details, Deactivate w/ confirm); details page: edit name/email, reset password action, resume **metadata** list (name, analysis count) with delete (cascade warning modal), deactivate/reactivate.
AC: search debounced and server-driven; all actions reflect API state incl. error toasts; no resume content rendered anywhere (only metadata fields exist in the DTO); self-deactivation option hidden.

**9.3 Admin settings — AI models** `area:client P0`
Models table (model name, provider, masked key `••••last4`, status, usages); add-model form (provider, model name, API key, usages) with validation feedback from live-ping; disable / rotate-key / delete actions with confirms.
AC: key never displayed beyond last4 (also not in network tab beyond create request); add-invalid-key error surfaced inline; rotate flow updates mask.

**9.4 Resume export service (server)** `area:server P0`
`ExportModule`: `GET /resumes/:id/export?format=docx|pdf` — DOCX via `docx` package mapping every json-resume section; PDF via Puppeteer rendering a dedicated print HTML template (same data, print-grade styles); streamed download w/ correct headers/filename; concurrency-limited + cached by resume version for 10 min; ownership enforced.
AC: both formats open in Word/PDF readers with all sections of a full fixture resume present and ordered; special chars/long resumes render; export of foreign resume → 404; load test: 5 concurrent exports OK.

**9.5 Export integration + admin client tests** `area:client P1`
Wire 8.11 download dropdown + resume view export; RTL+MSW tests for 9.1–9.3.
AC: downloads work from both screens; admin suite coverage ≥80%.

### E10 · Phase 10 — Integration, Quality & Hardening `M10`

**10.1 SPA serving from Nest** `area:server P0`
Serve `frontend/dist`: hashed assets immutable-cached, `index.html` no-cache, SPA fallback for non-`/api` paths (deep links work), unknown `/api/**` stays JSON 404, compression, correct 404 status for truly unknown asset files; single-port production mode (per `CLAUDE.md`).
AC: e2e: deep-link `/resumes/abc` serves the app; `/api/v1/nope` → JSON 404; `curl` shows cache headers; works in the Docker image.

**10.2 Accessibility & responsive audit** `area:client P0`
Keyboard-only pass over every journey; ARIA roles/labels; focus management on route change + modals; axe automated checks in CI on key pages; responsive QA matrix (360/768/1024/1440/1920, portrait+landscape).
AC: axe: zero serious/critical; documented manual checklist signed off; no horizontal scroll at any breakpoint.

**10.3 Performance & web vitals** `area:client P1`
Bundle analysis + budgets (initial JS < 250KB gz), route-level splitting verified, image optimization, font strategy, prefetch on intent; Lighthouse CI budget (perf ≥90 landing/dashboard).
AC: budgets enforced in CI; LCP < 2.5s / CLS < 0.1 on landing (lab).

**10.4 Sentry integration** `area:server P1` `area:client`
`@sentry/nestjs` (filter expected 4xx, attach requestId) + `@sentry/react` (ErrorBoundary, release tagging, sourcemap upload in CI); both env-gated, PII scrubbed.
AC: with DSN unset → no-op; test event visible in Sentry from both sides; sourcemapped stack in a thrown test error.

**10.5 OpenTelemetry** `area:server P1`
NodeSDK (env-gated): auto-instrument HTTP/Express/Mongoose, custom spans: job claim/execute, each analysis step, LLM call (model/tokens as attrs), SSE connections gauge; trace-id injected into pino logs; OTLP exporter config.
AC: with endpoint set, a full analysis renders as one connected trace (HTTP → job → 3 step spans → LLM child spans); overhead < 5% on health-check benchmark; disabled = zero deps loaded.

**10.6 Playwright E2E suite** `area:infra P0`
Against compose `full` profile with `LLM_PROVIDER=fake` + seeded admin: journeys — register/login/logout, create resume (form), upload+parse+review (fixture file), full analysis lifecycle incl. bell, apply suggestion, export download, admin user mgmt, admin settings; CI job on main + nightly; trace/video on failure.
AC: suite green 3 consecutive CI runs (no flake); runtime < 10 min; failures upload traces.

**10.7 Security hardening & review** `area:server P0` `area:infra`
CSP (script-src self + hashes), `yarn audit` gate (fail on high), gitleaks in CI, IDOR sweep (every resource route tested with foreign ids), upload abuse re-check, dependency pinning review, `security-review` skill run over the full repo; threat-model notes in docs.
AC: zero high/critical findings open; IDOR matrix green; CSP report-only verified then enforced.

**10.8 Documentation set** `area:docs P0`
README (badges, quickstart matrix: local / Docker / Railway), CONTRIBUTING (workflow, conventions), `docs/runbook.md` (deploy, rollback, env rotation, Mongo backup/restore via volume snapshot + mongodump, stuck-job recovery, key rotation), `docs/architecture.md` (this plan distilled + diagrams), `.env.example` final audit.
AC: a new dev can go zero→running locally following README alone (tested by clean clone in CI container); runbook procedures each have exact commands.

### E11 · Phase 11 — Docker, CI/CD & Railway `M11`

**11.1 Production Dockerfile** `area:infra P0`
Multi-stage: `node:22` build stage (Yarn 1 ships in node images — no corepack; `yarn install --frozen-lockfile`) builds shared/server/frontend, then `yarn install --production --frozen-lockfile` for pruned runtime deps → runtime `node:22-slim` with chromium (+fonts) for Puppeteer, only prod deps + `dist` + `frontend/dist`, non-root `node` user, `tini` init, `HEALTHCHECK` → `/api/v1/health/ready`, `PUPPETEER_EXECUTABLE_PATH` env, image labels; target < 900MB (chromium-dominated), build args for versions.
AC: `docker build` then `docker run` with env file → healthy; PDF export works **inside** the container; runs as non-root (verified); image scanned (trivy) with no critical vulns.

**11.2 Compose `full` profile & local modes documentation** `area:infra P0`
`full` profile: app (built image, env_file, depends_on mongo healthy, volume for uploads) + mongo (volume); finalize the two documented local modes: (a) non-Docker: compose `db` + `yarn dev` (server) + `yarn dev` (frontend, proxy), (b) full Docker: single command.
AC: both modes verified from clean checkout following README; data survives `compose down && up` (volumes); hot-reload intact in mode (a).

**11.3 Complete CI/CD pipeline** `area:infra P0`
`ci.yml` final: changed-path filters, lint+typecheck+unit (matrix), API e2e (memory server), build artifacts, docker build + trivy + smoke (run image, hit health + one API), audit + gitleaks; `e2e.yml`: Playwright vs compose on main/nightly; concurrency groups; required status checks documented for branch protection.
AC: PR runtime < 10 min with caches; red on any gate blocks merge; image smoke test prevents broken-image merges.

**11.4 Railway deployment** `area:infra P0`
Railway project: Mongo service (template, volume) + app service from GitHub repo (Dockerfile builder); `railway.json` (healthcheckPath `/api/v1/health/ready`, restartPolicy on-failure, region); volume mounted at `UPLOAD_DIR`; full env var matrix set (incl. `MONGODB_URI` via Railway private networking reference, `trust proxy` on); deploy from `main` auto; custom domain/HTTPS notes; `PORT` from Railway respected.
AC: production URL serves the SPA + API; healthcheck green in Railway; SSE works through Railway proxy (heartbeat-verified); uploads survive redeploy (volume); deploy rollback procedure tested once and documented.

**11.5 Launch checklist & post-deploy verification** `area:infra P0`
Execute runbook checklist: seed admin on prod, real OpenAI key smoke (1 upload-parse + 1 analysis), Sentry test events, OTel trace visible (if endpoint configured), Lighthouse on prod URL, backup snapshot taken + restore drill on a scratch service, rate limits sane behind proxy (real client IPs), final `security-review` sign-off.
AC: every checklist item checked with evidence linked in the epic; production tagged `v1.0.0` with release notes.

---

## 11. Development Workflow (after approval)

1. **Issue creation first** (per your instruction): labels → milestones → epics → tasks → sub-issue links, exactly as §10. You'll get a summary table with issue numbers.
2. **Then implementation, one issue at a time**, in phase order: pick the next open task → branch `feat/<issue#>-<slug>` (or `fix/`, `chore/`) → implement w/ tests → pre-commit hooks run → conventional commits (`feat(server): … (#N)`) → push → PR (template, `Closes #N`) → CI green → run `review` skill on the diff (and `security-review` on auth/admin/hardening phases) → squash-merge → next issue.
3. **Phase close:** epic checklist verified, exit criteria from §8 demonstrated, milestone closed, short progress note to you.
4. **Your touchpoints:** approve plan (now) → provide PAT (issue creation) → provide `OPENAI_API_KEY` (P4 smoke) → optional OAuth/Sentry/OTel/SMTP keys (any time; features are flagged) → Railway account access or you run the documented Railway steps yourself (P11) → approve `v1.0.0`.

## 12. Local Development & Deployment Summary

| Mode           | How                                                                         | Notes                                                                                          |
| -------------- | --------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------- |
| Local (normal) | `docker compose --profile db up -d` → `yarn dev` in `server/` + `frontend/` | Vite proxies `/api`; hot reload both sides; `MAIL_DRIVER=console`, `LLM_PROVIDER=openai\|fake` |
| Local (Docker) | `docker compose --profile full up --build`                                  | Prod-like: single container serving SPA+API on `:3000` + Mongo w/ volumes                      |
| Railway (prod) | Push to `main` → auto-deploy Dockerfile                                     | Railway Mongo service (private networking), volume at `UPLOAD_DIR`, env per §7.3, he           |
