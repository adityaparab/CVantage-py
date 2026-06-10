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

### Phase 7 — Frontend Foundation
| # | Task | PR | Status |
|---|------|----|--------|
| 64 | Vite + React + TS scaffold (proxy, aliases, build) | #153 | ✅ |
| 65 | Design system & theming (Tailwind v4, UI kit, dark/light) | #154 | ✅ |
| 66 | Routing & layouts (guards, shells, lazy chunks, 404/403) | #155 | ✅ |
| 67 | API client & query layer (refresh queue, auth ctx, MSW) | #156 | ✅ |
| 68 | Forms infrastructure | — | ⏳ |
| 69 | Frontend test harness (Vitest+RTL+MSW stood up in #67) | — | ⏳ |

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

**Tests:** 325 passed, 2 skipped (0 failures)
**Lint/Format:** ruff clean, mypy strict clean
**Coverage:** 84% module-wide on server (gate ≥80%); admin module 98%

**Phases 0–6 complete (backend).** Backend foundation, auth, resume domain, AI
platform & analysis pipeline, notifications/realtime, and the full admin domain
(stats, user mgmt, privacy-bounded resume admin, AI model settings, RBAC matrix)
are implemented and tested. **Next: Phase 7 — Frontend Foundation.**

## Next Priority

- #64 Vite + React + TS scaffold (area:client, P0) — kicks off Phase 7
  (Frontend Foundation): scaffold, design system, routing, API client, forms,
  test harness. The entire frontend (Phases 7–9) is still to build.
- Phase 11 (Railway deploy, #103/#104) needs the user's Railway account/keys.
