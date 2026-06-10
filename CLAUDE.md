# CLAUDE.md — Build Constraints & Working Agreement

> This file defines the **non-negotiable build constraints** (stack, architecture rules) and the
> **working agreement** (how to use Git/GitHub and how to progress through issues) for CVantage.
> It is the authority for *how* the project is built. `PROMPT.md` defines *what* to build
> (functional requirements); `PLAN.md` is the end-to-end implementation plan and issue catalog;
> `cvantage-mockup.html` is the visual reference; `database/fastapi-beanie/models.py` is the
> canonical data model.
>
> If any instruction here conflicts with another document, **CLAUDE.md wins** for build/architecture
> and workflow concerns.

---

## 1. Stack (mandatory)

**Backend**

- **Python 3.11** (pinned via `.python-version`).
- **FastAPI** as the web framework; **uvicorn** (dev) / **gunicorn + uvicorn workers** (prod) as the server.
- **MongoDB** with **Beanie ODM** (Pydantic-v2-native, async) — the canonical schema lives in
  `database/fastapi-beanie/models.py` and is ported as-is into the server.
- **Pydantic v2** everywhere for validation/DTOs — it is the single source of truth; the frontend
  consumes **generated TypeScript types from the OpenAPI spec** (no hand-maintained shared package).
- **LangChain + langchain-openai** (Python) for all LLM work.
- **uv** is the package/dependency manager (`server/pyproject.toml` + `uv.lock`). No raw `pip install`
  into the environment; always `uv add` / `uv sync`.

**Frontend**

- **React + TypeScript + Vite + Tailwind CSS + TanStack Query**.
- **pnpm** is the package manager (Node 22 LTS, corepack-pinned).
- Light **and** dark themes; fully responsive (phones, tablets in both orientations, mid/large/xl screens).

**Single-server production**: the FastAPI server serves `frontend/dist` as an SPA on a single port.

**Tooling**

- Backend lint/format: **ruff**; types: **mypy (strict)**; tests: **pytest** (+ pytest-asyncio, httpx).
- Frontend lint: **ESLint** (flat config) + **Prettier**; tests: **Vitest + RTL + MSW**.
- E2E: **Playwright**.
- **pre-commit** hooks + **conventional-commit** message validation (commitizen).

Do **not** introduce alternative frameworks/managers (e.g., Flask, Django, Poetry, npm/yarn, Mongoose,
NestJS) without an explicit decision recorded in `PLAN.md`.

---

## 2. Architecture rules (mandatory)

1. **API surface**: REST under the `/api/v1` prefix. Problem-details-style JSON error envelope on every
   error. Cursor/offset pagination on every list endpoint.
2. **Config**: all environment variables validated at boot via a `pydantic-settings` `Settings` model
   (fail-fast). No `os.environ` access outside the config module. Keep `.env.example` exhaustive and in
   sync with every consumed key.
3. **Secrets**: only via env. `password_hash`, `api_key_encrypted`, `token_hash` use `exclude=True` and
   are never serialized or logged. Provider API keys are encrypted at rest (AES-256-GCM).
4. **Security by default**: argon2id password hashing, JWT access + rotating refresh tokens (httpOnly
   cookies, reuse detection), RBAC + resource-ownership checks (no IDOR), security headers, strict CORS
   allowlist, rate limiting, input validation + file magic-byte checks at every boundary.
5. **Data discipline**: placeholders are **never** persisted (recursive `prune_empty` mirrors the Beanie
   pre-validate event); soft delete honored everywhere (`deleted_at` excluded from all queries);
   optimistic concurrency (Beanie revision) on mutable aggregates; all schema indexes actually created.
6. **Privacy**: admins see resume **metadata only** — never resume or analysis *content*. Enforce in the
   service/DTO layer; audit logs store redacted metadata only.
7. **No multi-document Mongo transactions** (target Mongo is standalone): use atomic `$inc`,
   idempotent ordered cascades, and a periodic reconcile job.
8. **Abstractions behind interfaces (Protocols)**: storage (`local`/`s3`), mail (`console`/`smtp`),
   job runner (Mongo-backed, swappable for Redis later), LLM provider (real `openai` / deterministic
   `fake`). Driver chosen by env.
9. **Observability**: structured JSON logs (structlog) with request-id correlation and secret redaction;
   Sentry, OpenTelemetry, and LLM observability are all env-gated (zero overhead when unconfigured).
10. **OpenAPI documentation is part of "done"**: every new/changed endpoint ships a summary,
    description, typed `response_model` per status code (success + every error it can emit, using the
    error envelope), at least one request and one response example, and auth markers. A convention test
    fails CI if a route is under-documented.

---

## 3. Module / code conventions

