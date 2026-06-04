# Issues — VoiceSaju

Generated: 2026-05-28
Source documents:
- `PRD.md` (2026-05-29)
- `docs/prd_digest.md`
- `docs/requirements.md` (17 user stories, 44 FRs, 17 NFRs)
- `docs/ux_spec.md` (26 screens, 9 flows)
- `docs/architecture.md` (Next.js + FastAPI modular monolith)
- `docs/data_model.md` (21 tables, 54 access patterns)
- `docs/design_philosophy.md`, `docs/design_system.md`, `docs/wireframes.md`, `docs/interactions.md`, `docs/copy_guide.md` (v2 — Ink, Amber & 印)

Confidence: **High** — All FRs (FR-001 to FR-044) and US-01 to US-17 mapped; NFR-001..017 covered through observability + AC. Open variables (exact pricing A-01, Toss WebView policy A-04, Supertone pricing DEP-01) flagged inline within issues that depend on them.

---

## Board (status quick-glance)

### Backlog
ISSUE-001 .. ISSUE-102 (see below; ISSUE-005, ISSUE-025, ISSUE-035, ISSUE-036, ISSUE-043, ISSUE-084, ISSUE-085 are `Status: deferred` to Phase 2)

### In Progress
(empty)

### Done
(empty)

---

## Milestone Index

- **M1: Foundation** — ISSUE-001 .. ISSUE-027
- **M2: Saju Reading Flow** — ISSUE-028 .. ISSUE-046
- **M3: Daily Tarot** — ISSUE-047 .. ISSUE-055
- **M4: Quote Card + Sharing** — ISSUE-056 .. ISSUE-062
- **M5: My Page** — ISSUE-063 .. ISSUE-073
- **M6: Polish + Launch** — ISSUE-074 .. ISSUE-090
- **M2.5: v2 Design Refinement (Ink, Amber & 印)** — ISSUE-091 .. ISSUE-098 (cross-cuts M2/M3/M4)
- **Mock Adapter Layer (Phase 1 PoC)** — ISSUE-099 .. ISSUE-102 (cross-cuts M1; unlocks M2/M3 vertical slice without external API keys)

---

# M1 — Foundation

## ISSUE-001: Bootstrap backend service skeleton (FastAPI + uv)
- Track: platform
- UI: false
- Platform: web
- Manual: false
- PRD-Ref: NFR-016
- Priority: P0
- Estimate: 1d
- Status: backlog
- Owner:
- Branch:
- GH-Issue:
- PR:
- Depends-On: none

### Goal
A FastAPI 0.110+ service runs locally via `uv run uvicorn` and exposes `/healthz`.

### Scope (In/Out)
- In: `api/pyproject.toml` (uv-managed), FastAPI app factory (`voicesaju/main.py`), Pydantic v2 settings (`config.py`), `/healthz` endpoint returning `{status:"ok"}`, Uvicorn entrypoint, Ruff + Black config.
- Out: DB connection, auth, business logic.

### Acceptance Criteria (DoD)
- [ ] Given a fresh checkout, when I run `uv sync && uv run uvicorn voicesaju.main:app`, then the server starts on port 8000.
- [ ] Given the server is running, when I `GET /healthz`, then I receive `200 {"status":"ok"}`.
- [ ] Given I run `uv run pytest -q`, then the test suite passes (≥1 healthcheck test).
- [ ] Given I run `uv run ruff check . && uv run black --check .`, then no lint errors are reported.

### Implementation Notes
- Architecture §2 — pin Python 3.11+, FastAPI 0.110+, Uvicorn 0.27+, asyncpg 0.29+.
- Settings via Pydantic v2 `BaseSettings`; read `.env.local` for dev.
- Follow `claude.md` rules: `uv` for deps, `pytest` for tests.

### Tests
- [ ] `tests/unit/test_health.py::test_healthz_returns_ok`
- [ ] App factory does not raise on import (smoke).

### Rollback
- Delete `api/` directory; no schema or external resource created.

---

## ISSUE-002: Bootstrap Next.js 15 frontend skeleton
- Track: frontend
- UI: true
- Platform: web
- Manual: false
- PRD-Ref: NFR-014
- Priority: P0
- Estimate: 1d
- Status: backlog
- Owner:
- Branch:
- GH-Issue:
- PR:
- Depends-On: none

### Goal
A Next.js 15 (App Router, TypeScript, RSC) project runs locally and renders a placeholder landing route.

### Scope (In/Out)
- In: `web/` Next.js 15 + TypeScript + Tailwind CSS + shadcn/ui setup, `app/page.tsx` placeholder landing, ESLint + Prettier config, `tsconfig.json` strict mode.
- Out: Real landing UI, components, routing for other screens.

### Acceptance Criteria (DoD)
- [ ] Given a fresh checkout, when I run `pnpm install && pnpm dev`, then `http://localhost:3000/` renders a placeholder "VoiceSaju" headline.
- [ ] Given I run `pnpm typecheck`, then TypeScript reports zero errors.
- [ ] Given I run `pnpm lint`, then ESLint reports zero errors.
- [ ] Given I run `pnpm build`, then the production build succeeds.

### Implementation Notes
- Architecture §2 — Next.js 15.x, Tailwind 3.x, Zustand 4.x.
- App Router + RSC by default (FR-020 OG image generation requires SSR/Edge).
- Set up `app/layout.tsx` with global Korean font (Pretendard recommended).

### Tests
- [ ] `pnpm test` runs Vitest smoke test that mounts `<HomePage />`.
- [ ] `pnpm build` produces `.next/` output.

### Rollback
- Delete `web/` directory.

---

## ISSUE-003: Configure GitHub Actions CI (lint + test + typecheck)
- Track: platform
- UI: false
- Platform: web
- Manual: false
- PRD-Ref: NFR-017
- Priority: P0
- Estimate: 0.5d
- Status: backlog
- Owner:
- Depends-On: ISSUE-001, ISSUE-002

### Goal
Every PR triggers backend + frontend lint/typecheck/test in GitHub Actions.

### Scope (In/Out)
- In: `.github/workflows/ci.yml` with two jobs (backend: ruff + black + pytest; frontend: eslint + tsc + vitest); uses uv setup action; caches deps.
- Out: Deploy steps, secrets, release pipelines.

### Acceptance Criteria (DoD)
- [ ] Given a PR is opened, when CI runs, then both backend and frontend jobs report status checks.
- [ ] Given a backend test fails, when CI runs, then the PR cannot be merged (required check).
- [ ] Given dependency cache is cold, when CI runs, then total runtime is < 5 minutes.

### Implementation Notes
- Architecture §13.2 — pipeline stages.
- Use `astral-sh/setup-uv@v3` for backend; `pnpm/action-setup` + `actions/setup-node@v4` for frontend.

### Tests
- [ ] Workflow YAML is valid (`act -l` or `actionlint`).
- [ ] Triggered on `pull_request` and `push: main`.

### Rollback
- Remove `.github/workflows/ci.yml`.

---

## ISSUE-004: Manual setup — provision PostgreSQL 16 + Redis 7 (staging)
- Track: platform
- UI: false
- Platform: web
- Manual: false
- PRD-Ref: NFR-005, NFR-016
- Priority: P0
- Estimate: 0.5d
- Status: backlog
- Owner:
- Depends-On: none

> **Note (2026-05-28):** Manual external provisioning is no longer required for Phase 1 PoC. Use docker-compose.yml from ISSUE-001 deliverable (Postgres 16 + Redis 7 containers). Cloud provisioning deferred to Phase 2 (post-MVP launch).

### Goal
A managed PostgreSQL 16 instance and Redis 7 instance exist with credentials stored in the secrets manager.

### Scope (In/Out)
- In: Provision Fly Postgres OR Neon/Supabase (Postgres 16) for staging; provision Upstash Redis 7 (NRT region); store `DATABASE_URL`, `REDIS_URL` in Doppler / Fly secrets / Vercel env.
- Out: Application code changes, schema creation, prod resources.

### Acceptance Criteria (DoD)
- [ ] Given staging Postgres is provisioned, when I `psql $DATABASE_URL -c "SELECT version()"`, then output shows PostgreSQL 16.x.
- [ ] Given Upstash Redis is provisioned, when I `redis-cli -u $REDIS_URL PING`, then output is `PONG`.
- [ ] Given the secrets manager is configured, when I run `doppler secrets get DATABASE_URL`, then the value is masked but present.
- [ ] Given developers join the project, when they read `docs/deployment.md` (or RUNBOOK), then connection steps are documented.

### Implementation Notes
- Architecture §13.1 — Fly Postgres OR Neon/Supabase; Upstash Redis TLS.
- Do NOT commit credentials to repo. `.env.example` only.

### Tests
- [ ] Manual `psql` connectivity check passes.
- [ ] Redis CLI PING passes.

### Rollback
- Delete instances from cloud provider console.

---

## ISSUE-005: Manual setup — provision Cloudflare R2 bucket
- Track: platform
- UI: false
- Platform: web
- Manual: true
- PRD-Ref: NFR-005, FR-018, FR-028
- Priority: P0
- Estimate: 0.5d
- Status: deferred
- Owner:
- Depends-On: none

> **Note (2026-05-28):** Deferred to Phase 2. v1 uses local filesystem storage via MockStorageAdapter built into ISSUE-099. Cloudflare R2 provisioning will resume when Phase 2 launches.

### Goal
A Cloudflare R2 bucket exists for audio + OG assets with S3-compatible credentials in secrets manager.

### Scope (In/Out)
- In: Create R2 bucket `voicesaju-media-staging`; generate access key + secret with read/write scope; store as `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_ENDPOINT`, `R2_BUCKET` in secrets manager; create initial folder structure (`audio/`, `og/`, `static/`).
- Out: Production bucket, CDN config, public-read policy.

### Acceptance Criteria (DoD)
- [ ] Given R2 bucket is created, when I `aws s3 ls --endpoint-url=$R2_ENDPOINT s3://voicesaju-media-staging`, then the bucket lists without error.
- [ ] Given credentials are stored, when I read secrets from Doppler/Fly, then all 4 R2 variables are present.

### Implementation Notes
- Architecture §13.1 — public-read with signed URLs only.
- Bucket region: NRT (Tokyo) preferred for KR latency.

### Tests
- [ ] Manual upload/download via `aws s3 cp` works.

### Rollback
- Delete R2 bucket from Cloudflare dashboard.

---

## ISSUE-006: Configure SQLAlchemy 2.0 async + Alembic
- Track: backend
- UI: false
- Platform: web
- Manual: false
- PRD-Ref: NFR-005
- Priority: P0
- Estimate: 1d
- Status: backlog
- Owner:
- Depends-On: ISSUE-001, ISSUE-004

### Goal
The FastAPI service connects to Postgres via SQLAlchemy 2.0 async engine, and Alembic is wired with an empty initial migration.

### Scope (In/Out)
- In: `voicesaju/db/engine.py` (async engine + sessionmaker), `voicesaju/db/base.py` (declarative base), `alembic/` directory with `env.py` configured for async, empty `0001_initial.py`, `make migrate` / `uv run alembic upgrade head` works.
- Out: Actual table definitions (separate issues).

### Acceptance Criteria (DoD)
- [ ] Given staging DB is reachable, when I run `uv run alembic upgrade head`, then Alembic creates `alembic_version` table.
- [ ] Given the app starts, when I `GET /healthz/db`, then it returns `{"status":"ok","db":"connected"}`.
- [ ] Given I run `uv run alembic check`, then no pending model-vs-schema drift errors appear (initial state).

### Implementation Notes
- Architecture §2, §5.4 — SA 2.0 + asyncpg; forward-only migrations.
- Alembic `env.py` must use `async` engine (see SA 2.0 docs).
- Add `pre-commit` hook to verify no `downgrade()` body in new migrations.

### Tests
- [ ] `tests/unit/test_db_engine.py::test_engine_creates_session`
- [ ] Migration up/down on an in-memory test DB (or testcontainers Postgres).

### Rollback
- `alembic downgrade base` against staging; remove `alembic/` files.

---

## ISSUE-007: Implement enums + initial migration (0001_initial)
- Track: backend
- UI: false
- Platform: web
- Manual: false
- PRD-Ref: FR-001..036 (foundation)
- Priority: P0
- Estimate: 0.5d
- Status: backlog
- Owner:
- Depends-On: ISSUE-006

### Goal
All 11 Postgres enums from data_model §4.1 exist in the DB.

### Scope (In/Out)
- In: Alembic migration that creates `gender_enum`, `category_enum`, `reading_status_enum`, `tarot_status_enum`, `payment_type_enum`, `payment_method_enum`, `payment_status_enum`, `subscription_status_enum`, `free_token_kind_enum`, `auth_provider_enum`, `character_key_enum`, `tone_eval_label_enum`, `audit_action_enum`.
- Out: Tables that use these enums.

### Acceptance Criteria (DoD)
- [ ] Given the migration runs, when I `SELECT typname FROM pg_type WHERE typtype='e'`, then all 13 enums are listed.
- [ ] Given a downgrade is attempted via a compensating migration, when run, then enums drop cleanly.

### Implementation Notes
- data_model §4.1 — exact enum values.
- Use `sa.Enum(..., name="gender_enum", create_type=True)`.

### Tests
- [ ] Migration applies on fresh DB.
- [ ] Each enum has the documented set of values.

### Rollback
- Compensating migration `DROP TYPE`.

---

## ISSUE-008: Implement users + devices tables + indexes
- Track: backend
- UI: false
- Platform: web
- Manual: false
- PRD-Ref: FR-016, FR-003
- Priority: P0
- Estimate: 1d
- Status: backlog
- Owner:
- Depends-On: ISSUE-007

### Goal
`users` and `devices` tables exist with SQLAlchemy models and all indexes from data_model §5.1–§5.2.

### Scope (In/Out)
- In: Alembic migration; SQLAlchemy models `User`, `Device`; uuidv7 default; partial unique indexes on `kakao_sub`, `apple_sub`, `toss_id`; CHECK constraint requiring ≥1 provider; `device_id_client` unique.
- Out: Auth routes, session middleware.

### Acceptance Criteria (DoD)
- [ ] Given the migration runs, when I `\d users` in psql, then all columns and indexes from data_model §4.2 + §5.1 are present.
- [ ] Given I insert a User with no provider columns set, when committed, then the CHECK constraint fails.
- [ ] Given I insert two Users with the same `kakao_sub`, when committed, then the second fails on the partial unique index.

### Implementation Notes
- data_model §4.2, §4.4, §5.1, §5.2 — exact schema.
- Use `uuid-utils` or Python `uuid7()` polyfill for uuidv7.

### Tests
- [ ] `tests/unit/users/test_user_model.py` — CHECK constraint enforced.
- [ ] Unique index test on `kakao_sub` with NULL-tolerance.

### Rollback
- Compensating migration drops tables.

---

## ISSUE-009: Implement KMS envelope encryption helpers (security/envelope.py)
- Track: backend
- UI: false
- Platform: web
- Manual: false
- PRD-Ref: NFR-005
- Priority: P0
- Estimate: 1.5d
- Status: backlog
- Owner:
- Depends-On: ISSUE-001

### Goal
`security.envelope.encrypt_field(plaintext, user_id, column)` and `decrypt_field(envelope)` produce/consume AES-256-GCM envelopes per data_model §4.25.

### Scope (In/Out)
- In: `voicesaju/security/envelope.py` with encrypt/decrypt; `voicesaju/security/kms.py` abstracting KMS provider (with local-dev `LocalKMS` using a static KEK file gitignored); JSONB envelope schema validation; AAD = `user_id:<uuid>:profile:<column>`.
- Out: Actual table integration (profiles), KMS prod credentials.

### Acceptance Criteria (DoD)
- [ ] Given plaintext `"2000-01-01T07:30:00Z"`, when I call `encrypt_field`, then I get a JSONB dict with all 7 envelope keys (`kek_version`, `wrapped_dek`, `iv`, `ciphertext`, `tag`, `algorithm`, `aad`).
- [ ] Given an encrypted envelope, when I call `decrypt_field` with the correct user_id, then plaintext is recovered byte-for-byte.
- [ ] Given an envelope encrypted for user_A, when I call `decrypt_field` with user_B's id, then decryption fails (AAD mismatch → exception raised).
- [ ] Given a key rotation (new `kek_version`), when I call `rewrap_dek(envelope, new_kek)`, then `ciphertext` is unchanged but `wrapped_dek` differs.

### Implementation Notes
- data_model §4.25 — exact envelope shape.
- Use `cryptography` library (AES-256-GCM); 12-byte IV, 16-byte tag.
- LocalKMS reads KEK from `LOCAL_KEK_BASE64` env var.

### Tests
- [ ] Round-trip test (encrypt → decrypt) for 100 random payloads.
- [ ] AAD mismatch test.
- [ ] Key rotation test.
- [ ] Determinism guard: ciphertext differs across runs (IV randomness) but plaintext recovers.

### Rollback
- Remove `security/envelope.py` and `security/kms.py`.

---

## ISSUE-010: Implement profiles + saju_charts tables with envelope encryption
- Track: backend
- UI: false
- Platform: web
- Manual: false
- PRD-Ref: FR-027, NFR-005, FR-030
- Priority: P0
- Estimate: 1d
- Status: backlog
- Owner:
- Depends-On: ISSUE-008, ISSUE-009

### Goal
`profiles` and `saju_charts` tables exist with `birth_dt_enc` as JSONB; models use the envelope helpers from ISSUE-009.

### Scope (In/Out)
- In: Alembic migration for `profiles` + `saju_charts`; `Profile`, `SajuChart` SA models; property accessors that decrypt on read and encrypt on write via `envelope.py`; all constraints/indexes from data_model §5.3–§5.4.
- Out: Reading/Tarot tables, saju engine, profile API routes.

### Acceptance Criteria (DoD)
- [ ] Given a Profile is created with `birth_dt='2000-01-01T07:30Z'`, when persisted, then `birth_dt_enc` JSONB has 7 envelope keys and `SELECT birth_dt_enc::text` does not contain "2000".
- [ ] Given a Profile is read, when accessed via `profile.birth_dt`, then plaintext is returned.
- [ ] Given a SajuChart row, when I `SELECT chart_hash`, then it's a 64-char hex string.
- [ ] Given `birth_time_known=False`, when stored, then `pillars->'hour'` is JSON null.

### Implementation Notes
- data_model §4.5, §4.6, §5.3, §5.4.
- Add CHECK `(time_known) = (pillars->'hour' IS NOT NULL)` (drop if conflicts with JSONB semantics — confirm in test).

### Tests
- [ ] Roundtrip test: insert with plaintext property → reload → assert plaintext equal.
- [ ] DB dump (text) does not contain plaintext birth date.
- [ ] Correction counter increments correctly (boundary 0→1→2 OK, 2→3 raises CHECK error).

### Rollback
- Compensating migration drops tables.

---

## ISSUE-011: Implement saju calculation engine (FR-030)
- Track: backend
- UI: false
- Platform: web
- Manual: false
- PRD-Ref: FR-030, FR-031, NFR-017
- Priority: P0
- Estimate: 1.5d
- Status: backlog
- Owner:
- Depends-On: ISSUE-010

### Goal
`saju.engine.compute_chart(birth_dt_kst, is_lunar, gender, time_unknown) -> SajuChart` returns deterministic 4-pillar charts using `manseryeok` + `korean-lunar-calendar`.

### Scope (In/Out)
- In: `voicesaju/saju/engine.py`, `voicesaju/saju/lunar.py`, `voicesaju/saju/models.py` (Pillar, Stem, Branch, FiveElements, TenGods); `chart_hash(chart)` SHA-256; `ENGINE_VERSION` constant; cache lookup against `saju_charts.chart_hash`.
- Out: Validation fixture suite (ISSUE-012), API routes.

### Acceptance Criteria (DoD)
- [ ] Given identical inputs, when `compute_chart` is called 3 times, then output is bit-for-bit identical (NFR-017).
- [ ] Given `is_lunar=True`, when invoked, then lunar→solar conversion uses `korean-lunar-calendar`.
- [ ] Given `time_unknown=True`, when invoked, then `chart.hour is None` and 3 pillars are returned.
- [ ] Given `time_unknown=False`, when invoked, then all 4 pillars contain `stem`, `branch`, `element`, `ten_god`.
- [ ] Given two users with identical inputs, when both compute, then they share the same `chart_hash` and the second hits the cache (DB-level UNIQUE).

### Implementation Notes
- Architecture §9 — pure-function engine; pin `manseryeok` exact version.
- `ENGINE_VERSION = "saju.v1.2026-05"`.

### Tests
- [ ] `tests/unit/saju/test_engine_determinism.py` — 10 inputs × 3 runs identical.
- [ ] `tests/unit/saju/test_lunar_conversion.py` — known lunar→solar pairs.
- [ ] `tests/unit/saju/test_time_unknown.py` — Hour pillar omitted.

### Rollback
- Remove `voicesaju/saju/` module.

---

## ISSUE-012: Build saju engine validation fixture suite (≥50 cases)
- Track: backend
- UI: false
- Platform: web
- Manual: false
- PRD-Ref: FR-030, NFR-017, DEP-04
- Priority: P0
- Estimate: 1.5d
- Status: backlog
- Owner:
- Depends-On: ISSUE-011

### Goal
`tests/fixtures/saju_known_cases.json` contains ≥ 50 hand-verified 명식 examples, and CI runs them on every PR.

### Scope (In/Out)
- In: 50+ entries with `{birth_dt, is_lunar, gender, time_unknown, expected_pillars}` curated from textbook references or trusted manseryeok websites; pytest regression test that runs all cases 3× per run; CI job that blocks merge on any miss.
- Out: Fixing `manseryeok` library bugs (out of scope; falls back to thin adapter or library swap if a case fails).

### Acceptance Criteria (DoD)
- [ ] Given ≥50 cases exist, when I run `uv run pytest tests/regression/test_saju_known_cases.py`, then all cases pass.
- [ ] Given any case fails, when CI runs, then the PR is blocked.
- [ ] Given a single case is run 3× in a row, when compared, then outputs are byte-identical.

### Implementation Notes
- Architecture §9.3 — JSON schema; mix of `time_unknown=True`/`False` and solar/lunar.
- Document each fixture's source in a `comment` field.

### Tests
- [ ] Regression test passes all fixtures.
- [ ] Determinism check (3× run) included in fixture runner.

### Rollback
- Skip regression CI job; library swap if `manseryeok` proves unreliable.

---

## ISSUE-013: Implement free_tokens table + service
- Track: backend
- UI: false
- Platform: web
- Manual: false
- PRD-Ref: FR-003, FR-017, FR-023
- Priority: P0
- Estimate: 1d
- Status: backlog
- Owner:
- Depends-On: ISSUE-008

### Goal
`free_tokens` table and `users.services.token_service` support idempotent grant + consume operations.

