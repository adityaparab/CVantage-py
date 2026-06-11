# Project Status

Last updated: 2026-06-11
Branch: main

## Recently Completed (Phase 3–6)

### Phase 3 — Resume Domain ✅
| # | Task | PR | Status |
|---|------|----|--------|
| 40 | json-resume Pydantic schemas | #131 | ✅ |
| 41 | Resume CRUD (POST/GET/PATCH/DELETE) | #132 | ✅ |
| 42 | Dashboard stats & counter integrity | #133 | ✅ |
| 43 | Storage abstraction (LocalDisk + S3) | #134 | ✅ |
| 44 | Upload endpoint (multi-layer validation) | #135 | ✅ |
| 45 | Text extraction service (PDF/DOCX/DOC) | #136 | ✅ |
| 46 | Resume module test suite | — | ✅ (173 tests) |

### Phase 4 — AI Platform & Analysis Pipeline ✅
| # | Task | PR | Status |
|---|------|----|--------|
| 47 | AES-256-GCM key encryption + AI model registry | #137 | ✅ |
| 48 | LlmService (LangChain, FakeLlmProvider) | #138 | ✅ |
| 50 | Mongo-backed job runner (heartbeat, recovery) | #139 | ✅ |
| 51 | Resume parsing pipeline (LLM → json-resume) | #140 | ✅ |
| 52 | 3-step analysis pipeline (compare/suggest/interview) | #141 | ✅ |
| 53 | Analysis CRUD, retry, cancel, suggestion apply/dismiss | #142 | ✅ |
| 54 | LLM observability (LangSmith/Langfuse) & cost guards | #148 | ✅ |
| 55 | AI platform test suite (real Beanie via mongomock) | #147 | ✅ |

### Phase 5 — Notifications & Realtime ✅
| # | Task | PR | Status |
|---|------|----|--------|
| 56 | Notifications module (bell, lifecycle, auto-clear) | #143 | ✅ |
| 57 | SSE event streams for analysis progress | #144 | ✅ |
| 58 | Realtime test suite (notifications + SSE) | #147 | ✅ |

### Phase 8 — Frontend Candidate Experience
| # | Task | PR | Status |
|---|------|----|--------|
| 71 | Landing page (hero, features, how-it-works) | #159 | ✅ |
| 72 | Auth screens (login/register/forgot/reset, OAuth) | #160 | ✅ |
| 73 | Candidate dashboard (stats, table, create/delete) | #161 | ✅ |
| 74 | Upload flow (dropzone, validation, progress) | #162 | ✅ |
| 77 | Resume editor (all 12 sections, prune, section nav) | #164 | ✅ |
| 78 | Resume view & in-place editing (PATCH, 409 reload) | #165 | ✅ |
| 80 | Analysis start screen (JD input, validation, create) | #166 | ✅ |
| 81 | Analysis progress + bell notification (poll, retry) | #167 | ✅ |
| 82 | Analysis results (scores, suggestions, interview QA) | #168 | ✅ |
| 83 | Apply-suggestions (apply/dismiss, resume preview) | #169 | ✅ |
| 86 | Candidate experience test suite (feature folders ≥80%) | #170 | ✅ |
| 79 | Upload review split-view (needs server parse-status) | — | ⏳ |
| 86 | Candidate experience test suite | — | ⏳ |

### Phase 7 — Frontend Foundation ✅
| # | Task | PR | Status |
|---|------|----|--------|
| 64 | Vite + React + TS scaffold (proxy, aliases, build) | #153 | ✅ |
| 65 | Design system & theming (Tailwind v4, UI kit, dark/light) | #154 | ✅ |
| 66 | Routing & layouts (guards, shells, lazy chunks, 404/403) | #155 | ✅ |
| 67 | API client & query layer (refresh queue, auth ctx, MSW) | #156 | ✅ |
| 68 | Forms infrastructure (RHF+zod fields, array, dirty guard) | #157 | ✅ |
| 69 | Frontend test harness (Vitest+RTL+MSW, coverage gates) | #158 | ✅ |

### Phase 6 — Admin Domain ✅
| # | Task | PR | Status |
|---|------|----|--------|
| 59 | Admin stats endpoint (RBAC-guarded) | #145 | ✅ |
| 60 | Admin user management (search/update/reset/deactivate) | #149 | ✅ |
| 61 | Privacy-bounded resume administration (cascade delete) | #150 | ✅ |
| 62 | AI model settings endpoints (validate/rotate/guard) | #151 | ✅ |
| 63 | Admin test suite + RBAC matrix + security review | #152 | ✅ |

## Bug fixes landed (found via the phase 4-5 test suites, PR #147)

- **Secret-field persistence:** `password_hash`/`api_key_encrypted`/`token_hash`
  used `Field(exclude=True)`, which also dropped them from Beanie's stored doc —
  hashes were never written to Mongo. Removed `exclude=True`; secrets stay out of
  API responses via the DTO layer.
- **Analysis step state:** steps held a stale reference across `analysis.save()`
  (Beanie `merge_models` replaces the list), so completion never persisted —
  analyses finished with steps stuck `in_progress`. Step is now re-acquired.
- **Missing deps:** pinned `python-docx`/`pypdf` (text extraction) in #146.
- **last_active_at tz bug (#152):** `_touch_last_active` subtracted a tz-aware
  `now` from the tz-naive value Mongo returns, raising `TypeError` on a user's
  second request within 5 min. Now normalizes to UTC. Found by the admin RBAC
  matrix (real JWTs, no dependency override).

## Current State

**Server:** 325 passed, 2 skipped · ruff/mypy strict clean · 84% coverage (admin 98%)
**Frontend:** 51 passed · typecheck/lint/format clean · build emits per-route chunks

**Phases 0–7 complete + Phase 8 in progress.** Backend (0–6) and the frontend
foundation (7) are done. The candidate app is demoable end-to-end:
landing → register/login → dashboard (stats, resume table, optimistic delete) →
upload (validated dropzone + progress). Phase 8 done so far: #71, #72, #73, #74.

## Next Priority — resume at #77

- **#77 Resume editor (create flow)** — the largest single issue: a full
  json-resume form across all 12 sections + meta, partial-date fields, array
  add/remove/reorder, `pruneEmpty` before submit, section nav, per-field zod
  validation. The forms infra (#68: `TextField`/`ArrayField`/`DateField`) and a
  starter zod schema pattern are already in place to build on.
- Then #78 (in-place view/edit), #79 (upload review — also needs the server to
  expose `upload_parse` status on the resume response), #80–83 (analysis
  start/progress-SSE/results/apply), #86 (candidate test suite).
- Phase 9 (admin UI #87–89 + server export #90), Phase 10 (SPA serve, a11y/perf,
  Sentry, OTel, Playwright, hardening, docs), Phase 11 (Docker/CI/`railway.json`
  + runbook — prep only; **Railway deploy #103/#104 needs your account**).