- **One package per domain** under `server/app/` (e.g., `auth/`, `users/`, `resumes/`, `analyses/`,
  `ai/`, `jobs/`, `admin/`). Each typically contains `router.py`, `service.py`, `schemas.py`,
  `dependencies.py`, and `models.py` (or imports from `app/database/models/`).
- **Routers** declare tags, summaries, descriptions, response models, and error responses.
- **Services** hold business logic; routers stay thin. Database access goes through Beanie documents /
  repository-style helpers — never from routers directly.
- **Dependencies** (`Depends(...)`) provide the current user, RBAC checks, pagination params, and config.
- **Naming**: `snake_case` for Python identifiers, files, and JSON/Mongo fields; `PascalCase` for
  Pydantic/Beanie models; async functions for all I/O.
- **Type everything**: mypy strict must pass; no untyped public functions.
- **Tests live in `server/tests/`** mirroring the package layout; use the httpx `AsyncClient` app factory
  and a Mongo test fixture. Coverage thresholds per `PLAN.md` (≥80% module-wide; ≥85% for auth/admin).

---

## 4. Git & GitHub workflow (mandatory)

**Always use the GitHub CLI (`gh`) for anything that talks to GitHub.** Do not call the GitHub REST API
directly, and do not use other GitHub integrations. Examples:

- Issues: `gh issue create`, `gh issue list`, `gh issue view`, `gh issue edit`, `gh issue close`.
- Sub-issues / labels / milestones: manage via `gh` (`gh label`, `gh issue edit --milestone`, and
  `gh api` **only** when a `gh` subcommand does not exist — still through the `gh` tool, never raw curl).
- Pull requests: `gh pr create`, `gh pr view`, `gh pr merge --squash`, `gh pr checks`.
- Repo/CI inspection: `gh run list`, `gh run view`, `gh repo view`.

**Always use plain `git` for local version control** — staging, committing, branching, pushing:

- `git checkout -b <branch>`, `git add`, `git commit`, `git push -u origin <branch>`.
- **Conventional commits**, scoped: `feat|fix|chore|docs|refactor|test(server|frontend|infra|docs|deps): … (#<issue>)`.
- Never use `git push --force` on shared branches, `git reset --hard` on others' work, or `--no-verify`
  to bypass hooks.

---

## 5. Issue execution loop (mandatory)

Work **one issue at a time**, in phase order from `PLAN.md`, and **do not wait for confirmation between
issues**. For each issue:

1. **Pick** the next open task issue (lowest phase, then lowest number) with `gh issue list`.
2. **Branch**: `git checkout -b feat/<issue#>-<short-slug>` from an up-to-date `main`.
3. **Implement** the issue's scope with tests; keep changes within that issue's boundaries.
4. **Verify locally**: run the relevant checks — `uv run ruff check`, `uv run mypy`, `uv run pytest`
   (and `pnpm lint`/`pnpm typecheck`/`pnpm test` for frontend issues). Everything must be green.
5. **Commit** with a conventional message referencing the issue, e.g.
   `feat(server): add health endpoints (#12)`. Pre-commit hooks must pass (do not bypass them).
6. **Push** the branch and **open a PR** with `gh pr create`, body including `Closes #<issue>`.
7. **Get CI green** (`gh pr checks`), then **squash-merge** with `gh pr merge --squash --delete-branch`.
8. **Sync**: `git checkout main && git pull`.
9. **Move on immediately** to the next issue — repeat without pausing for confirmation.

**Stop and ask the user only when genuinely blocked**, e.g.: a required secret/credential is missing
(`OPENAI_API_KEY`, OAuth keys, Railway access), an external account action is needed, CI fails for a
reason outside the issue's scope, or the work would deviate from `PLAN.md`/`PROMPT.md` in a way that
needs a decision. Otherwise, keep progressing autonomously.

**Definition of Done** (every issue): code + tests written and green · ruff/mypy/eslint/tsc clean ·
no secrets committed · `.env.example`/docs updated if config changed · exhaustive OpenAPI docs for any
new/changed endpoint · conventional commit(s) referencing the issue · PR squash-merged closing the issue.

---

## 6. Quick command reference

```bash
# Backend (run from server/)
uv sync                                   # install/refresh deps from uv.lock
uv run uvicorn app.main:app --reload      # dev server (http://localhost:8000)
uv run ruff check . && uv run ruff format .
uv run mypy .
uv run pytest                             # add --cov for coverage

# Frontend (run from frontend/)
pnpm install
pnpm dev                                  # Vite dev server, proxies /api → :8000
pnpm lint && pnpm typecheck && pnpm test
pnpm build                                # emits dist/

# Local Mongo
docker compose --profile db up -d         # healthy mongo on localhost:27017

# GitHub (always via gh)
gh issue list --state open
gh pr create --fill --base main
gh pr checks
gh pr merge --squash --delete-branch
```