### Scope (In/Out)
- In: Migration for `free_tokens` table; `FreeToken` model; `grant_signup_token(user_id)`, `grant_nonmember_trial(device_id)`, `grant_compensation(user_id)`, `consume_token(token_id, reading_id)` service methods; partial unique indexes per data_model §5.5.
- Out: API routes (covered when paywall builds out).

### Acceptance Criteria (DoD)
- [ ] Given user_A has no signup_grant token, when `grant_signup_token(user_A)` is called, then 1 row is inserted with `kind='signup_grant'`, `consumed_at=NULL`.
- [ ] Given user_A already has a signup_grant token, when `grant_signup_token(user_A)` is called again, then the partial unique index prevents a second row (idempotent).
- [ ] Given a token exists, when `consume_token(token_id, reading_id)` is called, then `consumed_at` and `consumed_by_reading_id` are set atomically.
- [ ] Given a free_token row has neither `user_id` nor `device_id`, when committed, then the CHECK constraint fails.

### Implementation Notes
- data_model §4.7, §5.5.
- Use `ON CONFLICT DO NOTHING` semantics in SA upsert.

### Tests
- [ ] `tests/unit/users/test_token_service.py::test_idempotent_signup_grant`
- [ ] `tests/unit/users/test_token_service.py::test_consume_marks_timestamps`

### Rollback
- Compensating migration drops table.

---

## ISSUE-014: Implement payments + subscriptions + refunds tables
- Track: backend
- UI: false
- Platform: web
- Manual: false
- PRD-Ref: FR-021, FR-022, FR-023
- Priority: P0
- Estimate: 1d
- Status: backlog
- Owner:
- Depends-On: ISSUE-008

### Goal
`payments`, `subscriptions`, `refunds` tables exist with models, constraints, indexes per data_model §4.13–§4.15.

### Scope (In/Out)
- In: Alembic migration; SA models `Payment`, `Subscription`, `Refund`; all CHECK constraints + partial unique indexes from §5.9–§5.11.
- Out: Toss client integration, webhook handlers.

### Acceptance Criteria (DoD)
- [ ] Given a Payment is inserted with `amount_krw=0`, when committed, then CHECK constraint fails.
- [ ] Given two Payments share the same `toss_order_id`, when committed, then unique index rejects the second.
- [ ] Given a user has an `active` subscription and another `active` is inserted, when committed, then partial unique index rejects.
- [ ] Given `refunded_amount_krw > amount_krw`, when committed, then CHECK fails.

### Implementation Notes
- data_model §4.13–§4.15, §5.9–§5.11.
- `subscriptions.monthly_saju_remaining` CHECK between 0 and 1.

### Tests
- [ ] `tests/unit/payment/test_models.py` — all constraints enforced.

### Rollback
- Compensating migration drops tables.

---

## ISSUE-015: Implement readings + transcripts + followups + audio tables
- Track: backend
- UI: false
- Platform: web
- Manual: false
- PRD-Ref: FR-007, FR-009, FR-010, FR-028
- Priority: P0
- Estimate: 1d
- Status: backlog
- Owner:
- Depends-On: ISSUE-010, ISSUE-013, ISSUE-014

### Goal
`readings`, `reading_transcripts`, `reading_followups`, `reading_audio` tables exist with models and all indexes from data_model §5.6–§5.7.

### Scope (In/Out)
- In: Alembic migration; SA models with FK relationships; CHECK constraints linking `entitlement_kind` to `payment_id` / `subscription_id` / `free_token_id`; `idempotency_key` unique; `reading_audio.duration_ms` between 60s–120s CHECK.
- Out: Pipeline orchestration (ISSUE-031+).

### Acceptance Criteria (DoD)
- [ ] Given `entitlement_kind='payment'` but `payment_id=NULL`, when committed, then CHECK fails.
- [ ] Given a Reading has 4 followups, when inserting the 4th with `slot_index=3`, then CHECK fails (range 0..2).
- [ ] Given two followups share `(reading_id, slot_index)`, when committed, then unique index rejects.

### Implementation Notes
- data_model §4.8–§4.11, §5.6–§5.7.

### Tests
- [ ] `tests/unit/reading/test_reading_model.py` — all entitlement CHECKs.
- [ ] Slot index uniqueness test.

### Rollback
- Compensating migration drops tables.

---

## ISSUE-016: Implement tarot_cards + tarot_draws tables + seed
- Track: backend
- UI: false
- Platform: web
- Manual: false
- PRD-Ref: FR-012, FR-013, FR-014, FR-015
- Priority: P0
- Estimate: 1d
- Status: backlog
- Owner:
- Depends-On: ISSUE-010

### Goal
`tarot_cards` (seeded with 22 Major Arcana) and `tarot_draws` tables exist with all indexes from §5.8.

### Scope (In/Out)
- In: Alembic migration for both tables; `TarotCard`, `TarotDraw` models; seed insert of 22 cards (indices 0–21) with KR/EN names + meanings + placeholder R2 art keys; partial unique indexes for `(user_id, date_kst)` and `(device_id, date_kst)`.
- Out: Card art assets (content production), tarot pipeline.

### Acceptance Criteria (DoD)
- [ ] Given the migration runs, when I `SELECT COUNT(*) FROM tarot_cards`, then I get 22.
- [ ] Given two TarotDraws for the same user_id + date_kst, when committed, then partial unique index rejects.
- [ ] Given a draw with neither `user_id` nor `device_id`, when committed, then CHECK fails.

### Implementation Notes
- data_model §4.12, §4.17, §5.8, §7.1.
- Use `ON CONFLICT (card_index) DO NOTHING` for idempotent seed.

### Tests
- [ ] All 22 indices present after migration.
- [ ] Idempotency check (rerun migration → no duplicate).

### Rollback
- Compensating migration drops tables.

---

## ISSUE-017: Implement quote_cards + intro_audio_clips + character_voices tables + seed
- Track: backend
- UI: false
- Platform: web
- Manual: false
- PRD-Ref: FR-005, FR-018, FR-020
- Priority: P0
- Estimate: 1d
- Status: backlog
- Owner:
- Depends-On: ISSUE-015, ISSUE-016

### Goal
`quote_cards`, `intro_audio_clips`, `character_voices` tables exist; seed data includes 6 intro placeholders + 2 character voices.

### Scope (In/Out)
- In: Migration; `QuoteCard`, `IntroAudioClip`, `CharacterVoice` models; seed 2 character voices (`nuna`, `dosa` with `TBD_*_VOICE_ID`) and 6 intro placeholders (3 categories × 2 birth_time variants); CHECK on `quote_text ≤ 40 chars`; `share_slug` unique.
- Out: Actual audio production (DEP-07).

### Acceptance Criteria (DoD)
- [ ] Given the migration runs, when I `SELECT * FROM character_voices`, then 2 rows exist with `character_key IN ('nuna','dosa')`.
- [ ] Given the migration runs, when I `SELECT COUNT(*) FROM intro_audio_clips`, then 6 rows exist.
- [ ] Given a QuoteCard with `quote_text` of 41 chars, when committed, then CHECK fails.

### Implementation Notes
- data_model §4.16, §4.18, §4.19, §7.2, §7.3.

### Tests
- [ ] Seed idempotency rerun test.

### Rollback
- Compensating migration drops tables.

---

## ISSUE-018: Implement tone_prompt_versions + tone_eval_cases + tone_violation_events tables
- Track: backend
- UI: false
- Platform: web
- Manual: false
- PRD-Ref: FR-032, NFR-010
- Priority: P0
- Estimate: 1d
- Status: backlog
- Owner:
- Depends-On: ISSUE-015, ISSUE-016

### Goal
All three tone-related tables exist with constraints from data_model §4.20–§4.22.

### Scope (In/Out)
- In: Migration; SA models; `tone_prompt_versions` partial unique on `(prompt_key) WHERE is_active=true`; CHECK on `prompt_key`, `layer`, `severity`, `category_tag` values.
- Out: Actual prompts (covered in M2 issues), eval cases (covered in ISSUE-019).

### Acceptance Criteria (DoD)
- [ ] Given two `tone_prompt_versions` rows with same `prompt_key` both `is_active=true`, when committed, then partial unique index rejects the second.
- [ ] Given a `tone_violation_events` row with both `reading_id` and `tarot_id` NULL, when committed, then CHECK fails.

### Implementation Notes
- data_model §4.20–§4.22, §5.14.

### Tests
- [ ] Active-singleton invariant test.

### Rollback
- Compensating migration drops tables.

---

## ISSUE-019: Build tone evaluation set (≥ 50 cases) + CI regression
- Track: backend
- UI: false
- Platform: web
- Manual: false
- PRD-Ref: FR-032
- Priority: P0
- Estimate: 1.5d
- Status: backlog
- Owner:
- Depends-On: ISSUE-018

### Goal
`tests/fixtures/tone_evalset.json` contains ≥ 50 labeled cases (ok/violation), seeded into `tone_eval_cases`, and CI runs the regression on every PR.

### Scope (In/Out)
- In: 50+ JSON cases covering profanity/hate/sexual/discrimination/borderline-spicy; CI test that exercises the deny-list against each case and asserts 100% of `violation` cases blocked + ≥ 95% of `ok` cases preserved; seed migration loading the cases.
- Out: The deny-list itself (ISSUE-020).

### Acceptance Criteria (DoD)
- [ ] Given the fixture file exists, when I `cat tests/fixtures/tone_evalset.json | jq 'length'`, then ≥ 50.
- [ ] Given the CI regression runs, when all cases pass thresholds, then exit code 0.
- [ ] Given a violation case is not blocked by the deny-list, when CI runs, then the build fails.

### Implementation Notes
- Architecture §7.3 — layer-2 release gate.
- Cases must be Korean text; include borderline cases ("매운맛 ≠ 욕설").

### Tests
- [ ] CI job exists and is required for merge.

### Rollback
- Skip CI regression job.

---

## ISSUE-020: Implement deny-list tone guardrail (FR-032 layer 3)
- Track: backend
- UI: false
- Platform: web
- Manual: false
- PRD-Ref: FR-032, NFR-010
- Priority: P0
- Estimate: 1d
- Status: backlog
- Owner:
- Depends-On: ISSUE-019

### Goal
`llm.guardrail.denylist.filter_chunk(text) -> FilterResult` returns either `pass`, `substitute(safe_text)`, or `block` based on a curated Korean deny-list.

### Scope (In/Out)
- In: `voicesaju/llm/guardrail/denylist.py` with Aho-Corasick scanner; Korean deny list (profanity/hate/sexual/discrimination); safe-substitute phrase per character (`nuna`, `dosa`); `ToneViolationEvent` insert on hit.
- Out: Moderation API call (deferred per OQ-07).

### Acceptance Criteria (DoD)
- [ ] Given a chunk containing a deny-list term, when filtered, then returns `substitute` and inserts a `tone_violation_events` row.
- [ ] Given a clean chunk, when filtered, then returns `pass`.
- [ ] Given 50+ tone eval cases (ISSUE-019), when run through the filter, then 100% of `violation` cases are caught.

### Implementation Notes
- Architecture §7.3 — Aho-Corasick on streaming tokens.
- Sanitize triggering content before storing in DB (mask profanity).

### Tests
- [ ] Filter unit tests for each category.
- [ ] Regression against tone_evalset.

### Rollback
- Default to `pass` if module fails (fail-open is unacceptable; must alert instead — wire to Sentry).

---

## ISSUE-021: Implement design system tokens + base UI components
- Track: frontend
- UI: true
- Platform: web
- Manual: false
- PRD-Ref: NFR-012, NFR-014
- Priority: P0
- Estimate: 1.5d
- Status: backlog
- Owner:
- Depends-On: ISSUE-002

### Goal
Tailwind theme is configured with category colors (love=pink, work=blue, money=gold, tarot=purple), typography (Pretendard), spacing scale, and 8 foundational components are built per ux_spec §6.

### Scope (In/Out)
- In: `tailwind.config.ts` with full token set; components `<PrimaryButton>`, `<SecondaryButton>`, `<TertiaryLink>`, `<CategoryCard>`, `<OptionCard>`, `<StepIndicator>`, `<Toast>`, `<Banner>`; Storybook setup (optional but recommended) or component preview page.
- Out: Character-specific or voice-specific components (separate issues).

### Acceptance Criteria (DoD)
- [ ] Given Tailwind config is loaded, when I use `bg-category-love` / `bg-category-work` / `bg-category-money` / `bg-category-tarot`, then the correct hex is applied.
- [ ] Given the component preview page is loaded, when I view it, then all 8 components render in default/disabled/loading states.
- [ ] Given I run axe-core on the preview page, when scanned, then zero AA violations (NFR-012).
- [ ] Given keyboard-only navigation, when I tab through components, then visible focus rings appear on every interactive element (NFR-013).

### Implementation Notes
- ux_spec §6, §5.5 — color tokens; A-06 hex values approximate (pending design finalization).
- Use shadcn/ui primitives as base.

### Tests
- [ ] Vitest + Testing Library snapshot tests per component.
- [ ] axe-core a11y test on preview page.

### Rollback
- Remove component files; revert Tailwind config.

---

## ISSUE-022: Implement BottomTabBar + TopAppBar + ConfirmModal + BottomSheet
- Track: frontend
- UI: true
- Platform: web
- Manual: false
- PRD-Ref: US-01..US-17 (navigation foundation)
- Priority: P0
- Estimate: 1d
- Status: backlog
- Owner:
- Depends-On: ISSUE-021

### Goal
Navigation chrome + modal primitives are implemented and accessible.

### Scope (In/Out)
- In: `<BottomTabBar>` (3 tabs: 사주 / 오늘의 타로 / 마이; hide-on-playback prop), `<TopAppBar>` (back/title/action slots), `<ConfirmModal>` (focus-trapped), `<BottomSheet>` (slide-up, swipe-dismiss).
- Out: Wiring to real routes (covered when each screen lands).

### Acceptance Criteria (DoD)
- [ ] Given BottomTabBar is rendered with `hideOnPlayback={true}`, when I check the DOM, then the bar is absent.
- [ ] Given a ConfirmModal opens, when I press Tab, then focus stays within the modal; when I press ESC, then the modal closes.
- [ ] Given a BottomSheet opens on mobile viewport, when I swipe down, then it dismisses.
- [ ] Given axe-core scans the page with each component open, when scanned, then zero AA violations.

### Implementation Notes
- ux_spec §5.2 (focus management) + §6.1 (components).
- BottomTabBar: non-member 마이 tab opens signup modal instead of `/me`.

### Tests
- [ ] Focus-trap test for ConfirmModal.
- [ ] ESC dismisses modal.

### Rollback
- Remove component files.

---

## ISSUE-023: Implement runtime context detection (Web vs Toss WebView)
- Track: frontend
- UI: false
- Platform: web
- Manual: false
- PRD-Ref: FR-024, FR-019
- Priority: P0
- Estimate: 0.5d
- Status: backlog
- Owner:
- Depends-On: ISSUE-002

### Goal
`useRuntimeContext()` React hook returns `{ channel: 'web' | 'toss_webview', capabilities: {...} }` based on user-agent + Toss JS bridge detection.

### Scope (In/Out)
- In: `web/src/lib/context/runtime-context.tsx` provider + hook; user-agent regex for `Toss/`; Toss JS bridge ping check; capabilities object (`canShareInstagram`, `canShareKakao`, `canSaveImage`); persisted in React context.
- Out: UI adaptations (covered in payment/share/auth issues).

### Acceptance Criteria (DoD)
- [ ] Given a request from Chrome, when the hook runs, then `channel='web'`.
- [ ] Given a request from a UA containing `Toss/`, when the hook runs, then `channel='toss_webview'`.
- [ ] Given the hook is called in SSR, when rendered, then no errors (uses default Web context until hydration).

### Implementation Notes
- Architecture §4.1 — runtime context detection.
- A-04 unconfirmed; default capabilities to `{ canShareInstagram: false, canShareKakao: false, canSaveImage: true }` in Toss WebView until verified.

### Tests
- [ ] Unit tests with mocked UA strings.

### Rollback
- Remove provider; default everything to `web`.

---

## ISSUE-024: Implement device ID issuance (anonymous tracking)
- Track: backend
- UI: false
- Platform: web
- Manual: false
- PRD-Ref: FR-003, FR-013
- Priority: P0
- Estimate: 1d
- Status: backlog
- Owner:
- Depends-On: ISSUE-008

### Goal
`POST /api/v1/auth/device` issues a `device_id`, upserts a `devices` row, and sets an HttpOnly cookie `vs_did`.

### Scope (In/Out)
- In: FastAPI route; `users.services.device_service.upsert_device(device_id_client)`; cookie set with `HttpOnly`, `Secure`, `SameSite=Lax`, 1-year expiry; client-side helper to generate uuidv4 on first visit if no cookie present.
- Out: Linking device to user on signup (ISSUE-068).

### Acceptance Criteria (DoD)
- [ ] Given a request with no `vs_did` cookie, when `POST /api/v1/auth/device` is called with `{device_id_client: uuid}`, then a `devices` row is inserted and `Set-Cookie: vs_did=...` is returned.
- [ ] Given a request with the same `device_id_client`, when called again, then the existing row's `last_seen_at` is updated (no duplicate row).
- [ ] Given an invalid (non-UUID) `device_id_client`, when called, then 422.

### Implementation Notes
- Architecture §11.1 — `vs_did` HttpOnly cookie.
- data_model AP-06.

### Tests
- [ ] Upsert idempotency.
- [ ] Cookie attributes verified.

### Rollback
- Remove route + service.

---

## ISSUE-025: Manual setup — register Kakao OAuth app + Apple Sign-In service
- Track: platform
- UI: false
- Platform: web
- Manual: true
- PRD-Ref: FR-016, DEP-09, DEP-10
- Priority: P0
- Estimate: 1d
- Status: deferred
- Owner:
- Depends-On: none

> **Note (2026-05-28):** Deferred to Phase 2. v1 uses MockAuthAdapter (ISSUE-100) — a pre-seeded test user with dev JWT lets all auth-gated flows run end-to-end without OAuth provisioning. Real Kakao/Apple registration resumes when Phase 2 launches.

### Goal
Kakao Developers app registered + Apple Developer Sign-In Services enabled; credentials in secrets manager.

### Scope (In/Out)
- In: Register Kakao Developers app (web platform, OAuth redirect URI `https://staging.voicesaju.example/api/v1/auth/kakao/callback`), obtain REST API key + admin key, set scopes (account_email at minimum); enable Apple Sign-In, register Service ID + private key, configure redirect URI; store `KAKAO_REST_API_KEY`, `KAKAO_CLIENT_SECRET`, `APPLE_TEAM_ID`, `APPLE_KEY_ID`, `APPLE_PRIVATE_KEY_PEM`, `APPLE_SERVICE_ID` in Doppler/Fly secrets.
- Out: Backend integration code (ISSUE-026).

### Acceptance Criteria (DoD)
- [ ] Given the Kakao Developers app is created, when I visit the app dashboard, then OAuth + redirect URIs are listed.
- [ ] Given the Apple Service ID is registered, when I download the private key (`.p8`), then it's stored encrypted in secrets manager (NOT in repo).
- [ ] Given a developer runs `doppler secrets`, when listed, then 6+ Kakao/Apple variables are present.

### Implementation Notes
- DEP-09, DEP-10 in requirements.md.
- Documentation: `docs/runbook/auth_setup.md`.

### Tests
- [ ] Manual test: visit Kakao OAuth URL with the key → consent screen renders.

### Rollback
- Delete Kakao app + Apple Service ID from respective dashboards.

---

## ISSUE-026: Implement Kakao + Apple OAuth backend routes
- Track: backend
- UI: false
- Platform: web
- Manual: false
- PRD-Ref: FR-016, US-13
- Priority: P0
- Estimate: 1.5d
- Status: backlog
- Owner:
- Depends-On: ISSUE-008, ISSUE-013, ISSUE-024, ISSUE-100

### Goal
Kakao + Apple OAuth callbacks create/log in users, store session in Redis, set `vs_sess` cookie, and grant signup token on first creation.

### Scope (In/Out)
- In: `voicesaju/auth/routes.py` with `GET /auth/kakao/start`, `GET /auth/kakao/callback`, `GET /auth/apple/start`, `POST /auth/apple/callback`; `users.services.user_service.find_or_create_by_provider`; signup token granted via FR-017; `vs_sess` HttpOnly Secure SameSite=Lax cookie + Redis-backed session.
- Out: Toss bridge auth (ISSUE-046), frontend login screen (ISSUE-027).

### Acceptance Criteria (DoD)
- [ ] Given a Kakao OAuth callback with valid code, when called, then a User row is created (or existing one found by `kakao_sub`), a session is created in Redis, and `vs_sess` cookie is set.
- [ ] Given a new user signs up, when account creation completes, then exactly one `free_tokens` row with `kind='signup_grant'` exists (idempotent).
- [ ] Given two providers return the same `email_hash`, when both sign in, then both providers link to the same User row (architecture §11 dup-detection).
- [ ] Given an Apple `form_post` callback, when processed, then session is created same as Kakao.

### Implementation Notes
- Architecture §11.1, FR-016 AC.
- Use Authlib for OAuth; verify Apple JWT signature against Apple JWKS.

### Tests
- [ ] `tests/integration/auth/test_kakao_callback.py` (mocked Kakao userinfo).
- [ ] `tests/integration/auth/test_apple_callback.py` (mocked JWT).
- [ ] Dup-detection test.

### Rollback
- Disable routes; users cannot sign in via OAuth (Toss WebView still works).

---

## ISSUE-027: Implement /auth/login screen + signup prompt modal
- Track: frontend
- UI: true
- Platform: web
- Manual: false
- PRD-Ref: FR-016, US-13, US-02
- Priority: P0
- Estimate: 1d
- Status: backlog
- Owner:
- Depends-On: ISSUE-022, ISSUE-023, ISSUE-026

### Goal
`/auth/login` page (Screen 15) renders Kakao + Apple buttons; signup prompt modal (Screen 25) appears in non-member flows.

### Scope (In/Out)
- In: `app/auth/login/page.tsx`; `<SignupPromptModal>` component invoking the OAuth start endpoints; loading/error states per ux_spec Screen 15; Toss WebView channel shows single "토스로 계속하기" button (per ISSUE-023 runtime context).
- Out: OAuth backend (covered in ISSUE-026).

### Acceptance Criteria (DoD)
- [ ] Given a web user visits `/auth/login`, when the page loads, then "카카오로 시작하기" and "Apple로 시작하기" buttons appear.
- [ ] Given a Toss WebView user visits `/auth/login`, when the page loads, then only "토스로 계속하기" button appears.
- [ ] Given the user taps Kakao, when OAuth redirect happens, then the browser navigates to the Kakao consent URL.
- [ ] Given OAuth fails, when the user returns, then a banner "로그인이 취소됐어요" appears and buttons re-enable.

### Implementation Notes
- ux_spec Screen 15 + Screen 25.
- Korean copy from ux_spec §4.

