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

### Phase 6 — Admin Domain
| # | Task | PR | Status |
|---|------|----|--------|
| 59 | Admin stats endpoint (RBAC-guarded) | #145 | ✅ |
| 60 | Admin user management (search/update/reset/deactivate) | #149 | ✅ |
| 61 | Privacy-bounded resume administration (cascade delete) | #150 | ✅ |
| 62 | AI model settings endpoints (validate/rotate/guard) | #151 | ✅ |
| 63 | Admin test suite + RBAC matrix | — | ⏳ |

## Bug fixes landed (found via the phase 4-5 test suites, PR #147)

- **Secret-field persistence:** `password_hash`/`api_key_encrypted`/`token_hash`
  used `Field(exclude=True)`, which also dropped them from Beanie's stored doc —
  hashes were never written to Mongo. Removed `exclude=True`; secrets stay out of
  API responses via the DTO layer.
- **Analysis step state:** steps held a stale reference across `analysis.save()`
  (Beanie `merge_models` replaces the list), so completion never persisted —
  analyses finished with steps stuck `in_progress`. Step is now re-acquired.
- **Missing deps:** pinned `python-docx`/`pypdf` (text extraction) in #146.

## Current State

**Tests:** 242 passed, 2 skipped (0 failures)
**Lint/Format:** ruff clean, mypy strict clean
**Coverage:** 81% module-wide on server (gate ≥80%)

**Phases 0–5 complete.** Backend foundation, auth, resume domain, AI platform &
analysis pipeline, and notifications/realtime are all implemented and tested.

## Next Priority

- #60 Admin user management (area:server, P0):
  - GET /admin/users (search, paginate, sort)
  - PATCH /admin/users/{id}, deactivate/reactivate
  - POST /admin/users/{id}/reset-password
  - Admin cannot deactivate themselves
  - RBAC: candidate → 403 on all admin routes
