# CVantage — MongoDB Schema

Two equivalent, production-grade implementations of the same data model (derived from `PROMPT.md`):

| Path | Stack | Entry point |
|---|---|---|
| `nestjs-mongoose/schemas.ts` | NestJS + @nestjs/mongoose (Mongoose 8) | `MongooseModule.forFeature(MODEL_DEFINITIONS)` |
| `fastapi-beanie/models.py` | FastAPI + Beanie ODM (Pydantic v2, async PyMongo/Motor) | `await init_beanie(database=db, document_models=DOCUMENT_MODELS)` |

## Collections

| Collection | Purpose |
|---|---|
| `users` | Candidates + admins. Single login flow; `role` enforces RBAC (no separate admin registration). Unique case-insensitive email; unique OAuth identity (Google/LinkedIn); denormalized `resumeCount`/`analysisCount` for dashboards; text index for admin user search. |
| `resumes` | Canonical resume stored as **json-resume-schema** (all sections incl. partial-date strings `YYYY[-MM[-DD]]`). Upload flow keeps `originalFile` (object-storage key, MIME whitelist .pdf/.doc/.docx, 10 MB cap), `originalText`, and `uploadParse` status. Rollup `analysisStatus` (unanalyzed/in_progress/completed/failed) drives the dashboard table. Soft delete; per-user unique name. |
| `analyses` | One doc per analysis run: `jobDescription`, immutable `resumeSnapshot`, fixed 3-step pipeline (compare → suggestions → interview questions) with per-step status, and the full result (overall/ATS/project scores 0–100, strong/weak points, matching skills, gaps, field-targeted suggestions with `applied` tracking, interview Q&A). Partial index serves the worker queue. |
| `notifications` | Bell notifications for analysis progress/completion. One active notification per analysis (unique partial index); cleared on details-page visit or manually; 30-day TTL. |
| `aimodels` | Admin settings: model name + provider (unique pair), AES-encrypted API key (never serialized) + `apiKeyLast4` for the masked UI, usage routing (parsing/analysis/fallback). |
| `authtokens` | Hashed refresh / password-reset / email-verify tokens. TTL on `expiresAt`. |
| `auditlogs` | Admin and security-relevant actions (user edits, password resets, resume deletions, model/key changes). 400-day TTL. |

## Key guarantees

- **Placeholders are never stored** — a recursive prune (Mongoose `pre('validate')` hook / Pydantic `model_validator`) strips empty strings, arrays, and objects from `jsonResume` before save.
- **Privacy** — admins see resume *names and counts* only; resume content and analysis results are never exposed through admin queries (enforce in the service layer; audit log stores redacted metadata only).
- **Secrets** — `passwordHash`, `apiKeyEncrypted`, `tokenHash` are `select: false` / `exclude=True` and stripped from JSON serialization.
- **Concurrency** — optimistic locking (Mongoose `optimisticConcurrency` / Beanie `use_revision`) on users, resumes, analyses.
- **Validation** — enums for every status, score ranges 0–100, JD length bounds, email/URL/partial-date formats, exactly-3-steps invariant, `completed ⇒ result present`.

Both files compile/validate clean: `tsc --strict` zero errors; Python models import and pass 12 validator smoke tests.