### Tests
- [ ] Playwright e2e: login page renders both buttons; tap → redirect.
- [ ] Vitest snapshot for SignupPromptModal default/loading/error states.

### Rollback
- Remove `app/auth/login/page.tsx`.

---

# M2 — Saju Reading Flow

## ISSUE-028: Implement onboarding step screens (4-step card flow)
- Track: frontend
- UI: true
- Platform: web
- Manual: false
- PRD-Ref: FR-001, FR-002, US-01
- Priority: P0
- Estimate: 1.5d
- Status: backlog
- Owner:
- Depends-On: ISSUE-021, ISSUE-022

### Goal
`/onboarding/birth-date`, `/onboarding/birth-time`, `/onboarding/gender`, `/onboarding/name` screens are implemented with step indicator + back navigation + session-stored state.

### Scope (In/Out)
- In: 4 page routes; `<DatePicker>` (solar/lunar toggle), `<TimePicker>` ("모름" checkbox), `<GenderToggle>`, name input (≤ 10 chars); session storage via Zustand store; per-step validation (no future dates, no Feb 30).
- Out: Profile API call (ISSUE-029).

### Acceptance Criteria (DoD)
- [ ] Given I'm on Step 1, when I pick a valid solar date and tap "다음", then I'm routed to Step 2 and the date is persisted in Zustand.
- [ ] Given I'm on Step 2 and tap "시간은 모르겠어요", when I check, then time spinners visually disable and `birth_time_unknown=true` is set.
- [ ] Given I tap back on Step 2, when navigated, then I return to Step 1 with my date preserved.
- [ ] Given I enter a name > 10 chars, when I submit, then inline error "이름은 10자 이내로 적어줘" appears.
- [ ] Given keyboard navigation, when I tab through Step 1, then focus moves logically (date picker → toggle → 다음 button).

### Implementation Notes
- ux_spec Screens 2–5, Flow A steps 1–5.
- Use `react-day-picker` or native `<input type="date">` with Lunar toggle handled separately.

### Tests
- [ ] Playwright e2e: full onboarding flow.
- [ ] Vitest: each step's validation logic.
- [ ] axe-core a11y on each step.

### Rollback
- Remove onboarding routes.

---

## ISSUE-029: Implement POST /api/v1/profile endpoint
- Track: backend
- UI: false
- Platform: web
- Manual: false
- PRD-Ref: FR-001, FR-002, FR-027, FR-030
- Priority: P0
- Estimate: 1d
- Status: backlog
- Owner:
- Depends-On: ISSUE-010, ISSUE-011

### Goal
`POST /api/v1/profile` accepts onboarding data, encrypts birth fields, computes saju chart, and returns `{profile_id, chart_id, chart}`.

### Scope (In/Out)
- In: FastAPI route with Pydantic schema; calls `envelope.encrypt_field` for birth_dt; calls `saju.engine.compute_chart`; inserts Profile + SajuChart (using chart_hash cache); returns serialized chart.
- Out: PATCH (correction) — separate issue (ISSUE-071).

### Acceptance Criteria (DoD)
- [ ] Given a valid request with `birth_date`, `birth_time`, `gender`, `is_lunar`, when posted, then 201 with `{profile_id, chart_id, chart}` is returned.
- [ ] Given `birth_time=null`, when posted, then `birth_time_known=false` is stored and chart.hour is null.
- [ ] Given `is_lunar=true`, when posted, then the engine converts to solar before computing.
- [ ] Given two users submit identical inputs, when both run, then they share the same `chart_id` (cache hit via `chart_hash`).

### Implementation Notes
- Architecture §6.2, AP-10, AP-11.
- Idempotency-Key header optional; on duplicate, return existing profile.

### Tests
- [ ] `tests/integration/profile/test_create_profile.py` — happy path + lunar + time_unknown.
- [ ] Cache reuse test (two users same input → same chart_id).

### Rollback
- Remove route.

---

## ISSUE-030: Implement /reading/category screen (category selection)
- Track: frontend
- UI: true
- Platform: web
- Manual: false
- PRD-Ref: FR-004, US-03
- Priority: P0
- Estimate: 1d
- Status: backlog
- Owner:
- Depends-On: ISSUE-028, ISSUE-029

### Goal
`/reading/category` (Screen 6) shows 3 category cards (연애/직장/금전) with character greeting and entitlement status.

### Scope (In/Out)
- In: Page route; renders 3 `<CategoryCard>` instances; calls `POST /api/v1/profile` if non-member (with onboarding state from Zustand) before showing; entitlement banner ("무료 토큰 1회" or "단건 결제 필요" or "구독 중") from `GET /api/v1/me`.
- Out: Intro screen routing (ISSUE-032).

### Acceptance Criteria (DoD)
- [ ] Given onboarding is complete, when I land on `/reading/category`, then 3 cards display with category-specific colors.
- [ ] Given I tap a category card, when tapped, then I navigate to `/reading/intro/[category]` with the category passed via URL.
- [ ] Given I am a subscriber, when the screen loads, then the bottom bar shows "구독 중 — 이번 달 사주 X/1회 남음" (per ISSUE-040 entitlement).
- [ ] Given the user is a non-member, when the screen loads, then the greeting uses "거기 너" (no name).

### Implementation Notes
- ux_spec Screen 6, Flow A step 6 / Flow B step 1.
- Copy: ux_spec §4.

### Tests
- [ ] Playwright e2e: category card tap → routes to /intro/[category].

### Rollback
- Remove route.

---

## ISSUE-031: Implement GET /api/v1/reading/intro/{category}
- Track: backend
- UI: false
- Platform: web
- Manual: false
- PRD-Ref: FR-005
- Priority: P0
- Estimate: 0.5d
- Status: backlog
- Owner:
- Depends-On: ISSUE-017

### Goal
`GET /api/v1/reading/intro/{category}` returns the appropriate intro clip URL based on category + `birth_time_known`.

### Scope (In/Out)
- In: FastAPI route; queries `intro_audio_clips` by `(category, character_key='nuna', birth_time_known_variant)`; returns `{audio_url, subtitle, duration_ms}` where `audio_url` is a signed R2 URL.
- Out: Frontend player (ISSUE-032).

### Acceptance Criteria (DoD)
- [ ] Given `category=love` and user's profile has `birth_time_known=true`, when called, then the standard variant clip URL is returned.
- [ ] Given `birth_time_known=false`, when called, then the "시간을 모르면…" variant is returned.
- [ ] Given no clip exists for the category, when called, then 404 (fallback handled client-side per ux_spec).

### Implementation Notes
- Architecture §6.3, data_model AP-46.

### Tests
- [ ] Unit test for variant selection.

### Rollback
- Remove route.

---

## ISSUE-032: Implement /reading/intro player + skip
- Track: frontend
- UI: true
- Platform: web
- Manual: false
- PRD-Ref: FR-005, US-03
- Priority: P0
- Estimate: 1d
- Status: backlog
- Owner:
- Depends-On: ISSUE-030, ISSUE-031, ISSUE-101

### Goal
`/reading/intro/[category]` (Screen 7) plays the 15-sec pre-recorded clip with subtitle and skip button.

### Scope (In/Out)
- In: Page route; fetches intro URL; renders `<CharacterIllustration character="nuna">`, `<SubtitleBand>`, progress bar; "건너뛰기" → "결제하기" copy swap at 12s; auto-routes to `/reading/paywall` at end or skip.
- Out: Paywall (ISSUE-036).

### Acceptance Criteria (DoD)
- [ ] Given I land on `/reading/intro/love`, when audio loads, then it auto-plays within 200ms (after user-initiated nav, no autoplay block).
- [ ] Given the audio reaches 12 seconds, when the threshold is crossed, then the skip button copy changes to "결제하기".
- [ ] Given audio fails (network or codec), when detected, then a "탭해서 듣기" button + static subtitle render as fallback.
- [ ] Given the intro completes, when ended, then I'm auto-routed to `/reading/paywall`.

### Implementation Notes
- ux_spec Screen 7, Flow A step 6, Flow B step 2.

### Tests
- [ ] Playwright e2e: load, play, skip → paywall.

### Rollback
- Remove route.

---

## ISSUE-033: Implement chunked audio player (MSE + subtitle sync)
- Track: frontend
- UI: true
- Platform: web
- Manual: false
- PRD-Ref: NFR-002, NFR-015, FR-007
- Priority: P0
- Estimate: 1.5d
- Status: backlog
- Owner:
- Depends-On: ISSUE-021

### Goal
`<VoicePlayer>` component plays a chunked audio stream via MediaSource Extensions and renders synchronized subtitles within 500ms lag.

### Scope (In/Out)
- In: `web/src/lib/audio/chunked-player.ts` (MSE-based progressive playback consuming presigned URLs); `web/src/lib/audio/subtitle-sync.ts` (time-coded subtitle event handler); `<VoicePlayer>` React component with pause/play, replay, time display, aria-live subtitle log; fallback to subtitle-only on TTS failure.
- Out: SSE backend integration (covered in pipeline issue).

### Acceptance Criteria (DoD)
- [ ] Given the player receives `audio_ready` events with chunk URLs, when chunks arrive, then MSE appends them and playback continues seamlessly.
- [ ] Given a `subtitle` event with `{seq, text, audio_offset_ms}`, when received, then the subtitle band updates within 500ms of the audio reaching `audio_offset_ms` (NFR-015).
- [ ] Given the user taps pause, when paused, then audio stops and subtitle freezes at current position.
- [ ] Given the user taps replay, when tapped, then audio restarts from offset 0 and subtitle resets.
- [ ] Given the first audio chunk does not arrive within 5s, when timeout fires, then player switches to subtitle-only mode and shows a banner (FR-034).

### Implementation Notes
- Architecture §4.1, §8.2.
- MSE: `audio/mpeg` codec; chunks appended via `SourceBuffer.appendBuffer()`.
- Respect `prefers-reduced-motion`.

### Tests
- [ ] Vitest unit: subtitle sync lag ≤ 500ms with fixture events.
- [ ] Playwright integration: chunked playback with mock SSE.

### Rollback
- Remove player component.

---

## ISSUE-034: Implement Anthropic LLM client wrapper (streaming, retries, cost tracking)
- Track: backend
- UI: false
- Platform: web
- Manual: false
- PRD-Ref: NFR-007, NFR-011, FR-007, FR-010, FR-015
- Priority: P0
- Estimate: 1.5d
- Status: backlog
- Owner:
- Depends-On: ISSUE-001

### Goal
`voicesaju.llm.anthropic_client` provides `stream(...)` and `complete(...)` methods with timeouts, retries, and cost tracking persisted to `Reading.cost_*` fields.

### Scope (In/Out)
- In: `voicesaju/llm/anthropic_client.py` (async Anthropic SDK wrapper); `voicesaju/llm/router.py` (Sonnet 4.6 / Haiku 4.5 routing per architecture §7.1); `voicesaju/llm/cost_tracker.py` (token + KRW accounting); 10s timeout; exponential backoff retries (max 2); structured logging.
- Out: Guardrail integration (handled separately in pipeline).

### Acceptance Criteria (DoD)
- [ ] Given a `stream_saju_main(chart, category, user)` call, when invoked, then it uses Sonnet 4.6 and yields tokens as they arrive.
- [ ] Given a `stream_followup(...)` call, when invoked, then it uses Haiku 4.5.
- [ ] Given Anthropic returns a 5xx, when called, then the client retries up to 2× with exponential backoff.
- [ ] Given the call times out > 10s, when timeout fires, then a `LLMTimeoutError` is raised.
- [ ] Given a successful call, when complete, then cost_tracker records `input_tokens`, `output_tokens`, `total_krw`.

### Implementation Notes
- Architecture §7.
- Mock the SDK in tests (no live API hits in CI).
- ANTHROPIC_API_KEY from secrets manager.

### Tests
- [ ] `tests/unit/llm/test_router.py` — model selection.
- [ ] `tests/unit/llm/test_cost_tracker.py` — token math.
- [ ] `tests/integration/llm/test_streaming_mock.py` — mocked stream.

### Rollback
- Remove module; pipeline cannot generate readings.

---

## ISSUE-035: Manual setup — obtain Anthropic API key + add to secrets
- Track: platform
- UI: false
- Platform: web
- Manual: true
- PRD-Ref: NFR-007, A-10
- Priority: P0
- Estimate: 0.5d
- Status: deferred
- Owner:
- Depends-On: none

> **Note (2026-05-28):** Deferred to Phase 2. v1 uses MockLLMAdapter (ISSUE-101) — fixture-based saju/tarot responses with streaming simulation let the full reading pipeline run without an Anthropic key. Real Anthropic provisioning resumes when Phase 2 launches.

### Goal
Anthropic API key with sufficient rate limits is provisioned and stored in secrets manager.

### Scope (In/Out)
- In: Sign up at console.anthropic.com, generate API key with model access for Claude Sonnet 4.6 + Haiku 4.5, store as `ANTHROPIC_API_KEY` in Doppler/Fly secrets, request rate-limit increase if projected load > default.
- Out: Backend integration (ISSUE-034 — can proceed with mocks in parallel).

### Acceptance Criteria (DoD)
- [ ] Given the API key is provisioned, when `curl https://api.anthropic.com/v1/messages -H "x-api-key: $ANTHROPIC_API_KEY" ...` is run, then a valid response is returned.
- [ ] Given the secrets manager is configured, when developers fetch secrets, then `ANTHROPIC_API_KEY` is present.
- [ ] Given projected peak load is calculated (≤ 100 concurrent readings), when rate limit headroom is checked against Anthropic's tier, then capacity is sufficient or a tier upgrade request is filed.

### Implementation Notes
- A-10 in requirements.md.

### Tests
- [ ] Manual curl test passes.

### Rollback
- Revoke API key.

---

## ISSUE-036: Manual setup — obtain Supertone TTS API access + voice IDs
- Track: platform
- UI: false
- Platform: web
- Manual: true
- PRD-Ref: DEP-01, FR-007, NFR-002, NFR-007
- Priority: P0
- Estimate: 1d
- Status: deferred
- Owner:
- Depends-On: none

> **Note (2026-05-28):** Deferred to Phase 2. v1 uses MockTTSAdapter (ISSUE-102) — pre-baked silent MP3 chunks streamed at realistic rate let the audio playback pipeline + UI player run without Supertone access. Real Supertone contract resumes when Phase 2 launches.

### Goal
Supertone API contract finalized; 시니컬 누님 + 노인 도사 voice IDs assigned; pricing tier confirmed within NFR-007 ceiling.

### Scope (In/Out)
- In: Business contact with Supertone, contract signing, voice ID assignment (recorded in `character_voices` seed migration update), pricing tier confirmation; credentials in secrets manager (`SUPERTONE_API_KEY`, `SUPERTONE_VOICE_ID_NUNA`, `SUPERTONE_VOICE_ID_DOSA`).
- Out: Backend client integration (ISSUE-037 — can use mock voices until this lands).

### Acceptance Criteria (DoD)
- [ ] Given the contract is signed, when reviewed, then the per-character per-second pricing is documented and projected to land below ~700 KRW per session (NFR-007 budget per architecture §14.3).
- [ ] Given the voice IDs are assigned, when migration `0002_supertone_voice_ids.py` is applied, then `character_voices.supertone_voice_id` is updated for both characters.
- [ ] Given `SUPERTONE_API_KEY` is in secrets, when accessed by the backend, then test synthesis call returns audio.

### Implementation Notes
- DEP-01.
- Project still proceeds with mocked TTS until contract lands.

### Tests
- [ ] Manual test synthesis call returns audio.

### Rollback
- Cancel contract; fall back to alternative TTS provider (architecture §15 #4).

---

## ISSUE-037: Implement Supertone TTS streaming client
- Track: backend
- UI: false
- Platform: web
- Manual: false
- PRD-Ref: NFR-002, FR-007, FR-034
- Priority: P0
- Estimate: 1.5d
- Status: backlog
- Owner:
- Depends-On: ISSUE-017, ISSUE-034

### Goal
`voicesaju.tts.supertone_client.synthesize_stream(text_stream, voice_id)` yields `AudioChunk` objects from Supertone API.

### Scope (In/Out)
- In: Async HTTPX client; sentence-level chunking (≤120 chars or punctuation boundary); concurrency cap (≤4 in-flight); first-chunk timeout 5s → raises `TTSFirstChunkTimeout`; mid-stream sentence timeout 3s; rate-limit (429) handling with backoff.
- Out: R2 upload (ISSUE-038), pipeline integration (ISSUE-039).

### Acceptance Criteria (DoD)
- [ ] Given a stream of sentences, when synthesized, then each `AudioChunk` is yielded as soon as Supertone returns it.
- [ ] Given first chunk does not arrive within 5s, when timeout fires, then `TTSFirstChunkTimeout` is raised (handled upstream as FR-034).
- [ ] Given Supertone returns 429, when called, then the client backs off exponentially; after > 8s of breach, falls through to text-only fallback signal.
- [ ] Given a voice_id is provided, when the request is made, then it's sent as the voice parameter to Supertone.

### Implementation Notes
- Architecture §8.2, §8.3.
- Use `httpx.AsyncClient` with `httpx-stream`.

### Tests
- [ ] `tests/unit/tts/test_supertone_chunking.py` — sentence boundaries.
- [ ] `tests/integration/tts/test_streaming_mock.py` — mock SSE.
- [ ] Timeout behavior tested.

### Rollback
- Remove module; pipeline falls back to text-only entirely.

---

## ISSUE-038: Implement R2 storage client + audio finalize worker
- Track: backend
- UI: false
- Platform: web
- Manual: false
- PRD-Ref: FR-028
- Priority: P0
- Estimate: 1d
- Status: backlog
- Owner:
- Depends-On: ISSUE-005, ISSUE-015

### Goal
R2 client uploads audio chunks + stitched mp3; arq worker `finalize_audio` stitches per-sentence chunks into a single `main.mp3` after reading completes.

### Scope (In/Out)
- In: `voicesaju/storage/r2_client.py` (boto3 S3 client pointed at R2); `voicesaju/jobs/worker.py` (arq entrypoint); `voicesaju/jobs/audio_finalize.py` (stitches chunks via ffmpeg-python concat); persisted to `audio/readings/{reading_id}/main.mp3`; updates `reading_audio` row.
- Out: OG image worker (ISSUE-058).

### Acceptance Criteria (DoD)
- [ ] Given multiple chunk files exist in R2 under `audio/readings/{id}/chunks/`, when `finalize_audio(reading_id)` runs, then a single `main.mp3` is uploaded and chunk files are deleted.
- [ ] Given the finalize completes, when checked, then `reading_audio` row has `r2_key`, `duration_ms`, `content_hash`, `file_size_bytes` set.
- [ ] Given the arq worker starts, when running, then it picks up queued `finalize_audio` jobs from Redis.

### Implementation Notes
- Architecture §8.4.
- ffmpeg must be installed in container image.

### Tests
- [ ] Integration test with R2 testcontainer (MinIO) or localstack.
- [ ] arq worker smoke test.

### Rollback
- Disable arq worker; replays will be unavailable until reprocessed.

---

## ISSUE-039: Implement reading pipeline orchestration (POST /api/v1/reading + SSE)
- Track: backend
- UI: false
- Platform: web
- Manual: false
- PRD-Ref: FR-007, NFR-001, NFR-011
- Priority: P0
- Estimate: 1.5d
- Status: backlog
- Owner:
- Depends-On: ISSUE-011, ISSUE-020, ISSUE-034, ISSUE-037, ISSUE-038, ISSUE-040

### Goal
`POST /api/v1/reading` validates entitlement, creates Reading row, and returns `{reading_id, sse_url}`. `GET /api/v1/reading/{id}/stream` orchestrates `chart_lookup → LLM stream → guardrail → TTS chunks → R2 upload → SSE emit`.

### Scope (In/Out)
- In: `voicesaju/reading/routes.py`, `voicesaju/reading/pipeline.py`; idempotent via `Idempotency-Key`; SSE events `subtitle`, `audio_ready`, `end`, `error`; OpenTelemetry spans per stage; 3s budget enforcement (alert if violated).
- Out: Follow-up endpoint (ISSUE-041), payment integration (ISSUE-044).

### Acceptance Criteria (DoD)
- [ ] Given a valid entitlement, when `POST /api/v1/reading {category, entitlement}` is called, then 201 with `{reading_id, sse_url, audio_stream_url}` is returned.
- [ ] Given the same Idempotency-Key is sent twice, when both arrive, then only one Reading row exists.
- [ ] Given the SSE stream connects, when running, then `subtitle` and `audio_ready` events stream until `end`.
- [ ] Given the first audio chunk reaches the client within 3 seconds of payment confirm (instrumented), when measured at p95, then NFR-001 holds.
- [ ] Given an entitlement is missing, when `POST /api/v1/reading` is called, then 402 with `error.code='payment_required'`.

### Implementation Notes
- Architecture §6.3, §7.1, §8.2.
- Each pipeline step has its own OTel span.

### Tests
- [ ] Integration test with mocked LLM + TTS; assert SSE event order.
- [ ] Idempotency test.
- [ ] 402 response test.

### Rollback
- Disable routes; reading flow halts.

---

## ISSUE-040: Implement entitlement check service
- Track: backend
- UI: false
- Platform: web
- Manual: false
- PRD-Ref: FR-006, FR-014, FR-022
- Priority: P0
- Estimate: 1d
- Status: backlog
- Owner:
- Depends-On: ISSUE-013, ISSUE-014

### Goal
`entitlement.service.check_entitlement(user_or_device, kind)` returns whether the user can access a reading (free_token / payment / subscription).

### Scope (In/Out)
- In: `voicesaju/entitlement/service.py`; queries FreeToken / Subscription / Payment; `GET /api/v1/me` returns entitlement summary; integrated into reading + tarot routes.
- Out: Toss Payments integration (ISSUE-043+).

### Acceptance Criteria (DoD)
- [ ] Given a user with an unconsumed signup_grant token, when `check_entitlement(user, kind='reading')` is called, then `{has_token: true, token_id: ...}` is returned.
- [ ] Given a subscriber with `monthly_saju_remaining=1`, when checked for reading, then `{has_subscription_credit: true, subscription_id: ...}`.
- [ ] Given a subscriber with `monthly_saju_remaining=0`, when checked, then `{has_subscription_credit: false}`.
- [ ] Given a non-member with no trial token, when checked, then `{has_anything: false, requires_payment: true}`.

### Implementation Notes
- AP-16, AP-17, AP-20, AP-21.

### Tests
- [ ] Unit tests for each entitlement permutation.

### Rollback
- Remove service; paywall defaults to "payment required" for everyone.

---

## ISSUE-041: Implement follow-up question endpoints (suggest + answer)
- Track: backend
- UI: false
- Platform: web
- Manual: false
- PRD-Ref: FR-009, FR-010, NFR-004
- Priority: P0
- Estimate: 1.5d
- Status: backlog
- Owner:
- Depends-On: ISSUE-034, ISSUE-037, ISSUE-039

### Goal
`GET /api/v1/reading/{id}/followups` returns 3 LLM-generated questions (with hardcoded fallback). `POST /api/v1/reading/{id}/followups/{index}` streams the answer.

### Scope (In/Out)
- In: Routes; uses Haiku 4.5 (JSON mode) for question suggestion; per-slot SSE stream for answer; persists `reading_followups` row (question_text, answer_text, audio_r2_key); button disable enforced server-side (cannot tap same slot twice).
- Out: Frontend follow-up UI (ISSUE-042).

### Acceptance Criteria (DoD)
- [ ] Given a completed main reading, when `GET .../followups` is called, then 3 questions are returned within 2 seconds.
- [ ] Given LLM fails to generate questions, when called, then 3 hardcoded fallback questions for the category are returned (FR-009 AC).
- [ ] Given `POST .../followups/0` is called, when streamed, then first audio chunk reaches client within 2 seconds (NFR-004).
- [ ] Given `POST .../followups/0` is called twice, when the second arrives, then 409 conflict (slot already consumed).
- [ ] Given answer duration is < 25s or > 45s, when measured, then a warning is logged (FR-010 AC).

### Implementation Notes
- Architecture §6.3, §7.1.
- Reuse the same SSE pipeline as main reading.

### Tests
- [ ] Integration: full reading + 3 followups happy path.
- [ ] Fallback question test.
- [ ] Slot-conflict test.

### Rollback
- Disable routes; followups unavailable.

---

## ISSUE-042: Implement /reading/play screen (main reading playback)
- Track: frontend
- UI: true
- Platform: web
- Manual: false
- PRD-Ref: FR-007, FR-008, FR-011, US-03, US-05
- Priority: P0
- Estimate: 1.5d
- Status: backlog
- Owner:
- Depends-On: ISSUE-033, ISSUE-039

### Goal
`/reading/play` (Screen 9) connects to SSE, renders `<VoicePlayer>` + `<SajuChart>` + `<CharacterIllustration>`, and handles all 5 states from ux_spec.

### Scope (In/Out)
- In: Page route; SSE EventSource subscription; chart sidebar (collapsible on mobile); one-line 명식 summary; loading state ("별기운을 모으는 중…"); error state ("별기운이 잠시 약하네…"); network-drop handling per FR-035.
- Out: Follow-up UI (ISSUE-045).

### Acceptance Criteria (DoD)
- [ ] Given I land on `/reading/play` with a valid reading_id, when the SSE connects, then loading state shows ≤3s then audio starts.
- [ ] Given the audio is playing, when I tap pause, then audio stops and subtitle freezes (NFR-015).
- [ ] Given I tap the 명식 chart cell, when tapped, then a tooltip with 오행 + 십신 appears.
- [ ] Given network drops mid-playback, when detected within 3s, then a "네트워크 연결이 끊겼습니다" banner appears and audio pauses.
- [ ] Given network reconnects within 60s, when reconnected, then playback resumes from last position.
- [ ] Given LLM fails, when error event arrives, then full-screen "별기운이 잠시 약하네…" + 다시 시도 / 마이페이지로 buttons render.

### Implementation Notes
- ux_spec Screen 9, Flow A step 8/9, Flow B step 6/7.

### Tests
- [ ] Playwright e2e: SSE happy path.
- [ ] Network-drop simulation test.
- [ ] axe-core: aria-live subtitle region.

### Rollback
- Remove route.

---

## ISSUE-043: Manual setup — register Toss Payments merchant account + webhook URL
- Track: platform
- UI: false
- Platform: web
- Manual: true
- PRD-Ref: FR-021, FR-022, DEP-03
- Priority: P0
- Estimate: 1d
- Status: deferred
- Owner:
- Depends-On: ISSUE-004

> **Note (2026-05-28):** Deferred to Phase 2. v1 uses MockPaymentAdapter (ISSUE-099) — fake checkout sessions with auto-fired success webhook (3s delay) let the full payment + entitlement flow run without a Toss merchant account. Real Toss provisioning resumes when Phase 2 launches.

### Goal
Toss Payments merchant account is approved; webhook URL is registered; test credentials are in secrets manager.

### Scope (In/Out)
- In: Apply for Toss Payments merchant (통신판매업 신고 prerequisite); register webhook URL `https://staging-api.voicesaju.example/api/v1/payments/webhook`; obtain test + live `client_key`, `secret_key`; store as `TOSS_CLIENT_KEY`, `TOSS_SECRET_KEY`, `TOSS_WEBHOOK_SECRET`.
- Out: Backend client integration (ISSUE-044).

### Acceptance Criteria (DoD)
- [ ] Given the merchant account is approved, when I log into the Toss Payments dashboard, then KakaoPay + TossPay payment methods are enabled.
- [ ] Given the webhook URL is registered, when a test payment fires, then the staging endpoint receives a signed payload.
- [ ] Given the secrets manager is configured, when listed, then 3 Toss variables are present.

### Implementation Notes
- DEP-03.

### Tests
- [ ] Manual test payment via Toss test sandbox returns webhook to staging.

### Rollback
- Cancel merchant account.

---

## ISSUE-044: Implement Toss Payments client + checkout endpoint
- Track: backend
- UI: false
- Platform: web
- Manual: false
- PRD-Ref: FR-021, US-09, US-10
- Priority: P0
- Estimate: 1.5d
- Status: backlog
- Owner:
- Depends-On: ISSUE-014, ISSUE-040, ISSUE-099

### Goal
`POST /api/v1/payments/checkout` creates a pending Payment + returns `{toss_order_id, amount_krw, success_url, fail_url}`. `POST /api/v1/payments/confirm` is the redirect endpoint that finalizes the payment.

### Scope (In/Out)
- In: `voicesaju/payment/toss_client.py` (httpx wrapper); `voicesaju/payment/routes.py`; client-generated idempotent `toss_order_id`; price config (`PRICE_SINGLE_KRW`, `PRICE_SUBSCRIPTION_KRW`) from env per A-01; confirm endpoint verifies amount + status with Toss API.
- Out: Webhook handler (ISSUE-045), refund (ISSUE-076).

### Acceptance Criteria (DoD)
- [ ] Given a `POST /api/v1/payments/checkout {kind:"single", method:"tosspay"}` request, when called, then a `payments` row is inserted with `status='pending'` and the response includes `toss_order_id`.
- [ ] Given the same Idempotency-Key is sent twice, when both arrive, then only one pending Payment row exists.
- [ ] Given `POST /api/v1/payments/confirm` is called after Toss redirect, when verified against Toss server API, then `payments.status='paid'` and `paid_at` is set.
- [ ] Given the amount in confirm differs from the stored row, when checked, then 400 (fraud guard).

### Implementation Notes
- Architecture §6.5, §11.5.
- TOSS API: `https://api.tosspayments.com/v1/payments/confirm`.

### Tests
- [ ] Integration with Toss sandbox (or mocked Toss responses).
- [ ] Fraud guard test (amount mismatch).

### Rollback
- Disable routes; users cannot pay.

---

## ISSUE-045: Implement Toss Payments webhook handler + signature verification
- Track: backend
- UI: false
- Platform: web
- Manual: false
- PRD-Ref: FR-021, FR-022
- Priority: P0
- Estimate: 1d
- Status: backlog
- Owner:
- Depends-On: ISSUE-044

### Goal
`POST /api/v1/payments/webhook` verifies HMAC signature from Toss, upserts Payment + Subscription rows idempotently.

### Scope (In/Out)
- In: Webhook route; HMAC-SHA256 signature check using `TOSS_WEBHOOK_SECRET`; idempotency on `toss_payment_key`; handles `PAYMENT_DONE`, `PAYMENT_FAILED`, `SUBSCRIPTION_RENEWED`, `SUBSCRIPTION_CANCELED`, `BILLING_FAILED` events.
- Out: Refund processing (ISSUE-076).

### Acceptance Criteria (DoD)
- [ ] Given a valid signed webhook with `PAYMENT_DONE`, when called, then `payments.status='paid'`, `paid_at` set, entitlement granted.
- [ ] Given an invalid signature, when called, then 401 (no DB writes).
- [ ] Given the same webhook is delivered twice, when both arrive, then only one update occurs (idempotent on `toss_payment_key`).
- [ ] Given a `SUBSCRIPTION_RENEWED` event, when processed, then `subscriptions.current_period_start/end` are advanced and `monthly_saju_remaining=1` reset.

### Implementation Notes
- Architecture §6.5, §11.4 (A08 OWASP).

### Tests
- [ ] Signature validation test.
- [ ] Idempotency test on duplicate webhook.

### Rollback
- Disable webhook route; manual reconciliation only.

---

## ISSUE-046: Implement Toss WebView bridge auth + payment routing
- Track: backend
- UI: false
- Platform: web
- Manual: false
- PRD-Ref: FR-016, FR-024, US-14
- Priority: P0
- Estimate: 1d
- Status: backlog
- Owner:
- Depends-On: ISSUE-026, ISSUE-044

### Goal
`POST /api/v1/auth/toss-bridge` verifies a Toss-signed token + maps to internal User. Paywall returns Toss-only payment options when context is `toss_webview`.

### Scope (In/Out)
- In: `voicesaju/auth/toss_bridge.py` (token verification: signature + audience + expiry); creates/links User row with `toss_id`; `voicesaju/security/webview_guard.py` (origin allowlist for SameSite=None cookies); paywall service returns method=`tosspay` only when channel is `toss_webview`.
- Out: Toss policy approval (DEP-02 — manual setup tracked separately).

### Acceptance Criteria (DoD)
- [ ] Given a valid Toss bridge token, when `POST /auth/toss-bridge` is called, then a User is found or created by `toss_id` and a session is issued with SameSite=None Secure cookie (when origin matches allowlist).
- [ ] Given an invalid signature, when called, then 401.
- [ ] Given the WebView origin is not in the allowlist, when called, then 403.
- [ ] Given context is `toss_webview`, when `GET /api/v1/reading/paywall` returns options, then only `method=tosspay` is listed.

### Implementation Notes
- Architecture §11.1, DEP-02 (policy approval is a separate dependency).
- This issue scaffolds against the documented Toss bridge spec; live integration testing depends on DEP-02.

### Tests
- [ ] Token verification unit tests (mocked signature).
- [ ] Origin guard tests.

### Rollback
- Disable Toss bridge route; Toss WebView users see an error.

---

# M3 — Daily Tarot

## ISSUE-047: Implement deterministic tarot seed (FR-013)
- Track: backend
- UI: false
- Platform: web
- Manual: false
- PRD-Ref: FR-013
- Priority: P0
- Estimate: 0.5d
- Status: backlog
- Owner:
- Depends-On: ISSUE-016

### Goal
`tarot.seed.daily_card_index(date_kst, subject_id)` returns a deterministic integer 0–21.

### Scope (In/Out)
- In: `voicesaju/tarot/seed.py` per architecture §10 exact implementation.
- Out: API routes.

### Acceptance Criteria (DoD)
- [ ] Given the same `date_kst` and `subject_id`, when called 100 times, then the result is identical every time.
- [ ] Given different `subject_id` values for the same date, when called, then a distribution test over 10,000 subjects shows roughly uniform spread (chi-squared at p > 0.05).
- [ ] Given the result, when checked, then it's always in `[0, 21]`.

### Implementation Notes
- Architecture §10.

### Tests
- [ ] Determinism: same input → same output (100 iterations).
- [ ] Distribution chi-squared test.

### Rollback
- Remove module.

---

## ISSUE-048: Implement tarot quota service (FR-014, weekly window)
- Track: backend
- UI: false
- Platform: web
- Manual: false
- PRD-Ref: FR-014
- Priority: P0
- Estimate: 1d
- Status: backlog
- Owner:
- Depends-On: ISSUE-016, ISSUE-040

### Goal
`tarot.quota.check_weekly_free(user_or_device)` returns remaining free draws this calendar week (Mon 00:00 KST → Sun 23:59 KST).

### Scope (In/Out)
- In: `voicesaju/tarot/quota.py`; Redis-backed counter with weekly reset; fallback DB scan if Redis miss (AP-33); subscriber bypass (always returns unlimited).
- Out: Paywall routing (ISSUE-050).

### Acceptance Criteria (DoD)
- [ ] Given a user has not drawn this week, when called, then returns `{remaining: 1}`.
- [ ] Given the user has drawn once this week, when called, then returns `{remaining: 0}`.
- [ ] Given the time crosses Monday 00:00 KST, when called, then the counter resets to 1.
- [ ] Given an active subscriber, when called, then `{remaining: unlimited}`.

### Implementation Notes
- AP-33, architecture §10.
- Redis key: `tarot:quota:{subject_id}:{iso_week_kst}`.

### Tests
- [ ] Quota reset test (mock clock).
- [ ] Subscriber bypass test.

### Rollback
- Default to "unlimited" (lossy revenue).

---

## ISSUE-049: Implement tarot pipeline (GET /tarot/today + POST /tarot/flip)
- Track: backend
- UI: false
- Platform: web
- Manual: false
- PRD-Ref: FR-012, FR-015, NFR-003
- Priority: P0
- Estimate: 1.5d
- Status: done
- Owner:
- Depends-On: ISSUE-034, ISSUE-037, ISSUE-038, ISSUE-047, ISSUE-048
- Branch: issue/049-tarot-pipeline
- GH-Issue: https://github.com/pillip/voicesaju/issues/79
- PR: https://github.com/pillip/voicesaju/pull/80

### Goal
`GET /api/v1/tarot/today` returns today's card metadata + quota; `POST /api/v1/tarot/today/flip` creates `tarot_draws` row + streams Haiku 4.5 reading via SSE.

### Scope (In/Out)
- In: Routes; idempotent on `(user_or_device, date_kst)`; SSE stream reusing the pipeline pattern from ISSUE-039; subscriber bypass; persists transcript + audio key.
- Out: Tarot paywall (ISSUE-050), frontend (ISSUE-051+).

### Acceptance Criteria (DoD)
- [ ] Given `GET /tarot/today` is called, when responded, then `{card_index, card_name, card_art_url, free_remaining, requires_payment}` is returned within 100ms.
- [ ] Given the same user calls `POST /tarot/today/flip` twice the same KST day, when both arrive, then only one row is created (unique constraint).
- [ ] Given the quota is exhausted, when `POST /tarot/today/flip` is called, then 402 with `error.code='payment_required'`.
- [ ] Given the SSE stream starts, when running, then first audio chunk arrives ≤ 2 seconds (NFR-003).

### Implementation Notes
- Architecture §6.4, §10.

### Tests
- [ ] Integration: full daily tarot flow.
- [ ] Idempotency on (user, date_kst).

### Rollback
- Disable routes.

---

## ISSUE-050: Implement /tarot + /tarot/paywall screens
- Track: frontend
- UI: true
- Platform: web
- Manual: false
- PRD-Ref: FR-012, FR-014, US-06, US-07
- Priority: P0
- Estimate: 1.5d
- Status: done
- Owner:
- Depends-On: ISSUE-022, ISSUE-049
- Branch: issue-050-tarot-screens
- GH-Issue: https://github.com/pillip/voicesaju/issues/81
- PR: https://github.com/pillip/voicesaju/pull/82

### Goal
`/tarot` (Screen 12) shows face-down card + quota banner + flip interaction. `/tarot/paywall` (Screen 24) routes quota-exhausted users to single/subscription options.

### Scope (In/Out)
- In: Page routes; `<TarotCard>` component (face-down/face-up with 300–600ms flip animation per FR-012); `<TarotQuotaBanner>`; quota check via `GET /tarot/today`; on quota=0 → routes to `/tarot/paywall`.
- Out: Tarot player (ISSUE-051).

### Acceptance Criteria (DoD)
- [ ] Given I open `/tarot` with quota=1, when loaded, then face-down card + "이번 주 무료 1회 남음" banner display.
- [ ] Given I tap the card, when tapped, then flip animation (300–600ms) plays and the card reveals.
- [ ] Given quota=0 and I tap the card, when tapped, then I'm routed to `/tarot/paywall` (no flip).
- [ ] Given `prefers-reduced-motion`, when I tap, then flip is instant (no animation).
- [ ] Given an already-flipped state (returned visit same day), when loaded, then face-up card + "다시 듣기" button shown.

### Implementation Notes
- ux_spec Screen 12, Screen 24, Flow C.

### Tests
- [ ] Playwright e2e: face-down → flip → reveal.
- [ ] Reduced-motion test.
- [ ] Quota-exhausted paywall routing.

### Rollback
- Remove routes.

---

## ISSUE-051: Implement /tarot/play screen (tarot voice playback)
- Track: frontend
- UI: true
- Platform: web
- Manual: false
- PRD-Ref: FR-015, US-06
- Priority: P0
- Estimate: 1d
- Status: backlog
- Owner:
- Depends-On: ISSUE-033, ISSUE-050

### Goal
`/tarot/play` (Screen 13) plays the 노인 도사 30–40s reading using `<VoicePlayer>` + card art + subtitle.

### Scope (In/Out)
- In: Page route; SSE connection to `POST /tarot/today/flip` result; `<CharacterIllustration character="dosa">`; auto-route to `/tarot/end` on audio completion.
- Out: Quote card on end (ISSUE-057).

### Acceptance Criteria (DoD)
- [ ] Given I land on `/tarot/play`, when SSE connects, then first audio chunk arrives ≤ 2s of flip end (NFR-003).
- [ ] Given audio completes, when ended, then auto-routes to `/tarot/end`.
- [ ] Given TTS fails, when detected, then subtitle-only fallback renders (FR-034).

### Implementation Notes
- ux_spec Screen 13.

### Tests
- [ ] Playwright e2e: flip → play → end routing.

### Rollback
- Remove route.

---

## ISSUE-052: Implement subscriber tarot bypass (no quota)
- Track: backend
- UI: false
- Platform: web
- Manual: false
- PRD-Ref: FR-022 (subscriber benefit)
- Priority: P1
- Estimate: 0.5d
- Status: done
- Owner:
- Depends-On: ISSUE-014, ISSUE-048, ISSUE-049
- Branch: issue-052-tarot-subscriber-bypass
- GH-Issue: #83
- PR: #85 (merged: b92c2f4)

### Goal
Active subscribers have unlimited tarot draws per day (only one card per day per FR-013, but no weekly cap).

### Scope (In/Out)
- In: `tarot.quota.check_weekly_free` already supports subscriber bypass; this issue verifies end-to-end + frontend UI banner change.
- Out: New subscriptions (ISSUE-066).

### Acceptance Criteria (DoD)
- [ ] Given an active subscriber visits `/tarot`, when the screen loads, then the quota banner shows "구독 중" (no "N회 남음").
- [ ] Given an active subscriber taps the card after their first draw of the day, when tapped, then they see "오늘의 카드는 이미 뒤집었어요" + "다시 듣기" (per FR-013 same-card-per-day, not a quota block).

### Implementation Notes
- ux_spec Flow C edge case.

### Tests
- [ ] Subscriber path integration test.

### Rollback
- Subscribers see free quota banner instead (degraded UX, no data loss).

---

## ISSUE-053: Implement KST midnight auto-refresh on /tarot
- Track: frontend
- UI: true
- Platform: web
- Manual: false
- PRD-Ref: FR-013
- Priority: P2
- Estimate: 0.5d
- Status: done
- Owner:
- Depends-On: ISSUE-050
- Branch: issue-053-tarot-kst-refresh
- GH-Issue: #84
- PR: #86 (merged: d2588ab)

### Goal
At KST midnight, the `/tarot` page either auto-refreshes or shows a "새로운 카드가 준비됐어요" banner.

### Scope (In/Out)
- In: `useEffect` timer that computes ms until next KST midnight; on cross, calls `router.refresh()` + shows toast.
- Out: Backend changes.

### Acceptance Criteria (DoD)
- [ ] Given the user has `/tarot` open at 23:59:50 KST, when the clock crosses 00:00:00, then a banner "새로운 카드가 준비됐어요" appears and the page reloads.
- [ ] Given the user is in a non-KST timezone, when the timer fires, then it still triggers at KST midnight (computed via `zonedTimeToUtc`).

### Implementation Notes
- ux_spec Flow C edge case.
- Use `date-fns-tz`.

### Tests
- [ ] Mock-clock test.

### Rollback
- Remove timer; users see stale card until manual refresh.

---

## ISSUE-054: Implement /tarot/end screen (tarot quote card)
- Track: frontend
- UI: true
- Platform: web
- Manual: false
- PRD-Ref: FR-018, US-08
- Priority: P1
- Estimate: 1d
- Status: backlog
- Owner:
- Depends-On: ISSUE-051, ISSUE-058

### Goal
`/tarot/end` (Screen 14) shows the purple-variant quote card with share CTAs.

### Scope (In/Out)
- In: Page route; renders `<QuoteCardPreview>` (purple variant) + `<ShareButtonRow>`; secondary CTA "내일 또 봐" → `/`; signup modal auto-opens for non-members.
- Out: Quote card backend (ISSUE-056+).

### Acceptance Criteria (DoD)
- [ ] Given the tarot session ends, when I land on `/tarot/end`, then the quote card preview renders within 3s.
- [ ] Given the user is a non-member, when the screen loads, then signup modal opens after 1s.
- [ ] Given the card background is purple variant (#C4B5FD or equivalent), when rendered, then it matches the design token.

### Implementation Notes
- ux_spec Screen 14.

### Tests
- [ ] Playwright e2e.

### Rollback
- Remove route; users return to `/` from `/tarot/play`.

---

## ISSUE-055: Implement tarot card art asset pipeline (placeholder + production-ready)
- Track: content
- UI: false
- Platform: web
- Manual: false
- PRD-Ref: DEP-06
- Priority: P1
- Estimate: 1d
- Status: backlog
- Owner:
- Depends-On: ISSUE-016

### Goal
22 placeholder tarot card art files + 1 back art are uploaded to R2 at `static/tarot/cards/{slug}.png` and `static/tarot/back.png`.

### Scope (In/Out)
- In: 22 placeholder PNG illustrations (can be temporary art until DEP-06 IP delivery); upload script using R2 client; update `tarot_cards.art_r2_key` if paths change.
- Out: Final production illustrations (DEP-06, content team).

### Acceptance Criteria (DoD)
- [ ] Given the upload runs, when verified, then 23 files exist in R2 under `static/tarot/`.
- [ ] Given the frontend fetches a card art URL, when loaded, then the image renders (no 404).
- [ ] Given DEP-06 final art arrives, when re-uploaded with same R2 keys, then versioning logic invalidates CDN cache.

### Implementation Notes
- DEP-06.

### Tests
- [ ] Manual smoke: open `/tarot`, verify all 22 indices load art.

### Rollback
- Use category-color silhouette as ultimate fallback (per ux_spec Screen 12 error state).

---

# M4 — Quote Card + Sharing

## ISSUE-056: Implement quote line extraction (Haiku 4.5)
- Track: backend
- UI: false
- Platform: web
- Manual: false
- PRD-Ref: FR-018
- Priority: P1
- Estimate: 1d
- Status: backlog
- Owner:
- Depends-On: ISSUE-034

### Goal
`content.quote_card.extract_quote(reading_text, character_key) -> str` returns a spicy quote ≤ 40 chars; falls back to category-specific hardcoded quote on LLM failure.

### Scope (In/Out)
- In: `voicesaju/content/quote_card.py`; Haiku 4.5 JSON-mode call with strict 40-char output budget; 3 hardcoded fallback quotes per category (love/work/money/tarot).
- Out: OG image bake worker (ISSUE-058).

### Acceptance Criteria (DoD)
- [ ] Given a reading text input, when called, then a quote ≤ 40 Korean characters is returned.
- [ ] Given the LLM returns > 40 chars, when post-validated, then it's truncated to 40 with "…" suffix OR fallback quote is used.
- [ ] Given the LLM fails, when called, then a category-appropriate fallback quote is returned (3 per category at minimum).
- [ ] Given the quote passes deny-list filter, when extracted, then it's stored on `quote_cards.quote_text`.

### Implementation Notes
- FR-018 AC, architecture §7.1.

### Tests
- [ ] Unit: char-count enforcement.
- [ ] Fallback quote per category.

### Rollback
- Always use fallback quote.

---

## ISSUE-057: Implement quote_cards row creation at session end
- Track: backend
- UI: false
- Platform: web
- Manual: false
- PRD-Ref: FR-018, FR-020
- Priority: P1
- Estimate: 1d
- Status: backlog
- Owner:
- Depends-On: ISSUE-017, ISSUE-056

### Goal
At reading or tarot session end, a `quote_cards` row is inserted with `share_slug`, `quote_text`, `character_key`, and `og_status='pending'`; queues OG bake job.

### Scope (In/Out)
- In: `content.quote_card_service.create_for_reading(reading_id)` and `create_for_tarot(tarot_id)`; `share_slug` generated as base62 hash; arq job enqueue for OG bake.
- Out: Worker bake (ISSUE-058), frontend (ISSUE-059).

### Acceptance Criteria (DoD)
- [ ] Given a reading completes, when the pipeline calls `create_for_reading(reading_id)`, then a `quote_cards` row is inserted with `og_status='pending'`.
- [ ] Given the row is inserted, when the arq worker polls, then an `og_bake` job is queued.
- [ ] Given a `share_slug` is generated, when checked, then it's ≤ 12 chars, unique, URL-safe.

### Implementation Notes
- data_model §4.16, AP-42.

### Tests
- [ ] Slug uniqueness test (insert 10,000 rows).

### Rollback
- Skip quote card generation; users see fallback static card on session end.

---

## ISSUE-058: Implement OG image bake worker (server-side render)
- Track: backend
- UI: false
- Platform: web
- Manual: false
- PRD-Ref: FR-018, FR-020
- Priority: P1
- Estimate: 1.5d
- Status: backlog
- Owner:
- Depends-On: ISSUE-038, ISSUE-057

### Goal
arq worker job `og_bake(quote_card_id)` composites the 1080×1920 image (background color + character illustration + quote text + watermark) and uploads to R2.

### Scope (In/Out)
- In: `voicesaju/jobs/og_bake.py`; Pillow-based compositor pulling category color + prebuilt PNG layers (character + frame) + drawing quote text in Pretendard; uploads to `og/{quote_card_id}.png`; updates `quote_cards.og_status='baked'`, `og_r2_key=...`.
- Out: Next.js OG edge route (ISSUE-060).

### Acceptance Criteria (DoD)
- [ ] Given a `quote_cards` row with `og_status='pending'`, when the worker processes it, then a 1080×1920 PNG exists in R2 within 3s of job start.
- [ ] Given the category is 연애, when baked, then the background is pink (per FR-018 AC, hex per A-06).
- [ ] Given baking fails, when retried 3×, then `og_status='failed'` and a fallback static card is used by `/share/[slug]` SSR.

### Implementation Notes
- Architecture §2 (OG image generation tradeoff: this issue keeps the bake on the backend via Pillow for the cached image; Next.js `@vercel/og` handles the live OG route in ISSUE-060).
- FR-018 AC color hex (A-06).

### Tests
- [ ] Integration: queue job → bake → R2 file exists.
- [ ] Color variant test per category.

### Rollback
- Set `og_status='failed'` for all; users see static fallback card.

---

## ISSUE-059: Implement /reading/end + ShareButtonRow component
- Track: frontend
- UI: true
- Platform: web
- Manual: false
- PRD-Ref: FR-019, US-08
- Priority: P1
- Estimate: 1.5d
- Status: backlog
- Owner:
- Depends-On: ISSUE-057, ISSUE-058

### Goal
`/reading/end` (Screen 11) shows the generated quote card and `<ShareButtonRow>` (인스타 / 카카오 / 이미지 저장).

### Scope (In/Out)
- In: Page route; `<QuoteCardPreview>` component with skeleton + fallback; `<ShareButtonRow>` with capability detection (native share sheet, KakaoTalk SDK, download); signup modal for non-members; "또 풀이 받기" + "마이페이지로" secondary CTAs.
- Out: Subscription upsell routing (ISSUE-067).

### Acceptance Criteria (DoD)
- [ ] Given I land on `/reading/end`, when card loads, then I see the quote card image + 3 share buttons within 3s.
- [ ] Given I tap "인스타 공유" on iOS Safari, when tapped, then the native share sheet opens.
- [ ] Given I tap "카카오 공유", when tapped, then the KakaoTalk SDK dialog opens.
- [ ] Given I tap "이미지 저장", when tapped, then the 1080×1920 PNG downloads.
- [ ] Given I am a non-member, when the screen loads, then the signup modal opens after 1s.
- [ ] Given I am on Toss WebView with restricted share, when share row renders, then "이미지 저장" + "링크 복사" are the only options.

### Implementation Notes
- ux_spec Screen 11, Flow F.

### Tests
- [ ] Playwright e2e: card load + each share button.

### Rollback
- Remove route.

---

## ISSUE-060: Implement /api/og/[slug] edge route (Next.js @vercel/og)
- Track: frontend
- UI: false
- Platform: web
- Manual: false
- PRD-Ref: FR-020
- Priority: P1
- Estimate: 1d
- Status: backlog
- Owner:
- Depends-On: ISSUE-058

### Goal
`GET /api/og/[slug]` returns a 1080×1920 PNG; used as the cached OG image for social previews.

### Scope (In/Out)
- In: `web/app/api/og/[slug]/route.ts`; calls backend to fetch quote card data; either redirects to R2 baked image (preferred) OR generates inline via `@vercel/og` as fallback; sets long cache headers.
- Out: Share landing page (ISSUE-061).

### Acceptance Criteria (DoD)
- [ ] Given a valid `slug`, when `GET /api/og/{slug}` is called, then a 1080×1920 PNG is returned (200, `content-type: image/png`).
- [ ] Given the baked image exists in R2, when called, then the route redirects to the signed R2 URL (sub-100ms).
- [ ] Given the slug doesn't exist, when called, then 404.

### Implementation Notes
- Architecture §6.6, §2 (`@vercel/og`).

### Tests
- [ ] Playwright: fetch image → assert dimensions + content-type.

### Rollback
- Remove route; OG images degraded to placeholder.

---

## ISSUE-061: Implement /share/[slug] landing page (SSR + OG meta)
- Track: frontend
- UI: true
- Platform: web
- Manual: false
- PRD-Ref: FR-020
- Priority: P1
- Estimate: 1d
- Status: backlog
- Owner:
- Depends-On: ISSUE-060

### Goal
`/share/[slug]` (Screen 23) is server-rendered with full OG meta tags pointing to `/api/og/[slug]`.

### Scope (In/Out)
- In: `app/share/[slug]/page.tsx` (RSC); `generateMetadata()` returns `og:image`, `og:title`, `og:description`, `twitter:card=summary_large_image`; fetches quote card from backend; "내 풀이도 받아보기" CTA → `/onboarding/birth-date`; handles expired slug per ux_spec Screen 23 error state.
- Out: Backend route (already in ISSUE-057).

### Acceptance Criteria (DoD)
- [ ] Given a social crawler fetches `/share/{slug}`, when responded, then `<meta property="og:image" content="/api/og/{slug}">` is present.
- [ ] Given the slug doesn't exist, when fetched, then a 404 page renders with "이 풀이의 명대사는 만료됐어요" + CTA.
- [ ] Given a human user views the page, when loaded, then the quote card image + "내 풀이도 받아보기" CTA render.

### Implementation Notes
- ux_spec Screen 23.

### Tests
- [ ] OG meta tags present in SSR HTML.
- [ ] 404 path.

### Rollback
- Remove route.

---

## ISSUE-062: Implement signup migration of non-member quote card on signup
- Track: backend
- UI: false
- Platform: web
- Manual: false
- PRD-Ref: US-02, FR-003
- Priority: P1
- Estimate: 0.5d
- Status: backlog
- Owner:
- Depends-On: ISSUE-026, ISSUE-057

### Goal
On signup, any `quote_cards` / `readings` rows owned by the linked device transfer ownership to the new user account.

### Scope (In/Out)
- In: `users.services.migrate_device_to_user(device_id, user_id)`; updates `readings.device_id=NULL, user_id=...`; updates `quote_cards` indirectly via reading link.
- Out: Frontend trigger (handled in signup flow).

### Acceptance Criteria (DoD)
- [ ] Given a device has 1 reading and 1 quote card, when migrated to a new user, then both rows are reassigned and the device's `linked_user_id` is set.
- [ ] Given migration runs and fails on one row, when committed, then transaction rolls back atomically.

### Implementation Notes
- AP-07.

### Tests
- [ ] Integration migration test.

### Rollback
- Skip migration; non-member rows remain orphaned (degraded UX).

---

# M5 — My Page

## ISSUE-063: Implement /me home screen
- Track: frontend
- UI: true
- Platform: web
- Manual: false
- PRD-Ref: US-15, US-16, FR-026, FR-027
- Priority: P1
- Estimate: 1d
- Status: backlog
- Owner:
- Depends-On: ISSUE-022, ISSUE-026

### Goal
`/me` (Screen 16) shows greeting + stats + navigation list (사주 명식 / 풀이 히스토리 / 결제·구독 관리 / 사주 정보 수정 / 약관·개인정보 / 로그아웃).

### Scope (In/Out)
- In: Page route (auth-required); fetches `GET /api/v1/me` for profile + entitlements; renders stats strip (풀이 N회 / 구독 상태 / 무료 토큰 N개); empty state for new members with signup token CTA.
- Out: Sub-pages (ISSUE-064+).

### Acceptance Criteria (DoD)
- [ ] Given I'm logged in, when I visit `/me`, then I see my profile greeting + stats + nav list within 1s.
- [ ] Given I'm a subscriber, when loaded, then a status pill "월 구독 중 — 다음 결제 [date]" displays prominently.
- [ ] Given I'm not logged in, when I visit `/me`, then I'm redirected to login (or signup modal opens).
- [ ] Given my profile fetch fails, when error state renders, then "잠시 후 다시 시도해주세요" + retry button.

### Implementation Notes
- ux_spec Screen 16.

### Tests
- [ ] Playwright e2e.

### Rollback
- Remove route.

---

## ISSUE-064: Implement /me/saju (saju chart visualization)
- Track: frontend
- UI: true
- Platform: web
- Manual: false
- PRD-Ref: FR-011, US-05
- Priority: P1
- Estimate: 1d
- Status: backlog
- Owner:
- Depends-On: ISSUE-029, ISSUE-063

### Goal
`/me/saju` (Screen 17) renders the user's 4-pillar chart via `<SajuChart>` component with tooltips.

### Scope (In/Out)
- In: Page route; `<SajuChart>` component (4 pillars × 천간/지지/오행/십신, accessible table); cell tooltip on tap/keyboard; "모름" Hour Pillar handling; "정보 수정하기" link → `/me/edit-saju`.
- Out: Edit form (ISSUE-071).

### Acceptance Criteria (DoD)
- [ ] Given I'm logged in with a chart, when I visit `/me/saju`, then 4 pillars render with KR character labels.
- [ ] Given `birth_time_unknown=true`, when rendered, then Hour Pillar shows "모름" and is visually de-emphasized.
- [ ] Given I tap any cell, when tapped, then a tooltip shows the 오행 + 십신 explanation.
- [ ] Given keyboard navigation, when I use arrow keys, then tooltip focus moves across the grid (NFR-013).
- [ ] Given screen reader, when activated on a cell, then it announces "년주 천간 무자, 오행 수, 십신 비견".

### Implementation Notes
- ux_spec Screen 17.

### Tests
- [ ] axe-core a11y.
- [ ] Keyboard nav test.

### Rollback
- Remove route.

---

## ISSUE-065: Implement /me/history (reading history list)
- Track: frontend
- UI: true
- Platform: web
- Manual: false
- PRD-Ref: FR-028, US-16
- Priority: P1
- Estimate: 1d
- Status: backlog
- Owner:
- Depends-On: ISSUE-063, ISSUE-066

### Goal
`/me/history` (Screen 18) lists past readings (date + category badge + summary + play icon); supports pagination.

### Scope (In/Out)
- In: Page route; fetches paginated `GET /api/v1/me/readings` (20/page); list of `<HistoryReadingRow>`; empty state for no readings; expired/deleted audio rows show "재생 불가".
- Out: Detail player (ISSUE-066).

### Acceptance Criteria (DoD)
- [ ] Given I have 5 past readings, when I visit `/me/history`, then 5 rows render sorted by date desc.
- [ ] Given I have 0 readings, when loaded, then empty state with 누님 illustration + "아직 풀이가 없네. 첫 풀이 받아볼래?" + CTA.
- [ ] Given a row has expired audio, when rendered, then it shows "재생 불가" label and is unclickable.
- [ ] Given I tap a row, when tapped, then I navigate to `/me/history/[id]`.

### Implementation Notes
- ux_spec Screen 18.

### Tests
- [ ] Playwright e2e.

### Rollback
- Remove route.

---

## ISSUE-066: Implement /me/history/[id] (history player) + GET /api/v1/me/readings
- Track: frontend, backend
- UI: true
- Platform: web
- Manual: false
- PRD-Ref: FR-028, US-16
- Priority: P1
- Estimate: 1d
- Status: backlog
- Owner:
- Depends-On: ISSUE-015, ISSUE-038, ISSUE-063

### Goal
`/me/history/[id]` (Screen 19) streams archived `reading_audio.r2_key` for replay (no regeneration). Backend route `GET /api/v1/me/readings` and `GET /api/v1/reading/{id}/audio.mp3` (Range-supported).

### Scope (In/Out)
- In: Backend route returning signed R2 URL with Range support; frontend page reusing `<VoicePlayer>` in non-streaming mode; archive ribbon "[YYYY-MM-DD] 풀이"; expired-audio fallback message.
- Out: Follow-up history (deferred to v1.1).

### Acceptance Criteria (DoD)
- [ ] Given I have a past reading, when I visit `/me/history/[id]`, then the archived audio streams without regeneration.
- [ ] Given the audio file no longer exists in R2, when loaded, then "이 풀이는 더 이상 재생할 수 없습니다" displays.
- [ ] Given I tap pause, when paused, then audio stops.

### Implementation Notes
- Architecture §6.3 (audio.mp3 Range endpoint), AP-27, AP-28.

### Tests
- [ ] Integration: archive read → stream.
- [ ] Expired-audio fallback test.

### Rollback
- Remove route.

---

## ISSUE-067: Implement /me/billing (subscription + payment history)
- Track: frontend
- UI: true
- Platform: web
- Manual: false
- PRD-Ref: FR-026, US-12
- Priority: P1
- Estimate: 1d
- Status: backlog
- Owner:
- Depends-On: ISSUE-063, ISSUE-044, ISSUE-068

### Goal
`/me/billing` (Screen 20) shows subscription status card + single-purchase history list + "구독 해지" or "구독 시작하기" CTA.

### Scope (In/Out)
- In: Page route; fetches `GET /api/v1/subscriptions/me` + `GET /api/v1/payments/history`; renders subscription status (tier, next billing, amount) or empty state; payment history list with `<PaymentReceiptRow>`; "구독 해지" confirm modal → backend cancel (ISSUE-068).
- Out: Subscription checkout (ISSUE-069).

### Acceptance Criteria (DoD)
- [ ] Given I'm a subscriber, when I visit `/me/billing`, then I see tier + next billing date + amount + "구독 해지" button.
- [ ] Given I'm not a subscriber and have no purchases, when loaded, then empty state + "구독 시작하기" CTA.
- [ ] Given I tap "구독 해지", when tapped, then a confirm modal appears with the next billing date in the message (Flow I).
- [ ] Given I confirm cancellation, when API succeeds, then status pill updates to "해지 예정 — [date]까지 이용 가능".

### Implementation Notes
- ux_spec Screen 20, Flow I.

### Tests
- [ ] Playwright e2e: subscribed + non-subscribed states.

### Rollback
- Remove route.

---

## ISSUE-068: Implement subscription create + cancel endpoints
- Track: backend
- UI: false
- Platform: web
- Manual: false
- PRD-Ref: FR-022, US-12
- Priority: P1
- Estimate: 1d
- Status: backlog
- Owner:
- Depends-On: ISSUE-014, ISSUE-044, ISSUE-045

### Goal
`POST /api/v1/subscriptions` initializes a Toss recurring billing handle. `POST /api/v1/subscriptions/cancel` schedules cancel at period end.

### Scope (In/Out)
- In: Routes; creates `subscriptions` row via Toss billing API; cancel sets `cancel_requested_at` + `status='cancel_at_period_end'`; webhook handler (in ISSUE-045) processes recurring renewal + cancellation.
- Out: UI (ISSUE-067).

### Acceptance Criteria (DoD)
- [ ] Given a valid `POST /api/v1/subscriptions {method:"tosspay"}`, when called, then a Subscription row is created with `status='active'`, `current_period_start/end`, `monthly_saju_remaining=1`.
- [ ] Given `POST /api/v1/subscriptions/cancel` is called by a subscriber, when called, then `status='cancel_at_period_end'`, `cancel_requested_at=now()`; access maintained until `current_period_end`.
- [ ] Given Toss API fails on cancel, when retried, then arq retry job schedules retries up to 3×.

### Implementation Notes
- Architecture §6.5, AP-38, AP-40.

### Tests
- [ ] Integration with Toss sandbox.
- [ ] Cancel state transitions.

### Rollback
- Disable routes.

---

## ISSUE-069: Implement /me/billing/subscribe checkout flow
- Track: frontend
- UI: true
- Platform: web
- Manual: false
- PRD-Ref: FR-022, US-12
- Priority: P1
- Estimate: 1d
- Status: backlog
- Owner:
- Depends-On: ISSUE-067, ISSUE-068

### Goal
`/me/billing/subscribe` opens Toss Payments SDK for subscription checkout.

### Scope (In/Out)
- In: Page route; loads Toss Payments JS SDK; calls `POST /api/v1/subscriptions` to get billing handle params; handles success → redirect to `/me/billing`; handles failure with retry.
- Out: Toss webhook (ISSUE-045).

### Acceptance Criteria (DoD)
- [ ] Given I tap "구독 시작하기" on `/me/billing` or `/upsell/subscription`, when routed, then the Toss SDK modal opens within 1s.
- [ ] Given payment succeeds, when callback fires, then I'm routed back to `/me/billing` with status "구독 중".
- [ ] Given payment fails, when callback fires, then a "결제가 실패했어요" banner shows with "다시 결제하기" button.

### Implementation Notes
- ux_spec Flow D, Flow E.

### Tests
- [ ] Playwright e2e with Toss test mode.

### Rollback
- Remove route.

---

## ISSUE-070: Implement /upsell/subscription screen (2nd-purchase upsell)
- Track: frontend
- UI: true
- Platform: web
- Manual: false
- PRD-Ref: FR-025, US-11
- Priority: P2
- Estimate: 0.5d
- Status: backlog
- Owner:
- Depends-On: ISSUE-069

### Goal
`/upsell/subscription` (Screen 22) auto-shows once after a user's 2nd single purchase.

### Scope (In/Out)
- In: Page route; triggered server-side after `payments.count(type='single', status='paid') = 2`; once-per-account flag (`upsell_shown_at` on user OR Redis flag); price comparison strip; "구독 시작하기" → `/me/billing/subscribe`; "다음에 할게요" → `/me`.
- Out: Backend trigger logic in payment confirm (modified ISSUE-044/045).

### Acceptance Criteria (DoD)
- [ ] Given a user has 2 lifetime single purchases and has never seen the upsell, when their 2nd payment completes, then they're routed to `/upsell/subscription`.
- [ ] Given the user dismisses the upsell, when "다음에 할게요" tapped, then the once-shown flag is set and the screen never re-appears.
- [ ] Given the user has 3+ purchases, when checked, then the screen is not shown (already past the trigger window).

### Implementation Notes
- ux_spec Screen 22, AP-22.

### Tests
- [ ] State-transition test.

### Rollback
- Remove route; upsell disabled.

---

## ISSUE-071: Implement /me/edit-saju + PATCH /api/v1/profile (2 free corrections)
- Track: backend, frontend
- UI: true
- Platform: web
- Manual: false
- PRD-Ref: FR-029, US-17
- Priority: P1
- Estimate: 1.5d
- Status: backlog
- Owner:
- Depends-On: ISSUE-010, ISSUE-029, ISSUE-063

### Goal
`PATCH /api/v1/profile` increments `correction_count` server-side (max 2). `/me/edit-saju` (Screen 21) renders form with counter banner and 운영 문의 fallback.

### Scope (In/Out)
- In: Backend PATCH route enforcing counter; new `saju_charts` row inserted on each correction (preserves history); frontend form with confirm modal "수정 후엔 새 사주로 풀이가 나와요. 과거 히스토리는 그대로 남아요."; empty state (0/2 remaining) with mailto link.
- Out: New chart used in future readings (already handled by existing pipeline).

### Acceptance Criteria (DoD)
- [ ] Given I have used 0 corrections, when I PATCH a new birth_date, then counter increments to 1 and a new `saju_charts` row is created.
- [ ] Given I have used 2 corrections, when I PATCH, then 403 with `error.code='correction_quota_exceeded'`.
- [ ] Given the counter is 2/2, when I visit `/me/edit-saju`, then the form is replaced with the 운영 문의 message.
- [ ] Given a correction is saved, when I view `/me/history`, then past reading entries still reference the old `chart_id`.

### Implementation Notes
- Architecture §6.2, FR-029 AC, AP-14.

### Tests
- [ ] Counter enforcement integration test.
- [ ] Past history unchanged after correction.

### Rollback
- Disable PATCH endpoint; users contact ops for changes.

---

## ISSUE-072: Implement /me/account (logout + delete account)
- Track: frontend, backend
- UI: true
- Platform: web
- Manual: false
- PRD-Ref: NFR-005 (GDPR/PIPA)
- Priority: P2
- Estimate: 1d
- Status: backlog
- Owner:
- Depends-On: ISSUE-008, ISSUE-063

### Goal
`/me/account` provides logout and "회원 탈퇴" (soft-delete account) functionality.

### Scope (In/Out)
- In: `POST /api/v1/auth/logout` + `POST /api/v1/users/me/delete` (soft-delete, sets `users.deleted_at` + `profiles.deleted_at`); confirm modal; logged-out redirect to `/`.
- Out: Hard-delete cron worker (ISSUE-088).

### Acceptance Criteria (DoD)
- [ ] Given I tap "로그아웃", when called, then my session is destroyed and I'm redirected to `/`.
- [ ] Given I tap "회원 탈퇴" and confirm, when the API call succeeds, then `users.deleted_at` is set and I'm logged out.
- [ ] Given my account is soft-deleted, when I try to log in with the same provider, then a new account is created (treated as a new user after 30-day grace).

### Implementation Notes
- Architecture §11, AP-08.

### Tests
- [ ] Soft-delete state transition.

### Rollback
- Disable delete; logout only.

---

## ISSUE-073: Implement GET /api/v1/payments/history endpoint
- Track: backend
- UI: false
- Platform: web
- Manual: false
- PRD-Ref: FR-026, US-12
- Priority: P1
- Estimate: 0.5d
- Status: backlog
- Owner:
- Depends-On: ISSUE-014

### Goal
`GET /api/v1/payments/history` returns paginated single-purchase history (20/page, desc by `created_at`).

### Scope (In/Out)
- In: Route; uses `payments_user_created_idx` for fast scan; returns `[{id, type, category, amount_krw, status, paid_at, refunded_amount_krw}]`.
- Out: Frontend (already in ISSUE-067).

### Acceptance Criteria (DoD)
- [ ] Given a user with 25 payments, when `GET /payments/history?page=1` is called, then 20 rows are returned sorted by `created_at DESC`.
- [ ] Given a user has 0 payments, when called, then `[]` is returned.

### Implementation Notes
- AP-39.

### Tests
- [ ] Pagination test.

### Rollback
- Disable route.

---

# M6 — Polish + Launch

## ISSUE-074: Implement legal pages (/legal/terms, /legal/privacy, /legal/refund)
- Track: content
- UI: true
- Platform: web
- Manual: false
- PRD-Ref: NFR-005 (PIPA/GDPR)
- Priority: P1
- Estimate: 1d
- Status: backlog
- Owner:
- Depends-On: ISSUE-002

### Goal
Three legal pages render the finalized ToS, Privacy Policy, and Refund Policy in Korean.

### Scope (In/Out)
- In: `/legal/terms` (이용약관 with "오락 목적" 면책 명시); `/legal/privacy` (개인정보 처리방침 — birth date encryption details); `/legal/refund` (환불 정책 — LLM 실패 시 자동 환불); static MDX or React content.
- Out: Backend legal review (requires legal counsel input).

### Acceptance Criteria (DoD)
- [ ] Given I visit `/legal/terms`, when loaded, then "오락 목적" disclaimer is visible in the content.
- [ ] Given I visit `/legal/privacy`, when loaded, then AES-256 encryption mention + Toss Payments data handling are stated.
- [ ] Given the page is rendered, when axe-core scans, then zero AA violations.

### Implementation Notes
- PRD §6.2, ux_spec §3 (Screens 1, 8 reference legal links).

### Tests
- [ ] All 3 pages return 200.
- [ ] axe-core a11y.

### Rollback
- Replace with "준비 중" placeholder.

---

## ISSUE-075: Implement error pages (/error/404 + /error/payment-failed + /error/llm-failed)
- Track: frontend
- UI: true
- Platform: web
- Manual: false
- PRD-Ref: FR-033, FR-036
- Priority: P1
- Estimate: 1d
- Status: backlog
- Owner:
- Depends-On: ISSUE-021, ISSUE-022

### Goal
Three error screens render gracefully with character voice and recovery CTAs.

### Scope (In/Out)
- In: `app/not-found.tsx` (404); `/error/payment-failed` reused on paywall failures (already in payment flow, this issue formalizes the screen); `/error/llm-failed` (Screen 26) with 누님 illustration + "별기운이 잠시 약하네…" + 다시 시도 / 마이페이지로 buttons.
- Out: Backend error codes (already in pipeline issues).

### Acceptance Criteria (DoD)
- [ ] Given a 404 URL, when fetched, then a friendly 404 page renders with home CTA.
- [ ] Given an LLM failure, when triggered, then the user sees 누님 illustration + "별기운이 잠시 약하네…" + refund/token notification.
- [ ] Given 다시 시도 is tapped, when called, then I'm routed back to the source screen.

### Implementation Notes
- ux_spec Screen 26.

### Tests
- [ ] Playwright e2e: triggered LLM failure state.

### Rollback
- Default Next.js error pages.

---

## ISSUE-076: Implement automatic refund worker (FR-023)
- Track: backend
- UI: false
- Platform: web
- Manual: false
- PRD-Ref: FR-023, FR-033
- Priority: P0
- Estimate: 1d
- Status: backlog
- Owner:
- Depends-On: ISSUE-013, ISSUE-014, ISSUE-039, ISSUE-045

### Goal
arq job `refund_for_reading(reading_id)` calls Toss refund API; on failure, credits a `failure_compensation` FreeToken.

### Scope (In/Out)
- In: `voicesaju/payment/refund.py`; `voicesaju/jobs/refund_retry.py`; called from reading pipeline on LLM failure; inserts `refunds` row; status transitions per data_model §4.15.
- Out: Refund UI in `/me/billing` (already covered).

### Acceptance Criteria (DoD)
- [ ] Given a reading fails after payment, when the refund job runs within 60s, then `payments.status='refunded'` and `refunds.status='succeeded'`.
- [ ] Given Toss refund API fails, when the fallback triggers, then a `free_tokens` row with `kind='failure_compensation'` is inserted and `refunds.status='failed_credited'`.
- [ ] Given the user is notified, when refund completes, then the message "환불 또는 무료 이용권이 지급되었습니다" is shown on next visit.

### Implementation Notes
- Architecture §6.5, AP-41.

### Tests
- [ ] Refund happy path.
- [ ] Fallback to FreeToken when Toss API fails.

### Rollback
- Manual refund only via ops dashboard.

---

## ISSUE-077: Implement OpenTelemetry instrumentation + Grafana Cloud setup
- Track: platform
- UI: false
- Platform: web
- Manual: false
- PRD-Ref: NFR-001, NFR-002, NFR-003, NFR-004, NFR-011, NFR-016
- Priority: P1
- Estimate: 1d
- Status: backlog
- Owner:
- Depends-On: ISSUE-039

### Goal
OpenTelemetry SDK is wired in FastAPI; key spans (entitlement_check, chart_compute, llm_stream, guardrail_filter, tts_chunk, r2_put, sse_emit) emit to Grafana Cloud.

### Scope (In/Out)
- In: `voicesaju/observability/otel.py`; OTLP exporter to Grafana Cloud; auto-instrumentation for FastAPI + asyncpg + httpx; custom spans in pipeline; Prometheus metrics on `/metrics`.
- Out: Frontend RUM (deferred).

### Acceptance Criteria (DoD)
- [ ] Given a reading session runs, when traced, then Grafana shows a single trace with all 7 pipeline spans.
- [ ] Given `/metrics` is scraped, when checked, then `reading_pipeline_e2e_seconds_bucket`, `tts_first_chunk_seconds_bucket`, `llm_call_duration_seconds_bucket` are present.
- [ ] Given p95 reading e2e > 5s, when alert fires, then PagerDuty (or email) is triggered.

### Implementation Notes
- Architecture §12.

### Tests
- [ ] Trace generation smoke test.

### Rollback
- Disable OTel export; spans collected locally only.

---

## ISSUE-078: Implement Sentry error tracking
- Track: platform
- UI: false
- Platform: web
- Manual: false
- PRD-Ref: NFR-016
- Priority: P1
- Estimate: 0.5d
- Status: backlog
- Owner:
- Depends-On: ISSUE-001, ISSUE-002

### Goal
Sentry SDK is wired into both backend (Python) and frontend (Next.js) with PII redaction.

### Scope (In/Out)
- In: Sentry init in `voicesaju/main.py` and `web/src/sentry.client.ts`; PII scrubbing filters (no birth_dt, no payment keys); release tagging from CI.
- Out: Custom dashboards.

### Acceptance Criteria (DoD)
- [ ] Given a backend exception is raised, when captured, then a Sentry issue appears within 30s.
- [ ] Given an error contains `birth_dt`, when sent, then the field is redacted before transmission.
- [ ] Given a frontend error, when captured, then the source map resolves the stack to readable code.

### Implementation Notes
- Architecture §12.1.

### Tests
- [ ] Trigger test error → verify Sentry capture.

### Rollback
- Remove SDK init.

---

## ISSUE-079: Implement structured logging + PII redaction
- Track: backend
- UI: false
- Platform: web
- Manual: false
- PRD-Ref: NFR-005, OWASP A09
- Priority: P1
- Estimate: 0.5d
- Status: backlog
- Owner:
- Depends-On: ISSUE-001

### Goal
All backend logs are JSON-structured to stdout with request_id, user_id, and a redaction filter that strips birth_dt/payment keys.

### Scope (In/Out)
- In: `voicesaju/observability/logging.py` using `structlog`; middleware to inject `request_id`; redaction filter; ship to Logtail/Better Stack via container runtime.
- Out: Log search dashboards.

### Acceptance Criteria (DoD)
- [ ] Given a request hits the API, when logged, then JSON output includes `timestamp`, `level`, `request_id`, `route`, `event`.
- [ ] Given a log message attempts to include `birth_dt`, when emitted, then the value is replaced with `[REDACTED]`.
- [ ] Given log volume, when shipped, then Logtail receives them within 30s.

### Implementation Notes
- Architecture §12.1.

### Tests
- [ ] Redaction unit test.

### Rollback
- Revert to default logging.

---

## ISSUE-080: Implement analytics event SDK (frontend + backend)
- Track: frontend, backend
- UI: false
- Platform: web
- Manual: false
- PRD-Ref: NFR-016 (success metrics §10.2)
- Priority: P1
- Estimate: 1d
- Status: backlog
- Owner:
- Depends-On: ISSUE-024, ISSUE-026

### Goal
Frontend emits funnel events (`onboarding_step`, `paywall_view`, `paywall_pay`, `reading_complete`, `quote_share`, `signup`); backend emits `payment_completed`, `subscription_started`, `subscription_cancelled`.

### Scope (In/Out)
- In: `web/src/lib/analytics/events.ts` (Mixpanel or PostHog SDK wrapper); `voicesaju/analytics/events.py`; events documented in `docs/analytics_events.md`.
- Out: Dashboards (vendor-side).

### Acceptance Criteria (DoD)
- [ ] Given I complete onboarding, when the event fires, then `onboarding_step` events for steps 1–4 are sent.
- [ ] Given I share a quote card, when tapped, then `quote_share` event with `channel=instagram|kakao|download` is sent.
- [ ] Given a payment completes, when webhook processes, then `payment_completed` event with amount + category is sent.

### Implementation Notes
- PRD §8.2.

### Tests
- [ ] Event emission unit test.

### Rollback
- Disable SDK init.

---

## ISSUE-081: Implement rate limiting middleware (auth + payment endpoints)
- Track: backend
- UI: false
- Platform: web
- Manual: false
- PRD-Ref: NFR-016, OWASP A07
- Priority: P1
- Estimate: 1d
- Status: backlog
- Owner:
- Depends-On: ISSUE-004, ISSUE-026

### Goal
Token-bucket rate limit applied to auth + payment endpoints (architecture §11.4).

### Scope (In/Out)
- In: `voicesaju/security/ratelimit.py` (Redis-backed token bucket); FastAPI dependency; default 10 req/min per IP for auth, 5 req/min per user for payment checkout.
- Out: Reading pipeline rate limit (separate concerns, deferred).

### Acceptance Criteria (DoD)
- [ ] Given an IP exceeds 10 req/min on auth endpoints, when the 11th request arrives, then 429 with retry-after header.
- [ ] Given Redis is down, when the limiter fails open, then a `WARNING` log is emitted (NEVER fail-closed on rate limit).

### Implementation Notes
- Architecture §11.4.

### Tests
- [ ] Burst → 429 test.

### Rollback
- Remove dependency; endpoints unrated.

---

## ISSUE-082: Implement CSRF protection (X-VS-CSRF header)
- Track: backend
- UI: false
- Platform: web
- Manual: false
- PRD-Ref: OWASP A01
- Priority: P1
- Estimate: 0.5d
- Status: backlog
- Owner:
- Depends-On: ISSUE-026

### Goal
All non-GET requests require a valid `X-VS-CSRF` header matching the session secret.

### Scope (In/Out)
- In: CSRF middleware; per-session secret stored in Redis; frontend reads from `GET /api/v1/csrf` and adds to all mutating fetches; Toss WebView bypasses (uses Authorization header instead).
- Out: None.

### Acceptance Criteria (DoD)
- [ ] Given a POST without `X-VS-CSRF`, when sent, then 403.
- [ ] Given a POST with a valid CSRF token matching the session, when sent, then proceeds normally.
- [ ] Given a Toss WebView POST with Authorization header, when sent, then proceeds without CSRF (per architecture §11.1).

### Implementation Notes
- Architecture §11.1.

### Tests
- [ ] CSRF rejection + acceptance tests.

### Rollback
- Disable middleware (security gap until fixed).

---

## ISSUE-083: Implement Dockerfile + multi-stage build
- Track: platform
- UI: false
- Platform: web
- Manual: false
- PRD-Ref: NFR-016
- Priority: P0
- Estimate: 1d
- Status: backlog
- Owner:
- Depends-On: ISSUE-006, ISSUE-038

### Goal
Multi-stage Dockerfile builds backend container with `uv export → pip install`, ffmpeg, and arq worker entrypoint.

### Scope (In/Out)
- In: `api/Dockerfile` (Python 3.11-slim base, uv install, ffmpeg apt-install, non-root user, healthcheck); `process_groups` config for web + worker.
- Out: Frontend (Vercel handles automatically).

### Acceptance Criteria (DoD)
- [ ] Given `docker build .` runs, when complete, then the image is < 500MB.
- [ ] Given `docker run ...` starts, when healthcheck fires, then `/healthz` returns 200 within 30s.
- [ ] Given an attacker tries `exec sh` as the container user, when checked, then it's a non-root user.

### Implementation Notes
- Architecture §13.2, claude.md `uv export -o requirements.txt`.

### Tests
- [ ] Image build + smoke test in CI.

### Rollback
- Use single-stage Dockerfile.

---

## ISSUE-084: Manual setup — deploy backend to Fly.io (staging)
- Track: platform
- UI: false
- Platform: web
- Manual: true
- PRD-Ref: NFR-016
- Priority: P0
- Estimate: 1d
- Status: deferred
- Owner:
- Depends-On: ISSUE-083

> **Note (2026-05-28):** Deferred to Phase 2 (post-MVP). v1 runs locally via `docker compose up` against the Mock adapter stack (ISSUE-099..102). Cloud deployment resumes when Phase 2 launches.

### Goal
Backend container is deployed to Fly.io staging in NRT region with both `web` and `worker` process groups.

### Scope (In/Out)
- In: `fly.toml` config; `flyctl deploy` to staging; Fly secrets configured; healthcheck wired; 2 instance minimum.
- Out: Production deployment (separate launch issue).

### Acceptance Criteria (DoD)
- [ ] Given the deploy runs, when complete, then `https://staging-api.voicesaju.fly.dev/healthz` returns 200.
- [ ] Given the worker process group is running, when checked via `flyctl status`, then both `web` and `worker` processes are listed.

### Implementation Notes
- Architecture §13.1.

### Tests
- [ ] Manual deploy smoke test.

### Rollback
- `flyctl releases rollback`.

---

## ISSUE-085: Manual setup — deploy frontend to Vercel (staging)
- Track: platform
- UI: false
- Platform: web
- Manual: true
- PRD-Ref: NFR-016
- Priority: P0
- Estimate: 0.5d
- Status: deferred
- Owner:
- Depends-On: ISSUE-002

> **Note (2026-05-28):** Deferred to Phase 2 (post-MVP). v1 runs locally via `pnpm dev` and consumes the local backend (Mock adapter stack). Vercel deployment resumes when Phase 2 launches.

### Goal
Frontend is deployed to Vercel with environment variables connected to staging backend.

### Scope (In/Out)
- In: Connect GitHub repo; configure env vars (`NEXT_PUBLIC_API_URL`, `NEXT_PUBLIC_TOSS_CLIENT_KEY`, Kakao SDK key, etc.); custom domain `staging.voicesaju.example`.
- Out: Production deploy.

### Acceptance Criteria (DoD)
- [ ] Given `git push main`, when Vercel deploys, then the staging URL renders the landing page.
- [ ] Given PR is opened, when Vercel previews build, then a unique preview URL is posted in the PR.

### Implementation Notes
- Architecture §13.1.

### Tests
- [ ] Manual: visit staging URL, verify landing.

### Rollback
- Promote previous Vercel deployment to production.

---

## ISSUE-086: Implement Landing page (/) hero + CTA
- Track: frontend
- UI: true
- Platform: web
- Manual: false
- PRD-Ref: US-01, US-06
- Priority: P1
- Estimate: 1d
- Status: backlog
- Owner:
- Depends-On: ISSUE-021, ISSUE-024

### Goal
`/` (Screen 1) shows hero illustration + tagline + primary "지금 풀이 받기" + secondary "오늘의 타로" CTAs + trust strip.

### Scope (In/Out)
- In: Landing page route; hero illustration (silhouette characters); tagline; CTA buttons; trust strip (cached counter); device ID issuance on first visit.
- Out: SEO meta + OG tags (separate small issue).

### Acceptance Criteria (DoD)
- [ ] Given a new visitor lands on `/`, when loaded, then "지금 풀이 받기" and "오늘의 타로" CTAs are above the fold.
- [ ] Given a returning visitor with an in-progress session, when loaded, then CTA copy swaps to "이어서 풀이 받기".
- [ ] Given trust strip API fails, when error, then hide silently (per ux_spec).

### Implementation Notes
- ux_spec Screen 1.

### Tests
- [ ] Playwright e2e.

### Rollback
- Show placeholder landing.

---

## ISSUE-087: Implement service availability monitoring (uptime + alerts)
- Track: platform
- UI: false
- Platform: web
- Manual: false
- PRD-Ref: NFR-016
- Priority: P1
- Estimate: 0.5d
- Status: backlog
- Owner:
- Depends-On: ISSUE-077, ISSUE-084, ISSUE-085

### Goal
External uptime monitor (Uptime Robot or Better Stack) checks `/healthz` every 60s; alerts on 2 consecutive failures.

### Scope (In/Out)
- In: Sign up Better Stack / Uptime Robot; create 2 monitors (backend `/healthz`, frontend `/`); webhook alerts to email + Slack.
- Out: Custom status page.

### Acceptance Criteria (DoD)
- [ ] Given a monitor is configured, when it pings, then green checks appear in the dashboard.
- [ ] Given the backend goes down, when monitor detects 2 failures, then an alert email is sent within 3 minutes.

### Implementation Notes
- Architecture §12.4.

### Tests
- [ ] Manual: deliberately fail healthcheck, observe alert.

### Rollback
- Disable monitors.

---

## ISSUE-088: Implement GDPR/PIPA hard-delete cron worker
- Track: backend
- UI: false
- Platform: web
- Manual: false
- PRD-Ref: NFR-005 (privacy)
- Priority: P2
- Estimate: 1d
- Status: backlog
- Owner:
- Depends-On: ISSUE-072, ISSUE-018

### Goal
Daily cron worker iterates `users WHERE deleted_at < now() - 30 days` and hard-deletes user + all dependent rows with audit log.

### Scope (In/Out)
- In: arq scheduled job (daily); cascade delete walking through profiles, saju_charts, readings, transcripts, audio, tarot_draws, payments, subscriptions, quote_cards, free_tokens; insert `audit_events` row per deletion; R2 audio files deleted.
- Out: User-initiated soft-delete (already in ISSUE-072).

### Acceptance Criteria (DoD)
- [ ] Given a user soft-deleted 31 days ago, when the cron runs, then their `users` row and all dependent data are removed.
- [ ] Given the deletion runs, when audited, then `audit_events` rows exist for each deleted entity.
- [ ] Given R2 audio files belong to a deleted user, when the cron runs, then those R2 keys are also deleted.

### Implementation Notes
- Architecture §11, AP-08, AP-54.

### Tests
- [ ] Integration test: soft-delete → wait 31 sim-days → hard-delete completes.

### Rollback
- Disable cron; users remain soft-deleted indefinitely (manual ops fallback).

---

## ISSUE-089: Implement reading session metrics dashboard (Grafana)
- Track: platform
- UI: false
- Platform: web
- Manual: false
- PRD-Ref: NFR-001, NFR-002, NFR-007, NFR-011
- Priority: P2
- Estimate: 0.5d
- Status: backlog
- Owner:
- Depends-On: ISSUE-077

### Goal
Grafana dashboard shows reading e2e p95, TTS first chunk p95, LLM cost p50/p95, payment failure rate, tone violation rate.

### Scope (In/Out)
- In: 1 dashboard JSON committed to `ops/grafana/dashboards/reading_pipeline.json`; imported into Grafana Cloud; alert thresholds per architecture §12.4.
- Out: Business analytics dashboards.

### Acceptance Criteria (DoD)
- [ ] Given the dashboard is imported, when viewed, then 5 panels render with live metrics from staging.
- [ ] Given thresholds are set, when a metric breaches yellow/red, then a Slack alert fires.

### Implementation Notes
- Architecture §12.4.

### Tests
- [ ] Manual: validate panel data.

### Rollback
- Remove dashboard.

---

## ISSUE-090: Implement pre-launch tone regression CI gate
- Track: backend
- UI: false
- Platform: web
- Manual: false
- PRD-Ref: FR-032
- Priority: P0
- Estimate: 0.5d
- Status: backlog
- Owner:
- Depends-On: ISSUE-019, ISSUE-020

### Goal
CI workflow runs tone evalset regression on every PR + on every merge to `main`; blocks deploy if any `violation` case is not blocked.

### Scope (In/Out)
- In: `.github/workflows/tone_regression.yml`; pytest target `tests/regression/test_tone_evalset.py`; required check on `main` branch.
- Out: Real-time violation telemetry (already in ISSUE-020).

### Acceptance Criteria (DoD)
- [ ] Given a PR is opened, when CI runs, then the tone regression job runs and either passes (all violations blocked) or fails the PR check.
- [ ] Given a developer modifies the deny list and a `violation` case is missed, when CI runs, then the build fails.

### Implementation Notes
- FR-032 AC, architecture §7.3.

### Tests
- [ ] Workflow YAML lint.

### Rollback
- Make the job non-blocking (tone regression runs but doesn't block deploy — emergency only).

---

# M2.5 — v2 Design Refinement (Ink, Amber & 印)

> Cross-cutting batch that lifts the M2/M3/M4 surfaces (reading flow, daily tarot, quote card) to the v2 visual + motion + copy system. Foundation issue ISSUE-091 unblocks the remaining 7. See `docs/design_philosophy.md`, `docs/design_system.md`, `docs/wireframes.md`, `docs/interactions.md`, `docs/copy_guide.md`.

## ISSUE-091: Integrate v2 design tokens (Ink, Amber & 印 palette, type, grain, vignette)
- Track: frontend
- UI: true
- Platform: web
- Manual: false
- PRD-Ref: FR-037, NFR-012
- Priority: P0
- Estimate: 1d
- Status: backlog
- Owner:
- Branch:
- GH-Issue:
- PR:
- Depends-On: ISSUE-021

### Goal
The v2 token palette (vermilion + hanji + baekrim), brush/mincho/serif fonts, grain texture, and `vignette-edge` body utility are available globally as CSS custom properties and typed TS tokens. Part of v2 (Ink, Amber & 印) refinement batch.

### Scope (In/Out)
- In: `web/styles/tokens.css` additions (`--vermilion-{100,300,500}`, `--hanji-{900,800,700,500,300}`, `--baekrim-200`, `--font-brush`, `--font-mincho`, `--grain-strong` inline SVG noise data URI); `next/font` loaders for `Nanum Brush Script`, `Noto Serif KR (900)`, `Cormorant Garamond` with `font-display: swap`; `web/styles/utilities.css` `.vignette-edge { background: radial-gradient(...) }`; mirror typed exports in `web/lib/tokens.ts`; Storybook story to visually verify scales.
- Out: Component refactors (handled in ISSUE-092..098).

### Acceptance Criteria (DoD)
- [ ] Given the app boots, when any component reads `var(--vermilion-500)`, then a non-empty colour value is returned (smoke test via `getComputedStyle`).
- [ ] Given the typography stack loads, when `var(--font-brush)` is applied to a node, then the rendered font-family resolves to `Nanum Brush Script` (visual regression baseline captured).
- [ ] Given `<body>` has the `vignette-edge` class, when rendered at 375 px and 1280 px, then a radial-gradient overlay visibly darkens the corners by ≥ 30% luminance vs centre (Playwright pixel sample).
- [ ] Given a node sets `background-image: var(--grain-strong)`, when inspected, then the resolved background is an inline `data:image/svg+xml,...` noise pattern.
- [ ] Given axe-core runs against a sample page using hanji-900 text on baekrim-200, when scanned, then contrast ratio ≥ 4.5:1 (NFR-012).

### Implementation Notes
- design_system.md §Tokens. Mirror the same hex values across `tokens.css` and `tokens.ts` to avoid drift. Use `next/font` with `preload: true` and `subsets: ['latin']` for the Latin fonts; for Korean, `display: 'swap'` only (Noto Serif KR is large; consider `weight: ['900']` only).
- Do not delete the v1 token names yet — keep both for the duration of M2.5 to allow incremental migration.

### Tests
- [ ] Storybook visual snapshot of the token swatch grid.
- [ ] Vitest unit: `tokens.ts` exports match `tokens.css` custom property names (string equality).
- [ ] Playwright axe-core on a fixture page using v2 tokens — zero AA violations.

### Rollback
- Remove the new `--vermilion-*`, `--hanji-*`, font loaders, and `.vignette-edge`; v1 tokens still operational.

---

## ISSUE-092: Build `<Seal>` (印) component with category-hanja mapping
- Track: frontend
- UI: true
- Platform: web
- Manual: false
- PRD-Ref: FR-038
- Priority: P0
- Estimate: 1d
- Status: backlog
- Owner:
- Branch:
- GH-Issue:
- PR:
- Depends-On: ISSUE-091

### Goal
A reusable `<Seal hanja size tilt category aria-label>` component renders the vermilion stamp signature used at reading end, follow-up answer end, quote-card corner, and tarot reveal. Part of v2 (Ink, Amber & 印) refinement batch.

### Scope (In/Out)
- In: `web/components/seal/Seal.tsx`; CSS module using `--vermilion-500` background, `--font-mincho` for the hanja character, `--grain-strong` via `background-blend-mode: multiply`; default rotation `-2.5deg` (tilt=left/default), `+2.5deg` (tilt=right); size variants `sm/md/lg → 48/72/112 px`; category→hanja lookup (`love=戀, work=業, money=財, tarot=月, reading-end=明`); Storybook stories for every size × tilt × category permutation.
- Out: Composition into screen layouts (handled in ISSUE-095, 097).

### Acceptance Criteria (DoD)
- [ ] Given `<Seal hanja="戀" />`, when rendered, then the DOM contains a vermilion-500 background block with the character `戀` in mincho font and `transform: rotate(-2.5deg)`.
- [ ] Given `<Seal category="work" />`, when rendered, then the hanja resolves to `業` via the category mapping table.
- [ ] Given `<Seal tilt="right" />`, when rendered, then computed `transform` contains `rotate(2.5deg)`.
- [ ] Given `<Seal size="lg" />`, when measured, then `width === height === 112px`.
- [ ] Given the default usage, when read by axe-core, then the seal node has `aria-hidden="true"`; when `aria-label` is provided, then `aria-hidden` is removed and the label is announced by VoiceOver/NVDA.

### Implementation Notes
- design_system.md §Components → Seal; design_philosophy.md §Visual signature.
- Apply `--grain-strong` as `background-image` with `background-blend-mode: multiply` so the ink grain shows over the vermilion fill.
- Keep the component framework-agnostic at the CSS level (no Tailwind dependency in this module) to ease future portability.

### Tests
- [ ] Vitest: rendered tilt + size matrix.
- [ ] Storybook visual regression snapshot per variant.
- [ ] axe-core: aria-hidden default + aria-label override.

### Rollback
- Remove `Seal` from any consumer; reading/quote-card/tarot end still render without the signature artefact.

---

## ISSUE-093: Build `<HanjaMonument>` + `<SajuChartTile>` components
- Track: frontend
- UI: true
- Platform: web
- Manual: false
- PRD-Ref: FR-005, FR-039
- Priority: P0
- Estimate: 1d
- Status: backlog
- Owner:
- Branch:
- GH-Issue:
- PR:
- Depends-On: ISSUE-091

### Goal
Two reusable display primitives that anchor the v2 visual identity across landing, onboarding (steps 1–3), category, reading-play, and my-page screens. Part of v2 (Ink, Amber & 印) refinement batch.

### Scope (In/Out)
- In: `web/components/hanja/HanjaMonument.tsx` (`<HanjaMonument char>` renders the character at `font-size: clamp(120px, 28vw, 240px)` in `--font-mincho`, colour `--hanji-900`); `web/components/saju/SajuChartTile.tsx` (`<SajuChartTile pillar element hanja missing>` renders one cell of the 4-pillar grid; `missing=true` overlays "모름" with vermilion-300 stroke); grid wrapper `<SajuChartGrid>` (4-col responsive); accessibility attributes (`aria-label="년주 천간 무자, 오행 수"`); Storybook stories for the supported character set (`命 生 時 性 戀 業 財 月 我 門`).
- Out: Refactoring existing `<SajuChart>` consumer in ISSUE-064 (will land in a follow-up that swaps to v2 tiles).

### Acceptance Criteria (DoD)
- [ ] Given `<HanjaMonument char="命" />` is rendered at 1280 px viewport, when measured, then `font-size` resolves between 120 px and 240 px (clamp bounds verified).
- [ ] Given `<SajuChartTile pillar="hour" missing={true} />`, when rendered, then a "모름" overlay appears and the tile receives `aria-label*="모름"`.
- [ ] Given a 4-col grid of `<SajuChartTile>` at 375 px width, when rendered, then all 4 tiles fit on one row without horizontal scroll (mobile constraint per NFR-014).
- [ ] Given the supported character set `命 生 時 性 戀 業 財 月 我 門`, when iterated in Storybook, then each renders cleanly with the mincho weight 900.
- [ ] Given a tile is focused via keyboard, when Enter is pressed, then a tooltip with 오행 + 십신 explanation appears (NFR-013).

### Implementation Notes
- design_system.md §Components → HanjaMonument, SajuChartTile; wireframes.md (landing, onboarding 1-3, category, reading-play, my-page).
- For the "모름" overlay, use vermilion-300 stroke text with a subtle rotate(-1.5deg) per the uncanny-tilt convention (mirrors FR-044).
- Do not break the existing `<SajuChart>` from ISSUE-064; this is additive. The migration to use these tiles is tracked separately when the M5 page is refactored.

### Tests
- [ ] Vitest: missing-state rendering + aria-label format.
- [ ] Playwright responsive: 4-col grid at 375 px / 430 px / 1280 px.
- [ ] axe-core: tooltip keyboard reachability.

### Rollback
- Remove components from imports; landing/onboarding/category fall back to plain text headings (degraded but functional).

---

## ISSUE-094: Implement 5-card tarot spread with 3D flip sequence
- Track: frontend
- UI: true
- Platform: web
- Manual: false
- PRD-Ref: FR-013, FR-040
- Priority: P1
- Estimate: 1.5d
- Status: done
- Owner:
- Branch: feat/issue-094-tarot-spread-v2
- GH-Issue: https://github.com/pillip/voicesaju/issues/147
- PR: https://github.com/pillip/voicesaju/pull/148
- Depends-On: ISSUE-051, ISSUE-091

### Goal
The `/tarot` (Screen 12) is upgraded from a single face-down card to a 5-card fan spread; tapping any card runs the deterministic discard → centre → flip → reveal sequence, ending with the FR-013-derived card. Part of v2 (Ink, Amber & 印) refinement batch.

### Scope (In/Out)
- In: `web/components/tarot/TarotSpread.tsx`; 5 `<SpreadCard data-pos={1..5}>` with `position: absolute; top: 50%; left: 50%; margin-top: -h/2; margin-left: -w/2`; 3-layer transform separation (`.spread-card` translate, `.__pose` rotate fan -22°/-11°/0°/+11°/+22°, `.__inner` rotateY flip); parent `.tarot-spread` sets `perspective: 2400px` desktop / `1800px` mobile and `transform-style: preserve-3d`; CSS state machine driven by classes `is-moving` (650ms) → `is-centered` (450ms) → `aria-pressed=true` (500ms flip) → `.reveal-visible` (400ms fade); deterministic card is fetched once on mount via existing `/tarot/today` (FR-013) — tap target does NOT influence the reveal card.
- Out: New backend route (existing FR-013 endpoint is reused); paywall path (already in ISSUE-052).

### Acceptance Criteria (DoD)
- [ ] Given the `/tarot` page loads, when the spread renders, then 5 face-down cards are positioned in a fan at angles -22°, -11°, 0°, +11°, +22° via `.__pose`.
- [ ] Given any card index 0..4 is tapped, when the sequence runs, then non-tapped cards translate off-screen (`is-moving` 650ms), the tapped card centres (`is-centered` 450ms), the inner layer flips (`rotateY(180deg)` 500ms triggered by `aria-pressed=true`), and the reveal section fades in (`reveal-visible` 400ms).
- [ ] Given two different sessions for the same `(date_KST, user_id)` where the user taps card index 0 in session A and card index 4 in session B, when revealed, then both sessions show the **same** card art (deterministic FR-013 guarantee).
- [ ] Given `.spread-card__back` and `.spread-card__front` are inspected, when checked in DevTools, then neither sets `position: relative` (they inherit `position: absolute` from `.spread-card__face` — regression guard).
- [ ] Given a 375 px viewport, when the spread renders, then no card overflows the viewport (auto-shrink scale or reduced angles applied).
- [ ] Given the flip animation completes, when the audio pipeline reads from FR-015, then audio begins within 2 s (NFR-003 preserved).

### Implementation Notes
- design_system.md §Components → TarotSpread + interactions.md §Flow C (Tarot Reveal).
- Critical CSS rule: `.spread-card__face { position: absolute; inset: 0; }` and faces MUST inherit (do not override with `position: relative`).
- Use `transform-style: preserve-3d` on both `.__pose` and `.__inner`; otherwise the back face disappears during the flip on Safari.
- Animation classes are toggled by a small reducer in the component; do not rely on `setTimeout` chains alone — use `animationend` / `transitionend` events for the cascade so reduced-motion users see an instant reveal instead.
- Reduced-motion: respect `prefers-reduced-motion: reduce` → skip discard + centre choreography, go straight to reveal with a fade.

### Tests
- [ ] Vitest reducer: tap → is-moving → is-centered → aria-pressed → reveal-visible sequence.
- [ ] Playwright e2e: tap each of 5 indices in turn (5 separate test runs), assert the reveal card art URL is identical across all 5 — FR-013 determinism guard.
- [ ] Playwright visual regression at 375 / 1280 px (fan positioning).
- [ ] axe-core: `aria-pressed`, focus order, reduced-motion fallback.

### Rollback
- Render a single face-down card (legacy ISSUE-051 layout) by feature-flagging `TAROT_V2_SPREAD=false`; users get the v1 single-card flip.

---

## ISSUE-095: Quote card v2 (9:16 export, vermilion seal, server OG image)
- Track: frontend, backend
- UI: true
- Platform: web
- Manual: false
- PRD-Ref: FR-018, FR-020, FR-021, FR-041
- Priority: P1
- Estimate: 1.5d
- Status: done
- Owner: claude
- Branch: feat/issue-095-quote-card-v2
- GH-Issue: https://github.com/pillip/voicesaju/issues/149
- PR: https://github.com/pillip/voicesaju/pull/150
- Depends-On: ISSUE-058, ISSUE-060, ISSUE-092

### Goal
The quote card on `/reading/end` and `/tarot/end` is re-styled to the v2 spec (9:16, category borderline, -1.5deg tilt, grain overlay, vermilion `<Seal>` bottom-right) and the server-side OG image generator produces a pixel-faithful 1080×1920 PNG. Part of v2 (Ink, Amber & 印) refinement batch.

### Scope (In/Out)
- In: Frontend `<QuoteCardPreview v="v2">` variant; category borderline tokens (`love=#B7414B 마른장미`, `work=#16344E 잉크블루`, `money=#B68B3F 황동`, `tarot=#5A3666 가지색`); auto-tilt `-1.5deg`; grain overlay; `<Seal category={...} tilt="right" size="md">` composited bottom-right; server-side render in `voicesaju/jobs/og_bake.py` (Pillow) updated to match new layout + a parallel `web/app/api/og/[slug]/route.ts` `@vercel/og` template; share affordances (Instagram via `navigator.share`, Kakao SDK, PNG download) all reference the same 1080×1920 asset.
- Out: Backend quote extraction (already in ISSUE-056); share landing route (already in ISSUE-061 — only the image source URL changes).

### Acceptance Criteria (DoD)
- [ ] Given a saju reading ends with category=love, when the quote card renders client-side, then the border colour resolves to `#B7414B` and the card has `transform: rotate(-1.5deg)`.
- [ ] Given the server-side bake runs for category=money, when the resulting PNG is downloaded, then its dimensions are exactly 1080×1920 and the border colour at the pixel centre of the top edge is `#B68B3F` (±2 per channel for Pillow rendering tolerance).
- [ ] Given the quote card renders for category=tarot, when inspected, then a `<Seal hanja="月" tilt="right" />` exists in the DOM at the bottom-right corner.
- [ ] Given the user taps "인스타 공유" on iOS Safari, when triggered, then `navigator.share` is invoked with a 1080×1920 PNG file payload.
- [ ] Given a social crawler fetches `/share/[slug]`, when responded, then `og:image` points to `/api/og/[slug]` and the returned PNG matches the v2 spec (visual regression < 0.1%).
- [ ] Given the OG bake worker (Pillow) and the edge route (`@vercel/og`) render the same `quote_card_id`, when both PNGs are compared, then pixel diff is < 1% (acceptable rendering engine tolerance).

### Implementation Notes
- design_system.md §Components → QuoteCard v2; interactions.md §Flow F; wireframes.md (reading-end, tarot-end).
- The Pillow worker (ISSUE-058) is the authoritative cache; the edge route is a fallback for first-fetch latency. Keep both layouts in lockstep — extract layout constants into `og/layout_v2.json` consumed by both renderers.
- The `<Seal>` in the corner uses the FR-038 category mapping; do not duplicate the mapping table here.
- Grain overlay on the photo layer uses `--grain-strong` with `background-blend-mode: multiply`.

### Tests
- [ ] Vitest: borderline colour per category, tilt value, seal mapping.
- [ ] Playwright visual regression: 4 category variants × 2 surfaces (reading-end, tarot-end).
- [ ] Integration: queue OG bake → 1080×1920 PNG in R2 → fetch via `/api/og/[slug]` → pixel-compare against Pillow output (diff < 1%).
- [ ] Playwright e2e: each share affordance invokes the correct API with the correct asset URL.

### Rollback
- Feature-flag `QUOTE_CARD_V2=false`; system falls back to ISSUE-058/059 layout. Previous OG images remain valid (cache-busting only on new sessions).

---

## ISSUE-096: Per-screen navigation variants (vertical, bottom v2, hanja tab bar)
- Track: frontend
- UI: true
- Platform: web
- Manual: false
- PRD-Ref: FR-042
- Priority: P1
- Estimate: 1d
- Status: done
- Owner:
- Branch: feat/issue-096-nav-variants
- GH-Issue: https://github.com/pillip/voicesaju/issues/151
- PR: https://github.com/pillip/voicesaju/pull/152
- Depends-On: ISSUE-091, ISSUE-022

### Goal
Each v2 screen renders the correct navigation chrome per the wireframes: landing (brand + back only), category (`.nav-vertical`), reading-play (`.nav-bottom-v2`), my-page (hanja tab bar 家/命/月/我). Part of v2 (Ink, Amber & 印) refinement batch.

### Scope (In/Out)
- In: `web/components/nav/RouteShell.tsx` that picks a variant from `usePathname()` (or explicit prop); `nav-vertical` (writing-mode: vertical-rl, anchored left, 44px tap targets); `nav-bottom-v2` (sticky bottom, immersive, never overlaps subtitle band); `MyPageTabBar` (4 hanja tabs `家 命 月 我` mapped to `/me`, `/me/saju`, `/tarot`, `/me/profile`) with aria-labels (`"홈"`, `"사주"`, `"타로"`, `"마이"`); landing shell with only brand-mark + back.
- Out: Route-level routing logic (already in M1 Next.js skeleton).

### Acceptance Criteria (DoD)
- [ ] Given the user visits `/` (landing), when rendered, then no horizontal/vertical nav is present — only the brand mark (top-right) and a back affordance (top-left).
- [ ] Given the user visits `/reading/category`, when rendered, then `.nav-vertical` (writing-mode: vertical-rl) is anchored to the left edge with tap targets ≥ 44 px.
- [ ] Given the user is on `/reading/play`, when rendered, then `.nav-bottom-v2` is sticky to `bottom: 0` and does not overlap the subtitle band at 375 px height.
- [ ] Given the user navigates to `/me`, when rendered, then a 4-button tab bar shows `家 命 月 我` and each has an `aria-label` (홈/사주/타로/마이).
- [ ] Given a screen reader is active on the hanja tab bar, when focus lands on `家`, then "홈" is announced (not the hanja character).
- [ ] Given the user switches between screens within a session, when the route changes, then the nav variant updates without flash-of-wrong-chrome (no layout shift > 0.1 CLS).

### Implementation Notes
- design_system.md §Navigation; wireframes.md (landing, category, reading-play, my-page).
- `nav-vertical` is intentional friction for the Toss-funnel entry — the writing-mode: vertical-rl creates a deliberate slow-down moment; do not change.
- Tap-target spacing must satisfy NFR-012/013 even in vertical orientation.
- Implement variant selection via a small map (no monster switch); allow override via prop for special cases like the 404 page.

### Tests
- [ ] Vitest: route → variant resolution table.
- [ ] Playwright: visit each route, screenshot the nav region, assert presence/absence.
- [ ] axe-core: tap-target size + aria-label coverage on hanja tabs.

### Rollback
- Set a feature flag `NAV_V2=false` to render a single default top-nav across all screens (degraded but consistent).

---

## ISSUE-097: Copy tone system (`<HandwrittenPrice>`, `<HandwrittenNote>`, `<SignedMark>`, `<pause/>`, marker `<em>`)
- Track: frontend, content
- UI: true
- Platform: web
- Manual: false
- PRD-Ref: FR-043
- Priority: P1
- Estimate: 1d
- Status: done
- Owner: claude
- Branch: feat/issue-097-copy-tone (merged + deleted)
- GH-Issue: https://github.com/pillip/voicesaju/issues/153
- PR: https://github.com/pillip/voicesaju/pull/154 (merged ef1f6a1)
- Depends-On: ISSUE-091, ISSUE-092

### Goal
The "누님이 횡설수설" voice is operationalised as a small set of typographic components and a CSS layer so all screens render copy with the same tone. Part of v2 (Ink, Amber & 印) refinement batch.

### Scope (In/Out)
- In: `web/components/copy/HandwrittenPrice.tsx` (brush script, `rotate(-1.5deg)`, vermilion-500); `HandwrittenNote.tsx` (brush, tilt prop -1.5/-3); `SignedMark.tsx` (mincho italic "signed, 누님" + inline `<Seal hanja="明" size="sm" />`); `<Pause />` element (renders `<br data-pause>` with adjusted leading); global `@layer copy-system` CSS rule: `article em { background: linear-gradient(180deg, transparent 60%, rgba(155,42,26,0.22) 60%); }`; copy lint script `pnpm copy:lint` checking copy strings against `docs/copy_guide.md` voice matrix (placeholder rule set, extensible).
- Out: Wholesale copy rewrite across all existing screens (this issue ships the primitives; consumers adopt them as part of v2 screen refactors tracked separately).

### Acceptance Criteria (DoD)
- [ ] Given `<HandwrittenPrice value="4,900원" />`, when rendered, then the rendered text uses `var(--font-brush)` and `transform: rotate(-1.5deg)` with vermilion-500 colour.
- [ ] Given `<HandwrittenNote tilt={-3}>흠… 진심이긴 해</HandwrittenNote>`, when rendered, then computed `transform` includes `rotate(-3deg)`.
- [ ] Given `<SignedMark />` is rendered at the end of `/reading/play` and `/reading/end`, when inspected, then the DOM contains the text `signed, 누님` followed by a `<Seal hanja="明" size="sm" />`.
- [ ] Given `<article>` content with `<em>중요한 말</em>`, when rendered, then the `<em>` has a marker-style highlight via the global gradient rule.
- [ ] Given the landing 횡설수설 copy contains `<Pause />`, when rendered, then a visible line break is inserted with leading adjusted so the pause reads intentional (visual regression baseline).
- [ ] Given `pnpm copy:lint` runs, when copy strings violate the voice matrix (e.g., using formal speech 합니다 in informal contexts), then the script exits non-zero with the offending strings highlighted.

### Implementation Notes
- copy_guide.md §Voice & Tone; design_system.md §Typography.
- Keep `<SignedMark>` cheap to compose — it is mounted at the end of every reading and follow-up answer, so re-render cost matters; memoise the seal child.
- `pnpm copy:lint` v1 is a minimal regex-based linter against a deny-list (`습니다`, `해요체` mismatch, formal honorifics in spicy contexts); evolves into a richer rule set later.

### Tests
- [ ] Vitest: rotate values, font tokens, aria-label preservation.
- [ ] Storybook visual: tilt -1.5 / -3, all three components composed.
- [ ] CI smoke: `pnpm copy:lint` runs on every PR (non-blocking initially; flip to blocking once rule set stabilises).

### Rollback
- Replace components with plain `<span>` / `<br>`; tone consistency degrades but no functional regression.

---

## ISSUE-098: Tilted utilities + reveal-section fade-in pattern
- Track: frontend
- UI: true
- Platform: web
- Manual: false
- PRD-Ref: FR-044
- Priority: P2
- Estimate: 0.5d
- Status: backlog
- Owner:
- Branch:
- GH-Issue:
- PR:
- Depends-On: ISSUE-091

### Goal
Lightweight CSS utilities that operationalise the v2 "uncanny tilt" motif and the reveal-section fade-in used by FR-040 (tarot reveal) and FR-041 (quote card reveal). Part of v2 (Ink, Amber & 印) refinement batch.

### Scope (In/Out)
- In: `web/styles/utilities.css` additions — `.tilted { transform: rotate(-1.5deg); }`, `.tilted--right { transform: rotate(1.5deg); }`, `.tilted--more { transform: rotate(-3deg); }`, `.reveal-hidden { opacity: 0; visibility: hidden; transition: opacity .4s ease-out, visibility 0s linear .4s; }`, `.reveal-visible { opacity: 1; visibility: visible; transition: opacity .4s ease-out, visibility 0s linear 0s; }`, `.reveal-show-hide` ↔ `.reveal-hide` for footer hiding during reveal; `@keyframes tap-hint-pulse` (1.6s ease-in-out infinite, scale 1 → 1.04) and `.tap-hint { animation: tap-hint-pulse 1.6s ease-in-out infinite; }`; Storybook stories demonstrating each utility.
- Out: Wiring of these classes into specific screens (tarot reveal wiring is part of ISSUE-094; quote card wiring is part of ISSUE-095).

### Acceptance Criteria (DoD)
- [ ] Given an element with class `.tilted`, when rendered, then computed `transform` is `rotate(-1.5deg)`.
- [ ] Given an element transitions from `.reveal-hidden` → `.reveal-visible`, when measured, then opacity animates over ~400 ms and visibility flips to `visible` immediately.
- [ ] Given an element has `.tap-hint`, when rendered, then a 1.6 s scale pulse animation runs indefinitely; respecting `prefers-reduced-motion: reduce`, the animation is disabled.
- [ ] Given the user enables `prefers-reduced-motion: reduce`, when applied, then all `.tilted*` rotations are reduced to 0deg (or kept; documented decision: kept because tilt is identity, not motion) and reveal transitions skip the fade (instant show).
- [ ] Given `.reveal-show-hide` toggles to `.reveal-hide` on a footer element, when toggled, then the footer disappears without causing a layout shift > 0.1 CLS.

### Implementation Notes
- design_system.md §Utilities; interactions.md §Flow C, F.
- Document the `prefers-reduced-motion` decision in the CSS comment: tilt is treated as identity (not motion) and is preserved; only animated transitions and the pulse are suppressed.
- Keep utilities pure CSS — no JS bundle impact.

### Tests
- [ ] Vitest computed-style snapshot for each utility.
- [ ] Playwright: trigger reveal sequence, assert opacity timeline.
- [ ] Playwright with `--prefers-reduced-motion=reduce` flag: pulse animation absent, fade skipped.

### Rollback
- Remove the CSS additions; consumers in ISSUE-094 / ISSUE-095 will need to inline equivalent rules until restored.

---

# Mock Adapter Layer (Phase 1 PoC)

> Cross-cutting batch that introduces a Protocol/Adapter pattern so the entire app can run end-to-end without external API keys. These four adapters unblock parallel work on the M1/M2 vertical slice and let local development + CI run against deterministic fixtures. Real provider adapters (Toss, Kakao/Apple, Anthropic, Supertone) are added in Phase 2 when ISSUE-025/035/036/043/084/085 resume.

## ISSUE-099: Implement MockPaymentAdapter (fake checkout + auto-fire webhook)
- Track: backend
- UI: false
- Platform: web
- Manual: false
- PRD-Ref: FR-024
- Priority: P0
- Estimate: 0.5d
- Status: backlog
- Owner:
- Branch:
- GH-Issue:
- PR:
- Depends-On: ISSUE-001

### Goal
`app.adapters.payment.PaymentAdapter` Protocol exists and `MockPaymentAdapter` returns a fake `CheckoutSession` + auto-fires a success webhook after a 3s delay, selected by `PAYMENT_PROVIDER=mock`.

### Scope (In/Out)
- In: `api/voicesaju/adapters/payment.py` defining `PaymentAdapter` Protocol (`create_checkout_session`, `confirm_payment`, `refund`); `MockPaymentAdapter` returning `CheckoutSession(id=uuid7, redirect_url="#mock-success", amount_krw=<requested>)`; FastAPI BackgroundTasks scheduling a webhook POST to the internal handler after 3s with `status='succeeded'`; `TossPaymentAdapter` stub class raising `NotImplementedError` (Phase 2 placeholder); adapter selection via `settings.PAYMENT_PROVIDER` env var (default `mock`); also include `MockStorageAdapter` for local-fs audio/OG asset storage referenced by ISSUE-005 deferral note.
- Out: Real Toss client (deferred to Phase 2, see ISSUE-043), checkout UI changes (frontend continues calling the same `/api/payments/checkout` endpoint).

### Acceptance Criteria (DoD)
- [ ] Given `PAYMENT_PROVIDER=mock` is set, when `POST /api/payments/checkout {kind:"single", amount_krw:4900}` is called, then the response is `200` with `{session_id, redirect_url:"#mock-success", amount_krw:4900}`.
- [ ] Given a mock session is created at `t=0`, when `t=3s` passes, then the internal webhook handler runs and the matching `payments` row transitions to `status='succeeded'` with `paid_at` set.
- [ ] Given the pytest suite runs with `responses` (or `respx`) installed and `PAYMENT_PROVIDER=mock`, when the full payment flow test runs, then no external HTTP calls leave the process (asserted via the library's `assert_all_requests_are_fired=False` + zero outbound calls).
- [ ] Given `PAYMENT_PROVIDER=toss` is set without a real key, when the app boots, then `TossPaymentAdapter` raises `NotImplementedError` at first use (not at import time, to keep tests fast).

### Implementation Notes
- Place adapter under `api/voicesaju/adapters/payment.py`. Use FastAPI `BackgroundTasks` for the 3s webhook simulation (single-process; for the worker path, enqueue an arq job with `defer=3`).
- Adapter selection lives in `api/voicesaju/adapters/__init__.py` via a small factory reading `settings.PAYMENT_PROVIDER`. Keep the Protocol thin — only what the reading + tarot pipeline needs.
- The mock's `CheckoutSession.id` should be deterministic per `(user_id, idempotency_key)` so test assertions can pin to a known value.

### Tests
- [ ] `tests/unit/adapters/test_payment_mock.py::test_mock_creates_session_and_fires_webhook` (uses `freezegun` for the 3s delay).
- [ ] `tests/integration/payment/test_mock_flow.py::test_full_checkout_to_succeeded` exercising `/api/payments/checkout` → webhook → entitlement granted, asserting zero outbound HTTP via `responses`.

### Rollback
- Set `PAYMENT_PROVIDER` to an undefined value → factory raises a clear error at boot; revert to the existing payment endpoints once a real adapter ships.

---

## ISSUE-100: Implement MockAuthAdapter (pre-seeded test user, dev JWT)
- Track: backend
- UI: false
- Platform: web
- Manual: false
- PRD-Ref: FR-016, FR-017
- Priority: P0
- Estimate: 0.5d
- Status: backlog
- Owner:
- Branch:
- GH-Issue:
- PR:
- Depends-On: ISSUE-001

### Goal
`AuthAdapter` Protocol exists and `MockAuthAdapter` returns a pre-seeded user (`test_user_001`, email `test@voicesaju.dev`, signed dev JWT), selected by `AUTH_PROVIDER=mock`.

### Scope (In/Out)
- In: `api/voicesaju/adapters/auth.py` defining `AuthAdapter` Protocol (`start_login`, `complete_login`, `verify_token`); `MockAuthAdapter` returning a JWT signed by a dev secret (`MOCK_AUTH_JWT_SECRET`, gitignored) with payload `{sub:"test_user_001", email:"test@voicesaju.dev"}`; `KakaoAuthAdapter`, `AppleAuthAdapter`, `TossIdAdapter` stub classes raising `NotImplementedError`; adapter selection via `settings.AUTH_PROVIDER` (default `mock`); pytest startup fixture that seeds the `users` row for `test_user_001` if absent.
- Out: Real OAuth flows (deferred to Phase 2, see ISSUE-025), frontend login screen changes (existing button copies still apply but route through the mock adapter in dev).

### Acceptance Criteria (DoD)
- [ ] Given `AUTH_PROVIDER=mock` is set, when `GET /api/auth/login` is called, then the response includes a signed JWT whose `sub` claim equals `test_user_001`.
- [ ] Given a request includes `Authorization: Bearer <mock_jwt>`, when the auth middleware verifies it, then `request.state.user` is the seeded `test_user_001` row.
- [ ] Given the pytest suite runs with `AUTH_PROVIDER=mock`, when any auth-gated test executes, then zero outbound HTTP calls hit `kauth.kakao.com`, `appleid.apple.com`, or any Toss host (asserted via `responses`).
- [ ] Given the seeded user does not exist, when the startup fixture runs, then a `users` row with `id=test_user_001`, `email_hash=sha256("test@voicesaju.dev")`, `provider='mock'` is inserted idempotently.

### Implementation Notes
- File at `api/voicesaju/adapters/auth.py`. The Protocol mirrors the eventual real-provider interface so swapping to `KakaoAuthAdapter` later is a single env change.
- The JWT signing secret is a dev-only string read from `.env.local`; production must fail to boot if `AUTH_PROVIDER=mock` (guard in `config.py`).
- Seed the test user via an Alembic data migration or a pytest session-scoped fixture — prefer the fixture so the dev DB stays untouched by default.

### Tests
- [ ] `tests/unit/adapters/test_auth_mock.py::test_mock_login_returns_signed_jwt`.
- [ ] `tests/integration/auth/test_middleware_with_mock_jwt.py::test_verifies_and_attaches_user` (mocks the seeded user row).
- [ ] `tests/integration/auth/test_no_external_calls.py` asserts zero outbound HTTP during the full login + verify cycle.

### Rollback
- Switch `AUTH_PROVIDER` to a stub that always returns 503; affected endpoints degrade to logged-out state. Real adapter restores normal flow when ISSUE-025 resumes.

---

## ISSUE-101: Implement MockLLMAdapter (fixture-based saju/tarot responses)
- Track: backend
- UI: false
- Platform: web
- Manual: false
- PRD-Ref: FR-008, FR-009
- Priority: P0
- Estimate: 0.5d
- Status: backlog
- Owner:
- Branch:
- GH-Issue:
- PR:
- Depends-On: ISSUE-001

### Goal
`LLMAdapter` Protocol exists and `MockLLMAdapter` streams fixture text from `tests/fixtures/llm/{category}/{n}.txt` sentence-by-sentence with a 100ms delay between sentences (simulating Anthropic SSE), selected by `LLM_PROVIDER=mock`.

### Scope (In/Out)
- In: `api/voicesaju/adapters/llm.py` defining `LLMAdapter` Protocol (`stream(prompt, category, seed) -> AsyncIterator[str]`); `MockLLMAdapter` reading from `tests/fixtures/llm/{love,work,money}/{1,2,3}.txt` (3 per saju category) + `tests/fixtures/llm/tarot/{0..6}.txt` (7 daily-rotation fixtures); deterministic fixture selection via `hash(seed) % n_fixtures`; sentence splitting on `.?!` boundaries; `asyncio.sleep(0.1)` between sentences; `ClaudeAdapter` stub class raising `NotImplementedError`; selection via `settings.LLM_PROVIDER` (default `mock`).
- Out: Real Anthropic client (deferred to Phase 2, see ISSUE-035), guardrail integration (already in ISSUE-020 — applies regardless of adapter).

### Acceptance Criteria (DoD)
- [ ] Given `LLM_PROVIDER=mock` and `category="love"`, when `MockLLMAdapter.stream()` is awaited, then it yields fixture sentences in order with ~100ms between each (asserted via wall-clock measurement in a slow test, ±20ms).
- [ ] Given three calls with the same `seed` value, when the streams are compared, then each yields the identical fixture file content (deterministic selection).
- [ ] Given the pytest suite runs with `LLM_PROVIDER=mock`, when any reading or follow-up test executes, then zero outbound HTTP calls hit `api.anthropic.com` (asserted via `responses`).
- [ ] Given a fixture file is missing on disk, when `MockLLMAdapter.stream()` is called for that category, then a clear `FileNotFoundError` is raised at the first yield (not silently swallowed).

### Implementation Notes
- File at `api/voicesaju/adapters/llm.py`. Fixtures match the voice rules in `docs/copy_guide.md` (시니컬 누님 for saju, 노인 도사 for tarot).
- Sentence splitter: prefer a simple regex `re.split(r"(?<=[.?!])\s+", text)` for v1; upgrade to a Korean-aware splitter only if the deny-list integration test reveals issues.
- The 100ms inter-sentence delay simulates Anthropic SSE pacing so the chunked audio player (ISSUE-033) and SSE pipeline (ISSUE-039) exercise their timing-sensitive paths in tests.

### Tests
- [ ] `tests/unit/adapters/test_llm_mock.py::test_streams_fixture_with_100ms_pacing` (uses `pytest.mark.asyncio` + monotonic clock).
- [ ] `tests/unit/adapters/test_llm_mock.py::test_deterministic_selection_by_seed`.
- [ ] `tests/integration/llm/test_no_anthropic_calls.py` asserts zero `api.anthropic.com` traffic during a full reading pipeline run with the mock adapter.

### Rollback
- Switch `LLM_PROVIDER` to a stub returning a single hardcoded sentence; reading pipeline degrades to a static message. Real Claude adapter restores normal flow when ISSUE-035 resumes.

---

## ISSUE-102: Implement MockTTSAdapter (pre-baked silent MP3 chunks)
- Track: backend
- UI: false
- Platform: web
- Manual: false
- PRD-Ref: FR-010, NFR-002
- Priority: P0
- Estimate: 0.5d
- Status: backlog
- Owner:
- Branch:
- GH-Issue:
- PR:
- Depends-On: ISSUE-001

### Goal
`TTSAdapter` Protocol exists and `MockTTSAdapter` streams 10 pre-baked silent MP3 chunks (200ms each, ~2s total per request) at a realistic 200ms inter-chunk rate, selected by `TTS_PROVIDER=mock`.

### Scope (In/Out)
- In: `api/voicesaju/adapters/tts.py` defining `TTSAdapter` Protocol (`stream(text, voice_id) -> AsyncIterator[bytes]`); `MockTTSAdapter` reading a single `tts_fixtures/silent.mp3` (~200ms, ~3 KB silent MP3) shipped alongside the module and yielding 10 copies with `asyncio.sleep(0.2)` between each; `SupertoneAdapter` stub raising `NotImplementedError`; selection via `settings.TTS_PROVIDER` (default `mock`); a small assertion at adapter load time that the fixture MP3 is present and parseable (via `mutagen` or raw header check).
- Out: Real Supertone client (deferred to Phase 2, see ISSUE-036), chunk-to-R2 upload pipeline (already in ISSUE-038, runs against MockStorageAdapter for Phase 1).

### Acceptance Criteria (DoD)
- [ ] Given `TTS_PROVIDER=mock` is set, when `MockTTSAdapter.stream(text, voice_id="nuna")` is awaited, then it yields exactly 10 byte chunks (one per `async for`).
- [ ] Given the 10 yielded chunks are concatenated into a single buffer and written to disk, when played in `ffplay` or via the browser `<audio>` element, then the resulting file is a valid playable MP3 of ~2s silence (no decoder errors).
- [ ] Given the pytest suite runs with `TTS_PROVIDER=mock`, when any TTS-touching test executes, then zero outbound HTTP calls hit Supertone hosts (asserted via `responses`).
- [ ] Given the inter-chunk pacing is measured, when 10 chunks complete, then the total elapsed wall-clock time is ≥ 1.8s and ≤ 2.4s (10 × 200ms ± tolerance for scheduler jitter).

### Implementation Notes
- Ship a single ~200ms silent MP3 in `api/voicesaju/adapters/tts_fixtures/silent.mp3`. Generate with `ffmpeg -f lavfi -i anullsrc=r=22050:cl=mono -t 0.2 -c:a libmp3lame silent.mp3` and commit the binary (≤ 3 KB).
- The 200ms pacing is intentional — it lets the chunked audio player (ISSUE-033) and the SSE first-chunk latency budget (NFR-002) be exercised against realistic timing in tests.
- Adapter file at `api/voicesaju/adapters/tts.py`. The Protocol is shared with `SupertoneAdapter` so swapping to the real provider is a single env change.

### Tests
- [ ] `tests/unit/adapters/test_tts_mock.py::test_yields_ten_chunks`.
- [ ] `tests/unit/adapters/test_tts_mock.py::test_concatenated_chunks_form_valid_mp3` (validates the magic bytes + decodes with `mutagen`).
- [ ] `tests/integration/tts/test_no_supertone_calls.py` asserts zero outbound HTTP during a full reading pipeline run.

### Rollback
- Switch `TTS_PROVIDER` to a stub returning zero chunks; the audio pipeline falls through to the subtitle-only fallback already implemented in ISSUE-033 / FR-034. Real Supertone adapter restores normal flow when ISSUE-036 resumes.

---

# Self-Review Summary

## Requirement coverage
- **All 17 user stories (US-01..US-17) mapped**: US-01→028,029; US-02→024,027,062; US-03→030,032,039,042; US-04→041,045 (followup UI in ISSUE-045 covered as part of session-end since separate followup screen is just state of /reading/play); US-05→064; US-06→047,049,050,051; US-07→050; US-08→057,058,059; US-09→044; US-10→046; US-11→070; US-12→067,068; US-13→026,027; US-14→046; US-15→063,029; US-16→065,066; US-17→071.
- **All 36 FRs covered**: FR-001..FR-036 each have at least one issue in scope. FR-008 character illustration is part of ISSUE-042 (display during playback).
- **All 17 NFRs addressed**: NFR-001..NFR-004 via pipeline (039,041,049,051) + observability (077,089); NFR-005 via encryption (009,010); NFR-006 via Toss integration (044,045); NFR-007/008 via cost tracker (034) + budget alerts (089); NFR-009 via observability + payment webhook (045,089); NFR-010 via deny-list (020) + telemetry (018); NFR-011 via 077; NFR-012/013 via design system (021,022) + axe-core in CI; NFR-014 via mobile-first responsive (021); NFR-015 via chunked audio (033); NFR-016 via uptime + healthcheck (087); NFR-017 via saju regression (012).
- **Followup-screen separation**: US-04 follow-up phase UI is part of ISSUE-042 (/reading/play extends state) + ISSUE-041 (backend). No separate frontend issue created — kept simple per ux_spec Screen 10 note "shares /reading/play route".

## Dependency graph validation
- Critical path: ISSUE-001 → 006 → 007 → 008/009 → 010 → 011/012 → 029 → 034/037 → 039 → 042 (saju reading working end-to-end). ~14 issues, all 0.5d–1.5d.
- Parallel tracks: M1 design system (021,022) parallel to backend foundations; frontend onboarding (028) parallel to backend profile API (029); Anthropic + Supertone manual setup (035,036) parallel to client code (034,037).
- No circular dependencies. Dependency depth ≤ 4 throughout.

## Sizing re-check
- All issues 0.5d–1.5d. ISSUE-066 (history player + endpoint combined) is 1d because the backend route is small. ISSUE-071 (edit-saju + PATCH) is 1.5d covering both ends but tightly scoped. ISSUE-039 (reading pipeline) is 1.5d — the core integration work; could split into "scaffold + SSE" + "LLM/TTS wiring" if it grows, but acceptable as 1.5d given dependencies are isolated.

## AC testability
- Every AC uses Given/When/Then. Latency targets reference specific NFRs. Edge cases (network drop, payment failure, LLM failure) have dedicated AC.

## Confidence rating
**High.** All FRs and user stories map to issues; dependencies form a sensible DAG; sizing fits the 0.5d–1.5d window. Open variables (A-01 pricing, A-04 Toss WebView, DEP-01 Supertone) are surfaced as manual setup issues (ISSUE-036, 043, 046) so code work can proceed in parallel with mocks. No requirements left orphaned.

## Addendum (2026-05-28) — Mock Adapter Layer + Deferred items
- **ISSUE-099..102 (Mock adapters)** add a Protocol/Adapter layer (Payment, Auth, LLM, TTS) so the full M1 + M2 vertical slice runs against deterministic fixtures with zero external HTTP. Each is 0.5d / P0 / depends only on ISSUE-001 — they can be picked up in parallel immediately after backend bootstrap.
- **Deferred to Phase 2 (Status: deferred)**: ISSUE-005 (R2), ISSUE-025 (Kakao/Apple OAuth), ISSUE-035 (Anthropic), ISSUE-036 (Supertone), ISSUE-043 (Toss), ISSUE-084 (Fly.io), ISSUE-085 (Vercel). These remain in the doc as Phase 2 reference but are out of scope for the v1 PoC.
- **ISSUE-004 reclassified**: Manual setup → non-manual (Postgres + Redis now ship as docker-compose containers from ISSUE-001).
- **Dependency redirects**: ISSUE-026 (Kakao/Apple OAuth backend) now depends on ISSUE-100; ISSUE-032 (intro player) on ISSUE-101; ISSUE-044 (Toss checkout endpoint) on ISSUE-099. ISSUE-100 already supplies a verified `request.state.user` and ISSUE-099 already supplies a `payments.status='succeeded'` transition, so downstream contracts are preserved.
- **Counts**: Total 102 issues (98 + 4 new mock adapters); 7 deferred; 2 remaining manual (ISSUE-084, ISSUE-085, both deferred).
