# Data Model — VoiceSaju

Version: 1.0
Source documents: `PRD.md` (2026-05-29), `docs/prd_digest.md`, `docs/requirements.md`, `docs/ux_spec.md`, `docs/architecture.md`, `docs/brainstorm_notes.md`, `docs/business_analysis.md`
Data-modeler confidence: **High** for entity coverage and access pattern derivation; **Medium** on a few specifics noted in §11 (audio retention policy A-07, exact pricing A-01) — both are config/seed concerns, not schema concerns.

> Authoritative for: tables, columns, constraints, indexes, encryption envelope structure, migration policy, seed data, query patterns, retention.
> Defers to architecture for: which service runs what, KMS provider choice, hosting region.

---

## 1. Storage Strategy

### 1.1 Primary storage — PostgreSQL 16

Chosen by `architecture.md §2`. Reinforced by access patterns derived in §3:

- **Strong relational integrity** for User ↔ Profile ↔ SajuChart ↔ Reading ↔ Payment chain. All transactional, all need FK enforcement.
- **JSONB** for `SajuChart.pillars` (variable structure: 4 pillars with stems/branches/elements/ten gods nested) — avoids 30+ scalar columns while keeping queryability via JSONB operators.
- **Partial / compound indexes** for cheap quota and idempotency lookups.
- **pgcrypto** is available but unused; column encryption is **application-level envelope encryption** (NFR-005) so the KMS-wrapped DEK stays outside Postgres.
- **Two-phase commit not required** — payments cross only the Toss boundary (idempotent webhook + receipt), not multiple internal services.

### 1.2 Secondary storage — Redis 7

Per `architecture.md §2, §11`. Three concerns:

1. **Session store** (`vs_sess:<sid>` → user_id, TTL 30d rolling).
2. **Idempotency / rate-limit / deterministic cache** (paywall, tarot seed, reading start).
3. **Worker broker** (arq queue for OG bake, refund retry, audio finalize).

### 1.3 Object storage — Cloudflare R2

- **Reading audio** (`audio/readings/{reading_id}/main.mp3`, `.../followup_{n}.mp3`) — FR-028 replay path; large blobs.
- **Tarot audio** (`audio/tarot/{tarot_id}.mp3`).
- **Quote card OG images** (`og/{quote_card_id}.png`) — 1080×1920, served behind signed URL.
- **Static deck assets** (`static/tarot/cards/{0..21}.png`, `static/intro_audio/{category}/{voice_id}.mp3`) — versioned, public-readable via signed URLs.

Postgres stores **R2 keys + content hashes**, never blob bytes.

### 1.4 Why not other stores

- No search index (Elasticsearch/Meilisearch) — no full-text search access pattern exists in v1.
- No dedicated time-series DB — observability sends metrics to Grafana Cloud directly (§ architecture 12).
- No graph DB — only one weak many-to-many (none, actually) exists.

---

## 2. Naming and Type Conventions

| Convention | Choice | Rationale |
|------------|--------|-----------|
| Primary keys | `id` = `UUID` (uuidv7 generated app-side) | Time-ordered for index locality, opaque for URLs, no global counter contention. |
| FK column naming | `<entity>_id` | Explicit, joinable. |
| Timestamps | `TIMESTAMPTZ` (UTC), columns `created_at`, `updated_at` | All times stored UTC; KST conversion at query-time for `date_kst` fields. |
| Soft delete | `deleted_at TIMESTAMPTZ NULL` | Only on `users` and `profiles` (GDPR/PIPA undo grace window). All other tables hard-delete or cascade. |
| Enums | Postgres native `ENUM` for closed sets that rarely change (`category`, `payment_status`, `reading_status`) | Type-safe; mutating enum requires migration (intentional friction). |
| Money | `INTEGER` storing whole KRW (no fractional won) | KRW has no minor unit; avoids float drift. Column suffix `_krw`. |
| Booleans | `BOOLEAN NOT NULL DEFAULT FALSE/TRUE` | Never nullable. |
| Idempotency keys | `TEXT` UUIDv4/v7 from client | Used in unique indexes. |
| Hashes | `CHAR(64)` for SHA-256 hex | Fixed-width, predictable. |

---

## 3. Access Patterns

Every access pattern below is derived from a UX screen, a flow step, or a back-end pipeline stage. Frequency is **rough order-of-magnitude** at the 12-month target (50k signups / ~20k MAU). Latency targets come from NFRs.

### 3.1 Authentication & Identity

| # | Pattern | Source | Op | Frequency | Latency Target |
|---|---------|--------|-----|-----------|----------------|
| AP-01 | Resolve session cookie → User | Every authed request | Read (Redis primary) | very high | ≤ 5 ms |
| AP-02 | Lookup User by `kakao_sub` (OAuth callback) | Flow G step 5 (signup); web login | Read | medium | ≤ 20 ms |
| AP-03 | Lookup User by `apple_sub` | Web login | Read | medium | ≤ 20 ms |
| AP-04 | Lookup User by `toss_id` (bridge handshake) | Flow E init; US-14 | Read | medium | ≤ 20 ms |
| AP-05 | Create User (new signup) — provider-linked | Flow G | Insert | low | ≤ 50 ms |
| AP-06 | Lookup or upsert Device by `device_id_client` | Anonymous landing, FR-003 | Read + Upsert | very high | ≤ 10 ms |
| AP-07 | Link Device → User on signup (migrate non-member state) | Flow G step 5 | Update | low | ≤ 20 ms |
| AP-08 | Soft-delete account (GDPR/PIPA right-to-erasure) | `/me/account` | Update + cascade scheduling | very low | ≤ 200 ms |

### 3.2 Profile & Saju Chart

| # | Pattern | Source | Op | Frequency | Latency Target |
|---|---------|--------|-----|-----------|----------------|
| AP-09 | Read current Profile for signed-in user | `/me`, `/reading/category`, paywall personalization | Read | high | ≤ 20 ms |
| AP-10 | Create Profile on first onboarding submit | Flow A step 5 → API `POST /api/v1/profile` | Insert (encrypted columns) | low | ≤ 50 ms |
| AP-11 | Compute (or cache-hit) SajuChart by `chart_hash` | `POST /api/v1/profile`, `PATCH /api/v1/profile` | Read+Insert | low | ≤ 100 ms (engine), ≤ 5 ms cache hit |
| AP-12 | Read current SajuChart for User (latest) | `/me/saju`, reading pipeline | Read | high | ≤ 20 ms |
| AP-13 | Read historical SajuChart by `id` (for `Reading.chart_id`) | History replay | Read | medium | ≤ 20 ms |
| AP-14 | Update Profile and bump correction counter (FR-029) | Flow H step 5 | Update + Insert SajuChart | very low | ≤ 100 ms |
| AP-15 | Check correction counter (FR-029 enforcement) | `/me/edit-saju` load | Read | low | ≤ 10 ms |

### 3.3 Entitlement & Free Tokens

| # | Pattern | Source | Op | Frequency | Latency Target |
|---|---------|--------|-----|-----------|----------------|
| AP-16 | List active FreeTokens for User | `/reading/paywall` load | Read | high | ≤ 20 ms |
| AP-17 | Read FreeToken for Device (non-member trial) | `/reading/paywall` non-member | Read | medium | ≤ 20 ms |
| AP-18 | Grant signup free token (idempotent) | Flow G step 5 | Insert | low | ≤ 30 ms |
| AP-19 | Grant non-member trial token on first onboarding | Flow A step 6 (intro) | Insert | medium | ≤ 30 ms |
| AP-20 | Consume FreeToken (mark `consumed_at`) | Flow A step 8; reading start | Update | medium | ≤ 30 ms |
| AP-21 | Check active Subscription for User | `/reading/paywall`, `/tarot/paywall` | Read | high | ≤ 20 ms |
| AP-22 | Count lifetime single-purchase Payments (FR-025 upsell trigger) | After every Payment row insert | Read | medium | ≤ 20 ms |

### 3.4 Reading Flow (Saju + Follow-ups)

| # | Pattern | Source | Op | Frequency | Latency Target |
|---|---------|--------|-----|-----------|----------------|
| AP-23 | Create Reading on entitlement validation | `POST /api/v1/reading` | Insert (idempotent) | medium | ≤ 30 ms |
| AP-24 | Update Reading status (queued → streaming → done → failed/refunded) | Reading pipeline state machine | Update | medium | ≤ 20 ms |
| AP-25 | Persist ReadingTranscript (main text) | End of LLM stream | Insert | medium | ≤ 30 ms |
| AP-26 | Append FollowUp entry to Reading | Each FR-010 tap | Insert | medium | ≤ 30 ms |
| AP-27 | Read Reading + Transcript + Audio key for replay | `/me/history/[id]` | Read (1 JOIN) | medium | ≤ 50 ms |
| AP-28 | List User's past Readings paginated | `/me/history` | Read (range scan) | medium | ≤ 50 ms for 20 rows |
| AP-29 | Persist final R2 audio key after worker stitch | arq `finalize_audio` job | Update | medium | ≤ 30 ms |
| AP-30 | Aggregate cost_krw per Reading (NFR-007 monitor) | Cost tracker | Update (additive) | medium | ≤ 20 ms |

### 3.5 Daily Tarot

| # | Pattern | Source | Op | Frequency | Latency Target |
|---|---------|--------|-----|-----------|----------------|
| AP-31 | Lookup today's TarotDraw for User|Device + date_kst (idempotency) | `/tarot` load, Flow C step 1 | Read | high | ≤ 10 ms |
| AP-32 | Create TarotDraw on first flip of the day | Flow C step 3 | Insert (unique constraint) | medium | ≤ 30 ms |
| AP-33 | Weekly free-quota count (FR-014) for User|Device | `/tarot` banner, before flip | Read | high | ≤ 10 ms (Redis-backed) |
| AP-34 | Persist TarotDraw transcript + audio key | End of tarot pipeline | Update | medium | ≤ 30 ms |

### 3.6 Payment & Subscription

| # | Pattern | Source | Op | Frequency | Latency Target |
|---|---------|--------|-----|-----------|----------------|
| AP-35 | Create pending Payment on checkout | `POST /api/v1/payments/checkout` | Insert | medium | ≤ 30 ms |
| AP-36 | Confirm Payment by `toss_payment_key` (webhook) | Toss → us | Update (idempotent by unique key) | medium | ≤ 50 ms |
| AP-37 | Lookup Payment by `toss_order_id` for client confirm redirect | `/payments/confirm` | Read | medium | ≤ 10 ms |
| AP-38 | Insert/Update Subscription on `subscription.created` webhook | Toss recurring billing event | Upsert | low | ≤ 50 ms |
| AP-39 | List Payments for User (history) | `/me/billing` | Read (range scan, desc) | medium | ≤ 50 ms for 20 rows |
| AP-40 | Mark Subscription `cancel_at_period_end` | Flow I | Update | low | ≤ 30 ms |
| AP-41 | Refund: insert Refund row + flip Payment status | FR-023 auto-refund worker | Update + Insert | low | ≤ 50 ms |

### 3.7 Quote Card & Share

| # | Pattern | Source | Op | Frequency | Latency Target |
|---|---------|--------|-----|-----------|----------------|
| AP-42 | Create QuoteCard row at session end (extracted quote line + R2 key placeholder) | Reading/Tarot pipeline end | Insert | medium | ≤ 30 ms |
| AP-43 | Read QuoteCard by public `share_slug` | `/share/[cardId]` SSR | Read | medium | ≤ 10 ms (often Redis-cached) |
| AP-44 | Update QuoteCard with finalized R2 key after worker bake | arq `og_bake` | Update | medium | ≤ 30 ms |

### 3.8 Content (immutable seed-data)

| # | Pattern | Source | Op | Frequency | Latency Target |
|---|---------|--------|-----|-----------|----------------|
| AP-45 | Lookup TarotCard metadata by index (0..21) | Tarot pipeline | Read | high | ≤ 5 ms (in-mem cached) |
| AP-46 | Lookup IntroAudioClip for (category, voice_id) | `/reading/intro` | Read | high | ≤ 10 ms |
| AP-47 | Lookup CharacterVoice for character_key (`nuna` / `dosa`) | TTS dispatch | Read | very high | ≤ 5 ms |
| AP-48 | Read current TonePromptVersion for prompt_key | Every LLM call | Read | very high | ≤ 5 ms (in-mem cached) |

### 3.9 Tone Guardrail Telemetry

| # | Pattern | Source | Op | Frequency | Latency Target |
|---|---------|--------|-----|-----------|----------------|
| AP-49 | Insert ToneViolationEvent (deny-list / moderation hit) | LLM streaming guardrail | Insert | low (target) | ≤ 30 ms |
| AP-50 | Rollup tone violations per session (NFR-010 monitor) | Daily metrics job | Read (aggregation) | low | < 5 s |

### 3.10 Tone Regression Set (LLM CI Gate)

| # | Pattern | Source | Op | Frequency | Latency Target |
|---|---------|--------|-----|-----------|----------------|
| AP-51 | Read all ToneEvalCase rows for current version | CI pre-deploy job (FR-032) | Read | very low (CI only) | < 2 s for ≥ 50 rows |
| AP-52 | Insert ToneEvalCase (new test case authoring) | Internal tooling | Insert | very low | ≤ 50 ms |

### 3.11 Audit & Compliance

| # | Pattern | Source | Op | Frequency | Latency Target |
|---|---------|--------|-----|-----------|----------------|
| AP-53 | Insert AuditEvent for PII access, GDPR action, refund | various | Insert | low | ≤ 30 ms |
| AP-54 | Cascade delete on hard erasure (GDPR right-to-be-forgotten) | Scheduled erasure worker | Delete (batched) | very low | best-effort |

---

## 4. Schema

All tables in schema `public`. Postgres-version-pinned features (`uuidv7`, `IDENTITY`, `GENERATED ALWAYS`) noted where used. Encryption flag column key:

- **`enc:envelope`** — column stores AES-256-GCM envelope (`{ciphertext, iv, tag, wrapped_dek, kek_version}` as JSONB). Plaintext **never** stored. Decryption requires KMS Decrypt of `wrapped_dek`.
- **`enc:none`** — plaintext, not classified sensitive PII.

### 4.1 Enums

```sql
CREATE TYPE gender_enum         AS ENUM ('F','M');
CREATE TYPE category_enum       AS ENUM ('love','work','money');
CREATE TYPE reading_status_enum AS ENUM ('queued','streaming','done','failed','refunded','cancelled');
CREATE TYPE tarot_status_enum   AS ENUM ('streaming','done','failed');
CREATE TYPE payment_type_enum   AS ENUM ('single','subscription_initial','subscription_recurring');
CREATE TYPE payment_method_enum AS ENUM ('tosspay','kakaopay');
CREATE TYPE payment_status_enum AS ENUM ('pending','paid','failed','refunded','partially_refunded');
CREATE TYPE subscription_status_enum AS ENUM ('active','cancel_at_period_end','cancelled','past_due');
CREATE TYPE free_token_kind_enum AS ENUM (
  'nonmember_trial',       -- FR-003
  'signup_grant',          -- FR-017
  'failure_compensation',  -- FR-023 fallback (refund failed)
  'ops_grant'              -- manual ops credit
);
CREATE TYPE auth_provider_enum  AS ENUM ('kakao','apple','toss');
CREATE TYPE character_key_enum  AS ENUM ('nuna','dosa');
CREATE TYPE tone_eval_label_enum AS ENUM ('ok','violation');
CREATE TYPE audit_action_enum   AS ENUM (
  'profile_read','profile_update','soft_delete','hard_delete',
  'payment_refund','correction_used','export_data'
);
```

### 4.2 Table: `users`

Identity root. One row per VoiceSaju account.

| Column | Type | Constraints | Default | Enc | Description |
|--------|------|-------------|---------|-----|-------------|
| `id` | UUID | PK | `uuidv7()` (app) | enc:none | Account identifier. |
| `kakao_sub` | TEXT | UNIQUE (partial) | NULL | enc:none | Kakao OAuth `sub` claim. UNIQUE only WHERE NOT NULL. |
| `apple_sub` | TEXT | UNIQUE (partial) | NULL | enc:none | Apple `sub` claim. UNIQUE only WHERE NOT NULL. |
| `toss_id` | TEXT | UNIQUE (partial) | NULL | enc:none | Toss bridge identifier. UNIQUE only WHERE NOT NULL. |
| `email_hash` | CHAR(64) | NULL | NULL | enc:none | SHA-256(lower(email)) for duplicate-detection across providers (FR-016). Email itself not stored. |
| `display_locale` | TEXT | NOT NULL | `'ko-KR'` | enc:none | Reserved for future i18n. |
| `created_at` | TIMESTAMPTZ | NOT NULL | `now()` | enc:none | |
| `updated_at` | TIMESTAMPTZ | NOT NULL | `now()` | enc:none | |
| `last_seen_at` | TIMESTAMPTZ | NULL | NULL | enc:none | Updated by session middleware (lazy, ≤ 1/h). |
| `deleted_at` | TIMESTAMPTZ | NULL | NULL | enc:none | Soft delete; hard-delete after 30d via scheduled worker. |

Constraints / invariants:

- `CHECK (kakao_sub IS NOT NULL OR apple_sub IS NOT NULL OR toss_id IS NOT NULL)` — every user must have ≥ 1 external identity.
- At least one of the three provider columns is non-null on insert.

Cascades:

- Most child rows do **not** cascade on `users.id` delete; instead the GDPR worker walks them in a defined order to log each deletion in `audit_events` (§4.16).

### 4.3 Table: `auth_identities` (optional v1.1; v1 keeps provider columns inline on `users`)

> **Design note**: We keep `kakao_sub`, `apple_sub`, `toss_id` inline on `users` in v1 (only 3 providers, no risk of explosion). This avoids a JOIN on every login (AP-02/03/04). When a 4th provider is added, this table is introduced and the inline columns are migrated.

### 4.4 Table: `devices`

Non-member identity (FR-003, FR-013 for non-members).

| Column | Type | Constraints | Default | Enc | Description |
|--------|------|-------------|---------|-----|-------------|
| `id` | UUID | PK | `uuidv7()` | enc:none | Server-issued device id. |
| `device_id_client` | UUID | UNIQUE NOT NULL | — | enc:none | Client-generated UUID from `localStorage`. |
| `linked_user_id` | UUID | FK `users(id)` ON DELETE SET NULL | NULL | enc:none | Set when device's owner signs up. |
| `first_seen_at` | TIMESTAMPTZ | NOT NULL | `now()` | enc:none | |
| `last_seen_at` | TIMESTAMPTZ | NOT NULL | `now()` | enc:none | |
| `user_agent_hash` | CHAR(64) | NULL | NULL | enc:none | SHA-256(UA) — diagnostic only, not for fingerprinting. |

### 4.5 Table: `profiles`

User-supplied saju input. **Birth fields encrypted.**

| Column | Type | Constraints | Default | Enc | Description |
|--------|------|-------------|---------|-----|-------------|
| `id` | UUID | PK | `uuidv7()` | enc:none | |
| `user_id` | UUID | UNIQUE NOT NULL FK `users(id)` | — | enc:none | One profile per user. |
| `birth_dt_enc` | JSONB | NOT NULL | — | **enc:envelope** | Envelope of birth `datetime` (UTC `YYYY-MM-DDTHH:MM:00`). When `birth_time_unknown=true`, plaintext is `YYYY-MM-DDT00:00:00` and the `time_known` flag below distinguishes. See §4.20 envelope structure. |
| `birth_is_lunar` | BOOLEAN | NOT NULL | `false` | enc:none | Toggle from onboarding step 1. |
| `birth_time_known` | BOOLEAN | NOT NULL | `true` | enc:none | Inverse of FR-001 "모름" checkbox. Stored explicitly for queryability without decrypt. |
| `gender` | gender_enum | NOT NULL | — | enc:none | |
| `name_optional` | TEXT | NULL CHECK (`char_length(name_optional) <= 10`) | NULL | enc:none | FR-001 optional name; per architecture §5.3 not classified PII. |
| `correction_count` | SMALLINT | NOT NULL CHECK (`correction_count BETWEEN 0 AND 2`) | `0` | enc:none | FR-029 enforcement. Increments on `PATCH /profile`. |
| `created_at` | TIMESTAMPTZ | NOT NULL | `now()` | enc:none | |
| `updated_at` | TIMESTAMPTZ | NOT NULL | `now()` | enc:none | |
| `deleted_at` | TIMESTAMPTZ | NULL | NULL | enc:none | Mirrors `users.deleted_at` for hot-path checks without join. |

Invariants:

- `correction_count` server-enforced (FR-029 AC).
- `birth_dt_enc.ciphertext` length stable (DEK rotation re-wraps DEK only; ciphertext untouched).

### 4.6 Table: `saju_charts`

Computed 명식 (immutable per generation). New row inserted on profile change (FR-029) so historical `readings` keep pointing at the chart that generated them.

| Column | Type | Constraints | Default | Enc | Description |
|--------|------|-------------|---------|-----|-------------|
| `id` | UUID | PK | `uuidv7()` | enc:none | |
| `user_id` | UUID | NOT NULL FK `users(id)` | — | enc:none | |
| `chart_hash` | CHAR(64) | NOT NULL UNIQUE | — | enc:none | SHA-256 of `(birth_dt_plain + is_lunar + gender + time_known + ENGINE_VERSION)`. Computed inside encryption boundary; only the hash is stored, not the plaintext. Enables cache reuse across users with identical input. |
| `engine_version` | TEXT | NOT NULL | — | enc:none | E.g., `'saju.v1.2026-05'` from architecture §9.2. |
| `pillars` | JSONB | NOT NULL | — | enc:none | `{year:{stem,branch,element,ten_god},month:{...},day:{...},hour:{...}|null,five_elements_summary:{...},ten_gods_summary:{...}}` |
| `time_known` | BOOLEAN | NOT NULL | `true` | enc:none | Denormalized from profile for queries that don't join. |
| `created_at` | TIMESTAMPTZ | NOT NULL | `now()` | enc:none | |

Invariants:

- `pillars.hour IS NULL` ⇔ `time_known = false` (validated at insert via app-level check; optional DB-level CHECK as `(time_known) = (pillars ? 'hour' AND pillars->'hour' IS NOT NULL)` — drop if it conflicts with JSONB null semantics).
- Per architecture §9.4, this row also acts as the **LLM prompt-cache key** input via `chart_hash`.

### 4.7 Table: `free_tokens`

Currency for the paywall. One row = one redemption credit.

| Column | Type | Constraints | Default | Enc | Description |
|--------|------|-------------|---------|-----|-------------|
| `id` | UUID | PK | `uuidv7()` | enc:none | |
| `user_id` | UUID | NULL FK `users(id)` | NULL | enc:none | Either user_id OR device_id is set (NOT both, NOT neither). |
| `device_id` | UUID | NULL FK `devices(id)` | NULL | enc:none | Set for FR-003 non-member trial. |
| `kind` | free_token_kind_enum | NOT NULL | — | enc:none | |
| `consumed_at` | TIMESTAMPTZ | NULL | NULL | enc:none | NULL = available. |
| `consumed_by_reading_id` | UUID | NULL FK `readings(id)` ON DELETE SET NULL | NULL | enc:none | Audit trail. |
| `created_at` | TIMESTAMPTZ | NOT NULL | `now()` | enc:none | |
| `expires_at` | TIMESTAMPTZ | NULL | NULL | enc:none | v1: NULL (no expiry per FR-017 AC). Reserved for v2. |

Constraints:

- `CHECK ((user_id IS NULL) <> (device_id IS NULL))` — exactly one owner.
- **Idempotent signup grant**: `UNIQUE (user_id, kind) WHERE kind = 'signup_grant'` — one grant per account (FR-017 AC).
- **Idempotent non-member trial grant**: `UNIQUE (device_id, kind) WHERE kind = 'nonmember_trial'` — one per device (FR-003 AC).

### 4.8 Table: `readings`

One row per saju reading session (paid, free-token, or subscription-redeemed).

| Column | Type | Constraints | Default | Enc | Description |
|--------|------|-------------|---------|-----|-------------|
| `id` | UUID | PK | `uuidv7()` | enc:none | |
| `user_id` | UUID | NOT NULL FK `users(id)` | — | enc:none | Non-members complete on `device` then this is set on signup-during-flow; if signup never happens the row is still owned by the device. (See `device_id` below for non-member trials.) |
| `device_id` | UUID | NULL FK `devices(id)` | NULL | enc:none | Set when reading was started by a non-member; NULLed when device is linked to a user. |
| `chart_id` | UUID | NOT NULL FK `saju_charts(id)` | — | enc:none | Snapshot of chart used; survives FR-029 corrections. |
| `category` | category_enum | NOT NULL | — | enc:none | FR-004. |
| `entitlement_kind` | TEXT | NOT NULL CHECK (`entitlement_kind IN ('payment','subscription','free_token')`) | — | enc:none | What unlocked it. |
| `payment_id` | UUID | NULL FK `payments(id)` | NULL | enc:none | Set when `entitlement_kind='payment'`. |
| `subscription_id` | UUID | NULL FK `subscriptions(id)` | NULL | enc:none | Set when `entitlement_kind='subscription'`. |
| `free_token_id` | UUID | NULL FK `free_tokens(id)` | NULL | enc:none | Set when `entitlement_kind='free_token'`. |
| `status` | reading_status_enum | NOT NULL | `'queued'` | enc:none | State machine. |
| `idempotency_key` | UUID | NOT NULL | — | enc:none | From `Idempotency-Key` header. |
| `tone_prompt_version` | TEXT | NOT NULL | — | enc:none | Snapshot of system prompt version (architecture §7.2). |
| `engine_version` | TEXT | NOT NULL | — | enc:none | Mirrors `saju_charts.engine_version`. |
| `model_main` | TEXT | NOT NULL | `'claude-sonnet-4-6'` | enc:none | LLM model id at execution time. |
| `cost_input_tokens` | INTEGER | NOT NULL | `0` | enc:none | Aggregate main + followups + side-calls. |
| `cost_output_tokens` | INTEGER | NOT NULL | `0` | enc:none | |
| `cost_tts_seconds` | NUMERIC(8,2) | NOT NULL | `0` | enc:none | Supertone billable seconds. |
| `cost_krw` | INTEGER | NOT NULL | `0` | enc:none | Rolled-up cost for NFR-007 monitoring. |
| `created_at` | TIMESTAMPTZ | NOT NULL | `now()` | enc:none | |
| `started_at` | TIMESTAMPTZ | NULL | NULL | enc:none | When pipeline first emits audio. |
| `finished_at` | TIMESTAMPTZ | NULL | NULL | enc:none | When session ended. |
| `refunded_at` | TIMESTAMPTZ | NULL | NULL | enc:none | Set when FR-023 triggers. |

Constraints:

- `CHECK ((entitlement_kind='payment') = (payment_id IS NOT NULL))`
- `CHECK ((entitlement_kind='subscription') = (subscription_id IS NOT NULL))`
- `CHECK ((entitlement_kind='free_token') = (free_token_id IS NOT NULL))`
- `UNIQUE (idempotency_key)` — guarantees AP-23 idempotency.
- `CHECK ((device_id IS NULL) OR (entitlement_kind = 'free_token'))` — non-members can only use free token.

### 4.9 Table: `reading_transcripts`

Persisted text for replay + audit. One row per reading.

| Column | Type | Constraints | Default | Enc | Description |
|--------|------|-------------|---------|-----|-------------|
| `reading_id` | UUID | PK FK `readings(id)` ON DELETE CASCADE | — | enc:none | 1:1 with reading. |
| `main_text` | TEXT | NOT NULL | — | enc:none | Full LLM output for main reading. |
| `tone_substitutions_count` | SMALLINT | NOT NULL | `0` | enc:none | Layer-3 guardrail substitution count. |
| `created_at` | TIMESTAMPTZ | NOT NULL | `now()` | enc:none | |

### 4.10 Table: `reading_followups`

Each follow-up Q+A. Up to 3 per reading (FR-009).

| Column | Type | Constraints | Default | Enc | Description |
|--------|------|-------------|---------|-----|-------------|
| `id` | UUID | PK | `uuidv7()` | enc:none | |
| `reading_id` | UUID | NOT NULL FK `readings(id)` ON DELETE CASCADE | — | enc:none | |
| `slot_index` | SMALLINT | NOT NULL CHECK (`slot_index BETWEEN 0 AND 2`) | — | enc:none | Position of the suggested button. |
| `question_text` | TEXT | NOT NULL | — | enc:none | One of 3 LLM-suggested questions. |
| `answer_text` | TEXT | NULL | NULL | enc:none | Filled when the user taps; remains NULL otherwise. |
| `audio_r2_key` | TEXT | NULL | NULL | enc:none | R2 path to stitched mp3. |
| `audio_duration_ms` | INTEGER | NULL | NULL | enc:none | |
| `model_followup` | TEXT | NOT NULL | `'claude-haiku-4-5'` | enc:none | |
| `tapped_at` | TIMESTAMPTZ | NULL | NULL | enc:none | NULL = button shown but not tapped. |
| `finished_at` | TIMESTAMPTZ | NULL | NULL | enc:none | |
| `created_at` | TIMESTAMPTZ | NOT NULL | `now()` | enc:none | |

Constraints:

- `UNIQUE (reading_id, slot_index)`.

### 4.11 Table: `reading_audio`

R2 pointer + metadata for the main audio. (Follow-up audio lives on `reading_followups`.)

| Column | Type | Constraints | Default | Enc | Description |
|--------|------|-------------|---------|-----|-------------|
| `reading_id` | UUID | PK FK `readings(id)` ON DELETE CASCADE | — | enc:none | |
| `r2_key` | TEXT | NOT NULL UNIQUE | — | enc:none | `audio/readings/{reading_id}/main.mp3`. |
| `content_hash` | CHAR(64) | NOT NULL | — | enc:none | SHA-256 of mp3 bytes; integrity check. |
| `duration_ms` | INTEGER | NOT NULL CHECK (`duration_ms BETWEEN 60000 AND 120000`) | — | enc:none | FR-007 60–120 sec window. |
| `file_size_bytes` | BIGINT | NOT NULL | — | enc:none | |
| `expires_at` | TIMESTAMPTZ | NULL | NULL | enc:none | NULL = no auto-expiry in v1 (A-07). Set when policy adopted. |
| `created_at` | TIMESTAMPTZ | NOT NULL | `now()` | enc:none | |

### 4.12 Table: `tarot_draws`

One row per (subject × KST date) — covers both members and devices.

| Column | Type | Constraints | Default | Enc | Description |
|--------|------|-------------|---------|-----|-------------|
| `id` | UUID | PK | `uuidv7()` | enc:none | |
| `user_id` | UUID | NULL FK `users(id)` | NULL | enc:none | |
| `device_id` | UUID | NULL FK `devices(id)` | NULL | enc:none | |
| `date_kst` | DATE | NOT NULL | — | enc:none | KST calendar date the card is for. |
| `card_index` | SMALLINT | NOT NULL CHECK (`card_index BETWEEN 0 AND 21`) | — | enc:none | FR-013 deterministic index. |
| `entitlement_kind` | TEXT | NOT NULL CHECK (`entitlement_kind IN ('free_quota','payment','subscription')`) | — | enc:none | What unlocked it. |
| `payment_id` | UUID | NULL FK `payments(id)` | NULL | enc:none | |
| `subscription_id` | UUID | NULL FK `subscriptions(id)` | NULL | enc:none | |
| `transcript_text` | TEXT | NULL | NULL | enc:none | Filled when reading completes. |
| `audio_r2_key` | TEXT | NULL | NULL | enc:none | |
| `audio_duration_ms` | INTEGER | NULL CHECK (`audio_duration_ms IS NULL OR audio_duration_ms BETWEEN 25000 AND 45000`) | NULL | enc:none | FR-015 25–45 sec window. |
| `tone_prompt_version` | TEXT | NOT NULL | — | enc:none | |
| `model_used` | TEXT | NOT NULL | `'claude-haiku-4-5'` | enc:none | |
| `cost_input_tokens` | INTEGER | NOT NULL | `0` | enc:none | |
| `cost_output_tokens` | INTEGER | NOT NULL | `0` | enc:none | |
| `cost_tts_seconds` | NUMERIC(8,2) | NOT NULL | `0` | enc:none | |
| `cost_krw` | INTEGER | NOT NULL | `0` | enc:none | |
| `status` | tarot_status_enum | NOT NULL | `'streaming'` | enc:none | |
| `created_at` | TIMESTAMPTZ | NOT NULL | `now()` | enc:none | |
| `finished_at` | TIMESTAMPTZ | NULL | NULL | enc:none | |

Constraints:

- `CHECK ((user_id IS NULL) <> (device_id IS NULL))` — exactly one subject.
- **Idempotency / "same card per day"**: two partial unique indexes (see §5).

### 4.13 Table: `payments`

Toss Payments receipts. Card data never stored (NFR-006).

| Column | Type | Constraints | Default | Enc | Description |
|--------|------|-------------|---------|-----|-------------|
| `id` | UUID | PK | `uuidv7()` | enc:none | |
| `user_id` | UUID | NOT NULL FK `users(id)` | — | enc:none | |
| `type` | payment_type_enum | NOT NULL | — | enc:none | |
| `method` | payment_method_enum | NOT NULL | — | enc:none | |
| `amount_krw` | INTEGER | NOT NULL CHECK (`amount_krw > 0`) | — | enc:none | |
| `currency` | CHAR(3) | NOT NULL | `'KRW'` | enc:none | |
| `category` | category_enum | NULL | NULL | enc:none | Set when type=`single` and bought from saju paywall; NULL for tarot single + subscription billing. |
| `toss_order_id` | TEXT | NOT NULL UNIQUE | — | enc:none | Idempotent client-generated. |
| `toss_payment_key` | TEXT | NULL UNIQUE (partial WHERE NOT NULL) | NULL | enc:none | Returned by Toss on success. |
| `subscription_id` | UUID | NULL FK `subscriptions(id)` | NULL | enc:none | Set when `type` is subscription_initial/recurring. |
| `status` | payment_status_enum | NOT NULL | `'pending'` | enc:none | |
| `failure_reason` | TEXT | NULL | NULL | enc:none | Toss error message for diagnostic. |
| `created_at` | TIMESTAMPTZ | NOT NULL | `now()` | enc:none | |
| `paid_at` | TIMESTAMPTZ | NULL | NULL | enc:none | When Toss webhook confirms. |
| `refunded_at` | TIMESTAMPTZ | NULL | NULL | enc:none | Last refund event. |
| `refunded_amount_krw` | INTEGER | NOT NULL CHECK (`refunded_amount_krw >= 0 AND refunded_amount_krw <= amount_krw`) | `0` | enc:none | Cumulative refunded amount. |

### 4.14 Table: `subscriptions`

One active subscription per user (current design — v1 doesn't support multi-tier).

| Column | Type | Constraints | Default | Enc | Description |
|--------|------|-------------|---------|-----|-------------|
| `id` | UUID | PK | `uuidv7()` | enc:none | |
| `user_id` | UUID | NOT NULL FK `users(id)` | — | enc:none | |
| `tier` | TEXT | NOT NULL CHECK (`tier IN ('monthly'))` | `'monthly'` | enc:none | v1 has one tier. |
| `status` | subscription_status_enum | NOT NULL | `'active'` | enc:none | |
| `toss_billing_key` | TEXT | NOT NULL UNIQUE | — | enc:none | Toss recurring billing handle. |
| `monthly_amount_krw` | INTEGER | NOT NULL | — | enc:none | Snapshot of price at sign-up. |
| `started_at` | TIMESTAMPTZ | NOT NULL | `now()` | enc:none | |
| `current_period_start` | TIMESTAMPTZ | NOT NULL | — | enc:none | |
| `current_period_end` | TIMESTAMPTZ | NOT NULL | — | enc:none | |
| `monthly_saju_remaining` | SMALLINT | NOT NULL CHECK (`monthly_saju_remaining BETWEEN 0 AND 1`) | `1` | enc:none | FR-022: 1 saju/period. Decremented on use. Resets on period roll. |
| `cancel_requested_at` | TIMESTAMPTZ | NULL | NULL | enc:none | When user requested cancel. |
| `cancelled_at` | TIMESTAMPTZ | NULL | NULL | enc:none | When subscription actually terminated. |
| `updated_at` | TIMESTAMPTZ | NOT NULL | `now()` | enc:none | |

Constraints:

- **At most one active subscription per user**: `UNIQUE (user_id) WHERE status IN ('active','cancel_at_period_end','past_due')`.

### 4.15 Table: `refunds`

Auditable log of refunds (FR-023). One row per refund event (a payment can be refunded in parts in theory; in v1 they're full refunds).

| Column | Type | Constraints | Default | Enc | Description |
|--------|------|-------------|---------|-----|-------------|
| `id` | UUID | PK | `uuidv7()` | enc:none | |
| `payment_id` | UUID | NOT NULL FK `payments(id)` | — | enc:none | |
| `reading_id` | UUID | NULL FK `readings(id)` | NULL | enc:none | Cause of refund. |
| `amount_krw` | INTEGER | NOT NULL CHECK (`amount_krw > 0`) | — | enc:none | |
| `reason` | TEXT | NOT NULL CHECK (`reason IN ('llm_failure','manual_ops','tts_outage','user_request')`) | — | enc:none | |
| `toss_refund_id` | TEXT | NULL UNIQUE (partial) | NULL | enc:none | Toss refund response handle. |
| `fallback_token_id` | UUID | NULL FK `free_tokens(id)` | NULL | enc:none | Set if Toss refund failed and we credited a token (FR-023 AC). |
| `status` | TEXT | NOT NULL CHECK (`status IN ('pending','succeeded','failed_credited','failed_open')`) | `'pending'` | enc:none | |
| `created_at` | TIMESTAMPTZ | NOT NULL | `now()` | enc:none | |
| `finished_at` | TIMESTAMPTZ | NULL | NULL | enc:none | |

### 4.16 Table: `quote_cards`

Generated viral asset. Created at session end (saju or tarot).

| Column | Type | Constraints | Default | Enc | Description |
|--------|------|-------------|---------|-----|-------------|
| `id` | UUID | PK | `uuidv7()` | enc:none | |
| `share_slug` | TEXT | NOT NULL UNIQUE | — | enc:none | Short opaque URL-safe slug (base62 of a hash; ≤ 12 chars). |
| `source_kind` | TEXT | NOT NULL CHECK (`source_kind IN ('reading','tarot')`) | — | enc:none | |
| `reading_id` | UUID | NULL FK `readings(id)` ON DELETE CASCADE | NULL | enc:none | |
| `tarot_id` | UUID | NULL FK `tarot_draws(id)` ON DELETE CASCADE | NULL | enc:none | |
| `category_or_card` | TEXT | NOT NULL | — | enc:none | `'love'`/`'work'`/`'money'` for saju; card name (e.g., `'the_fool'`) for tarot. |
| `quote_text` | TEXT | NOT NULL CHECK (`char_length(quote_text) <= 40`) | — | enc:none | FR-018 ≤40 chars. |
| `character_key` | character_key_enum | NOT NULL | — | enc:none | |
| `og_r2_key` | TEXT | NULL | NULL | enc:none | Filled when arq `og_bake` finishes. |
| `og_status` | TEXT | NOT NULL CHECK (`og_status IN ('pending','baked','failed')`) | `'pending'` | enc:none | |
| `created_at` | TIMESTAMPTZ | NOT NULL | `now()` | enc:none | |
| `expires_at` | TIMESTAMPTZ | NULL | NULL | enc:none | A-07; NULL = indefinite v1. |

Constraints:

- `CHECK ((source_kind='reading') = (reading_id IS NOT NULL))`
- `CHECK ((source_kind='tarot') = (tarot_id IS NOT NULL))`

### 4.17 Table: `tarot_cards` (seed/reference)

Static deck — 22 Major Arcana. Seed once at deploy; never user-mutable.

| Column | Type | Constraints | Default | Enc | Description |
|--------|------|-------------|---------|-----|-------------|
| `card_index` | SMALLINT | PK CHECK (`card_index BETWEEN 0 AND 21`) | — | enc:none | |
| `slug` | TEXT | NOT NULL UNIQUE | — | enc:none | `'the_fool'`, `'the_magician'`, ... |
| `display_name_kr` | TEXT | NOT NULL | — | enc:none | `'바보'`, `'마법사'`, ... |
| `display_name_en` | TEXT | NOT NULL | — | enc:none | `'The Fool'`, ... |
| `meaning_short_kr` | TEXT | NOT NULL | — | enc:none | One-line summary for face-up label. |
| `meaning_full_kr` | TEXT | NOT NULL | — | enc:none | LLM prompt context for tarot reading. |
| `art_r2_key` | TEXT | NOT NULL | — | enc:none | `static/tarot/cards/{slug}.png`. |
| `back_art_r2_key` | TEXT | NOT NULL | `'static/tarot/back.png'` | enc:none | Shared face-down art. |
| `created_at` | TIMESTAMPTZ | NOT NULL | `now()` | enc:none | |
| `updated_at` | TIMESTAMPTZ | NOT NULL | `now()` | enc:none | |

### 4.18 Table: `intro_audio_clips` (seed/reference)

Pre-recorded 15-sec 누님 intros per category (FR-005, DEP-07).

| Column | Type | Constraints | Default | Enc | Description |
|--------|------|-------------|---------|-----|-------------|
| `id` | UUID | PK | `uuidv7()` | enc:none | |
| `category` | category_enum | NOT NULL | — | enc:none | |
| `character_key` | character_key_enum | NOT NULL | `'nuna'` | enc:none | |
| `audio_r2_key` | TEXT | NOT NULL | — | enc:none | |
| `subtitle_text` | TEXT | NOT NULL | — | enc:none | Synced full caption. |
| `duration_ms` | INTEGER | NOT NULL CHECK (`duration_ms BETWEEN 10000 AND 20000`) | — | enc:none | ~15s. |
| `birth_time_known_variant` | BOOLEAN | NOT NULL | — | enc:none | TRUE = standard; FALSE = includes "시간을 모르면…" canned phrase (FR-002 AC). |
| `is_active` | BOOLEAN | NOT NULL | `true` | enc:none | |
| `created_at` | TIMESTAMPTZ | NOT NULL | `now()` | enc:none | |

### 4.19 Table: `character_voices` (seed/reference)

Maps internal character to Supertone voice id.

| Column | Type | Constraints | Default | Enc | Description |
|--------|------|-------------|---------|-----|-------------|
| `character_key` | character_key_enum | PK | — | enc:none | `'nuna'` or `'dosa'`. |
| `display_name_kr` | TEXT | NOT NULL | — | enc:none | `'시니컬 누님'` / `'노인 도사'`. |
| `supertone_voice_id` | TEXT | NOT NULL | — | enc:none | Filled at integration (DEP-01). |
| `speech_rate` | NUMERIC(3,2) | NOT NULL | `1.00` | enc:none | Multiplier. |
| `pitch_shift` | NUMERIC(3,2) | NOT NULL | `0.00` | enc:none | Semitones. |
| `created_at` | TIMESTAMPTZ | NOT NULL | `now()` | enc:none | |
| `updated_at` | TIMESTAMPTZ | NOT NULL | `now()` | enc:none | |

### 4.20 Table: `tone_prompt_versions` (seed + ops)

Versioned LLM system prompts.

| Column | Type | Constraints | Default | Enc | Description |
|--------|------|-------------|---------|-----|-------------|
| `id` | UUID | PK | `uuidv7()` | enc:none | |
| `prompt_key` | TEXT | NOT NULL CHECK (`prompt_key IN ('saju_main','followup','tarot','intro_hint','quote_extract','followup_question_suggest')`) | — | enc:none | |
| `version` | TEXT | NOT NULL | — | enc:none | E.g., `'v2026.05.29-1'`. |
| `character_key` | character_key_enum | NOT NULL | — | enc:none | |
| `model` | TEXT | NOT NULL | — | enc:none | `'claude-sonnet-4-6'` / `'claude-haiku-4-5'`. |
| `system_prompt` | TEXT | NOT NULL | — | enc:none | Full system prompt body. |
| `is_active` | BOOLEAN | NOT NULL | `false` | enc:none | Exactly one per `prompt_key` should be active. |
| `created_at` | TIMESTAMPTZ | NOT NULL | `now()` | enc:none | |
| `activated_at` | TIMESTAMPTZ | NULL | NULL | enc:none | |
| `deprecated_at` | TIMESTAMPTZ | NULL | NULL | enc:none | |

Constraints:

- `UNIQUE (prompt_key, version)`.
- **At most one active per prompt_key**: `UNIQUE (prompt_key) WHERE is_active = true`.

### 4.21 Table: `tone_eval_cases` (seed/ops)

Regression set for FR-032 (≥ 50 cases at launch).

| Column | Type | Constraints | Default | Enc | Description |
|--------|------|-------------|---------|-----|-------------|
| `id` | UUID | PK | `uuidv7()` | enc:none | |
| `case_set_version` | TEXT | NOT NULL | — | enc:none | Pinned per CI run. |
| `label` | tone_eval_label_enum | NOT NULL | — | enc:none | `'ok'` or `'violation'`. |
| `prompt_key` | TEXT | NOT NULL | — | enc:none | Which surface this tests. |
| `input_context` | JSONB | NOT NULL | — | enc:none | Synthetic chart + category + question. |
| `expected_behavior` | TEXT | NOT NULL | — | enc:none | Human description. |
| `rationale` | TEXT | NULL | NULL | enc:none | Why this case exists. |
| `created_at` | TIMESTAMPTZ | NOT NULL | `now()` | enc:none | |

### 4.22 Table: `tone_violation_events`

Real-time guardrail telemetry (NFR-010 monitor).

| Column | Type | Constraints | Default | Enc | Description |
|--------|------|-------------|---------|-----|-------------|
| `id` | UUID | PK | `uuidv7()` | enc:none | |
| `reading_id` | UUID | NULL FK `readings(id)` ON DELETE SET NULL | NULL | enc:none | |
| `tarot_id` | UUID | NULL FK `tarot_draws(id)` ON DELETE SET NULL | NULL | enc:none | |
| `layer` | TEXT | NOT NULL CHECK (`layer IN ('denylist','moderation','evalset_ci')`) | — | enc:none | Which guardrail caught it. |
| `severity` | TEXT | NOT NULL CHECK (`severity IN ('blocked','substituted','flagged_only')`) | — | enc:none | |
| `category_tag` | TEXT | NOT NULL CHECK (`category_tag IN ('profanity','hate','sexual','discrimination','other')`) | — | enc:none | |
| `triggering_chunk_sanitized` | TEXT | NOT NULL | — | enc:none | Profanity masked; audit-only. |
| `tone_prompt_version` | TEXT | NOT NULL | — | enc:none | |
| `created_at` | TIMESTAMPTZ | NOT NULL | `now()` | enc:none | |

Constraints:

- `CHECK ((reading_id IS NOT NULL) OR (tarot_id IS NOT NULL))` — at least one source.

### 4.23 Table: `audit_events`

PII access + privacy-action audit log (PIPA / GDPR).

| Column | Type | Constraints | Default | Enc | Description |
|--------|------|-------------|---------|-----|-------------|
| `id` | UUID | PK | `uuidv7()` | enc:none | |
| `actor_kind` | TEXT | NOT NULL CHECK (`actor_kind IN ('user','system','ops')`) | — | enc:none | |
| `actor_user_id` | UUID | NULL FK `users(id)` | NULL | enc:none | |
| `subject_user_id` | UUID | NULL FK `users(id)` | NULL | enc:none | Whose data was touched. |
| `action` | audit_action_enum | NOT NULL | — | enc:none | |
| `detail` | JSONB | NOT NULL | `'{}'::jsonb` | enc:none | Structured context (route, columns, etc.). PII never logged. |
| `request_id` | TEXT | NULL | NULL | enc:none | Trace correlation. |
| `created_at` | TIMESTAMPTZ | NOT NULL | `now()` | enc:none | |

### 4.24 Table: `idempotency_keys`

Optional v1.1 — for v1 we lean on the per-table `idempotency_key` UNIQUE columns (`readings.idempotency_key`, `payments.toss_order_id`, plus Redis for short-lived dedup). This table is reserved for cross-table, cross-day idempotency if needed later.

### 4.25 Encryption envelope structure (NFR-005)

`profiles.birth_dt_enc` JSONB shape:

```json
{
  "kek_version": "kek-2026-05",
  "wrapped_dek": "BASE64(KMS_Encrypt(DEK))",
  "iv": "BASE64(12-byte IV)",
  "ciphertext": "BASE64(AES-256-GCM(DEK, plaintext))",
  "tag": "BASE64(16-byte GCM tag)",
  "algorithm": "AES-256-GCM",
  "aad": "user_id:<uuid>:profile:birth_dt"
}
```

- **One DEK per row** (per-row envelope) — single key compromise leaks only that row.
- KMS provider (AWS KMS or GCP KMS) holds the KEK; rotation = `kek_version` bump + re-wrap of DEK, no plaintext rotation.
- AAD includes `user_id` and column name — defends against ciphertext-swap attacks across rows.
- Decryption path is logged to `audit_events(action='profile_read')` (sampled in production for cost, full for ops).

---

## 5. Indexes

Each index is justified by an access pattern (AP-#). Indexes without an access pattern are not created.

### 5.1 `users`

| Index | Columns | Type | Justification |
|-------|---------|------|---------------|
| `users_pkey` | `id` | btree | PK. AP-01, AP-08. |
| `users_kakao_sub_uq` | `(kakao_sub) WHERE kakao_sub IS NOT NULL` | partial unique | AP-02. |
| `users_apple_sub_uq` | `(apple_sub) WHERE apple_sub IS NOT NULL` | partial unique | AP-03. |
| `users_toss_id_uq` | `(toss_id) WHERE toss_id IS NOT NULL` | partial unique | AP-04. |
| `users_email_hash_idx` | `(email_hash) WHERE email_hash IS NOT NULL` | partial btree | Duplicate detection on signup. |
| `users_deleted_at_idx` | `(deleted_at) WHERE deleted_at IS NOT NULL` | partial btree | GDPR worker batch scans (AP-54). |

### 5.2 `devices`

| Index | Columns | Type | Justification |
|-------|---------|------|---------------|
| `devices_pkey` | `id` | btree | PK. |
| `devices_client_uq` | `device_id_client` | unique btree | AP-06. |
| `devices_linked_user_idx` | `(linked_user_id) WHERE linked_user_id IS NOT NULL` | partial btree | AP-07 reverse lookup. |

### 5.3 `profiles`

| Index | Columns | Type | Justification |
|-------|---------|------|---------------|
| `profiles_pkey` | `id` | btree | PK. |
| `profiles_user_uq` | `(user_id)` | unique btree | AP-09, AP-15. 1:1 with users. |

### 5.4 `saju_charts`

| Index | Columns | Type | Justification |
|-------|---------|------|---------------|
| `saju_charts_pkey` | `id` | btree | PK. AP-13. |
| `saju_charts_hash_uq` | `chart_hash` | unique btree | AP-11 cache hit. |
| `saju_charts_user_created_idx` | `(user_id, created_at DESC)` | compound btree | AP-12 "latest chart for user". |

### 5.5 `free_tokens`

| Index | Columns | Type | Justification |
|-------|---------|------|---------------|
| `free_tokens_pkey` | `id` | btree | PK. |
| `free_tokens_user_active_idx` | `(user_id, kind) WHERE consumed_at IS NULL` | partial compound | AP-16 active-tokens-for-user. |
| `free_tokens_device_active_idx` | `(device_id, kind) WHERE consumed_at IS NULL AND device_id IS NOT NULL` | partial compound | AP-17. |
| `free_tokens_signup_grant_uq` | `(user_id) WHERE kind='signup_grant'` | partial unique | FR-017 idempotent grant. |
| `free_tokens_nonmember_trial_uq` | `(device_id) WHERE kind='nonmember_trial'` | partial unique | FR-003 idempotent grant. |

### 5.6 `readings`

| Index | Columns | Type | Justification |
|-------|---------|------|---------------|
| `readings_pkey` | `id` | btree | PK. AP-24, AP-27. |
| `readings_idempotency_uq` | `idempotency_key` | unique btree | AP-23. |
| `readings_user_created_idx` | `(user_id, created_at DESC)` | compound btree | AP-28 history list. |
| `readings_user_paid_status_idx` | `(user_id, created_at DESC) WHERE entitlement_kind='payment' AND status='done'` | partial compound | AP-22 lifetime-paid-count (FR-025 upsell trigger). |
| `readings_status_running_idx` | `(status) WHERE status IN ('queued','streaming')` | partial btree | Worker reconciliation / stuck-session sweep. |
| `readings_payment_idx` | `(payment_id) WHERE payment_id IS NOT NULL` | partial btree | Refund flow joins. |
| `readings_device_idx` | `(device_id, created_at DESC) WHERE device_id IS NOT NULL` | partial compound | Non-member free trial enforcement + post-signup migration. |

### 5.7 `reading_transcripts`, `reading_followups`, `reading_audio`

| Index | Columns | Type | Justification |
|-------|---------|------|---------------|
| `reading_transcripts_pkey` | `reading_id` | btree | PK + 1:1 join (AP-27). |
| `reading_followups_pkey` | `id` | btree | PK. |
| `reading_followups_reading_slot_uq` | `(reading_id, slot_index)` | unique compound | AP-26 ordered slots. |
| `reading_audio_pkey` | `reading_id` | btree | PK + 1:1 join (AP-27). |
| `reading_audio_r2_key_uq` | `r2_key` | unique btree | Defensive integrity. |

### 5.8 `tarot_draws`

| Index | Columns | Type | Justification |
|-------|---------|------|---------------|
| `tarot_draws_pkey` | `id` | btree | PK. |
| `tarot_draws_user_date_uq` | `(user_id, date_kst) WHERE user_id IS NOT NULL` | partial unique compound | AP-31 idempotent same-card-per-day for members. |
| `tarot_draws_device_date_uq` | `(device_id, date_kst) WHERE device_id IS NOT NULL` | partial unique compound | AP-31 same for non-members. |
| `tarot_draws_user_date_desc_idx` | `(user_id, date_kst DESC)` | compound btree | Weekly quota window scan (AP-33 fallback if Redis miss). |
| `tarot_draws_status_running_idx` | `(status) WHERE status = 'streaming'` | partial btree | Stuck-session sweep. |

### 5.9 `payments`

| Index | Columns | Type | Justification |
|-------|---------|------|---------------|
| `payments_pkey` | `id` | btree | PK. |
| `payments_user_created_idx` | `(user_id, created_at DESC)` | compound btree | AP-39 history list. |
| `payments_toss_order_uq` | `toss_order_id` | unique btree | AP-37 client confirm + idempotency. |
| `payments_toss_payment_key_uq` | `(toss_payment_key) WHERE toss_payment_key IS NOT NULL` | partial unique | AP-36 webhook idempotency. |
| `payments_subscription_idx` | `(subscription_id) WHERE subscription_id IS NOT NULL` | partial btree | Recurring billing reconciliation. |
| `payments_user_single_paid_idx` | `(user_id, paid_at DESC) WHERE type='single' AND status='paid'` | partial compound | AP-22 lifetime-paid-single count (FR-025). |

### 5.10 `subscriptions`

| Index | Columns | Type | Justification |
|-------|---------|------|---------------|
| `subscriptions_pkey` | `id` | btree | PK. |
| `subscriptions_user_active_uq` | `(user_id) WHERE status IN ('active','cancel_at_period_end','past_due')` | partial unique | AP-21 "active subscription per user" enforcement. |
| `subscriptions_user_idx` | `(user_id)` | btree | AP-21 read path; also covers admin list. |
| `subscriptions_billing_key_uq` | `toss_billing_key` | unique btree | Toss webhook lookup. |
| `subscriptions_period_end_idx` | `(current_period_end) WHERE status IN ('active','cancel_at_period_end')` | partial btree | Daily roll-period scheduler. |

### 5.11 `refunds`

| Index | Columns | Type | Justification |
|-------|---------|------|---------------|
| `refunds_pkey` | `id` | btree | PK. |
| `refunds_payment_idx` | `(payment_id)` | btree | Join from payment row. |
| `refunds_status_open_idx` | `(status) WHERE status IN ('pending','failed_open')` | partial btree | Retry worker scan. |
| `refunds_toss_refund_uq` | `(toss_refund_id) WHERE toss_refund_id IS NOT NULL` | partial unique | Webhook idempotency. |

### 5.12 `quote_cards`

| Index | Columns | Type | Justification |
|-------|---------|------|---------------|
| `quote_cards_pkey` | `id` | btree | PK. |
| `quote_cards_slug_uq` | `share_slug` | unique btree | AP-43 public lookup. |
| `quote_cards_reading_idx` | `(reading_id) WHERE reading_id IS NOT NULL` | partial btree | Inverse navigation. |
| `quote_cards_tarot_idx` | `(tarot_id) WHERE tarot_id IS NOT NULL` | partial btree | Inverse navigation. |
| `quote_cards_pending_bake_idx` | `(created_at) WHERE og_status='pending'` | partial btree | arq worker scan. |

### 5.13 Seed / reference tables

| Index | Columns | Type | Justification |
|-------|---------|------|---------------|
| `tarot_cards_pkey` | `card_index` | btree | AP-45. |
| `tarot_cards_slug_uq` | `slug` | unique btree | Slug routing in admin/seed. |
| `intro_audio_clips_pkey` | `id` | btree | PK. |
| `intro_audio_clips_category_active_idx` | `(category, character_key, birth_time_known_variant, is_active)` | compound btree | AP-46. |
| `character_voices_pkey` | `character_key` | btree | AP-47. |
| `tone_prompt_versions_pkey` | `id` | btree | PK. |
| `tone_prompt_versions_active_uq` | `(prompt_key) WHERE is_active=true` | partial unique | AP-48 + single-active invariant. |
| `tone_prompt_versions_key_version_uq` | `(prompt_key, version)` | unique compound | Version history. |
| `tone_eval_cases_pkey` | `id` | btree | AP-52. |
| `tone_eval_cases_set_idx` | `(case_set_version, prompt_key, label)` | compound btree | AP-51 CI batch read. |

### 5.14 `tone_violation_events`, `audit_events`

| Index | Columns | Type | Justification |
|-------|---------|------|---------------|
| `tone_violation_events_pkey` | `id` | btree | PK. |
| `tone_violation_events_created_idx` | `(created_at DESC)` | btree | AP-50 rollup window. |
| `tone_violation_events_reading_idx` | `(reading_id) WHERE reading_id IS NOT NULL` | partial btree | Per-reading audit. |
| `audit_events_pkey` | `id` | btree | PK. |
| `audit_events_subject_idx` | `(subject_user_id, created_at DESC)` | compound btree | GDPR export query. |
| `audit_events_action_idx` | `(action, created_at DESC)` | compound btree | Compliance reports. |

---

## 6. Migrations

### 6.1 Tool & policy

- **Alembic** (SQLAlchemy 2.0 async). Per architecture §5.4 / §13.4.
- **Forward-only in production.** No `downgrade()` is run against prod.
- **Two-deploy rule for any destructive change**:
  1. App release N: stop reading from / writing to the column. Migration is **additive only** (adds new column, backfills, dual-writes if necessary).
  2. App release N+1 (after N is stable for ≥ 1 release cycle): migration **drops** the old column.
- **CI gates** before merge: migration applies cleanly to a fresh DB; applies cleanly on top of a snapshot of the previous prod migration head; saju regression and tone evalset still pass.
- **Production migration runs** as a deploy-step gate; the new container never receives traffic if migration fails.

### 6.2 Rollback strategy

- **App rollback** (Fly.io `flyctl releases rollback`) is independent of DB rollback.
- **DB "rollback" is a new forward migration** that compensates. Never `alembic downgrade` in prod.
- **Disaster rollback**: PITR (point-in-time-recovery) on managed Postgres + nightly logical dump to R2 (encrypted) retained 30 days.

### 6.3 Initial migration (v1)

`0001_initial.py`:

1. Create enums (§4.1).
2. Create tables in FK-safe order: `users` → `devices` → `profiles` → `saju_charts` → `free_tokens` → `payments` → `subscriptions` → `readings` → `reading_transcripts` → `reading_followups` → `reading_audio` → `tarot_cards` → `tarot_draws` → `quote_cards` → `intro_audio_clips` → `character_voices` → `tone_prompt_versions` → `tone_eval_cases` → `tone_violation_events` → `refunds` → `audit_events`.
3. Create all indexes from §5.
4. Run seed data SQL (§7).

### 6.4 Reference data migrations

Seed data (§7) lives in **idempotent** migrations (`INSERT ... ON CONFLICT DO NOTHING`). New cards / prompts / voices are added via separate small migrations, never edited in place.

---

## 7. Seed Data

Each item below ships in `0001_initial.py` (or a follow-up seed migration before launch). All inserts use `ON CONFLICT (...) DO NOTHING` for idempotency.

| Table | Data | Purpose |
|-------|------|---------|
| `tarot_cards` | 22 rows: Major Arcana (0=`the_fool` … 21=`the_world`) with KR + EN display names, short and full meanings, R2 keys for art. | Required for FR-013 deterministic selection + FR-015 reading + Flow C. |
| `character_voices` | 2 rows: `nuna` (시니컬 누님) and `dosa` (노인 도사) with placeholder `supertone_voice_id` (`'TBD_NUNA'`, `'TBD_DOSA'`) until DEP-01 contract. | Required for AP-47 dispatch. |
| `intro_audio_clips` | At minimum 6 rows: 3 categories × 2 birth-time-known variants (FR-002 variant + standard variant), all `character_key='nuna'`. DEP-07 supplies actual audio. | Required for FR-005 / Screen 7. |
| `tone_prompt_versions` | 6 rows (all `is_active=true` for first deploy): `saju_main` (Sonnet 4.6), `followup` (Haiku 4.5), `tarot` (Haiku 4.5), `intro_hint` (Haiku 4.5), `quote_extract` (Haiku 4.5), `followup_question_suggest` (Haiku 4.5). | Required for every LLM call (AP-48). |
| `tone_eval_cases` | ≥ 50 rows from `tests/fixtures/tone_evalset.json`, mix of `ok` and `violation` labels covering profanity / hate / sexual / discrimination / borderline-spicy. | Required for FR-032 CI gate (AP-51). |

### 7.1 Sample seed SQL (Major Arcana — abbreviated; full list in migration)

```sql
INSERT INTO tarot_cards
  (card_index, slug, display_name_kr, display_name_en, meaning_short_kr, meaning_full_kr, art_r2_key)
VALUES
  (0, 'the_fool', '바보', 'The Fool', '새로운 시작, 자유로운 영혼',
   '백지 같은 출발. 두려움보다 호기심이 앞서는 날.', 'static/tarot/cards/the_fool.png'),
  (1, 'the_magician', '마법사', 'The Magician', '의지와 창조',
   '네 손에 도구가 다 있어. 시작하기만 하면 돼.', 'static/tarot/cards/the_magician.png'),
  -- … through 21 …
  (21, 'the_world', '세계', 'The World', '완성, 통합',
   '한 챕터가 닫혀. 다음 챕터는 더 클 거야.', 'static/tarot/cards/the_world.png')
ON CONFLICT (card_index) DO NOTHING;
```

### 7.2 Sample seed SQL (character voices)

```sql
INSERT INTO character_voices (character_key, display_name_kr, supertone_voice_id, speech_rate, pitch_shift)
VALUES
  ('nuna', '시니컬 누님', 'TBD_NUNA_VOICE_ID', 1.00, 0.00),
  ('dosa', '노인 도사',   'TBD_DOSA_VOICE_ID', 0.90, -1.00)
ON CONFLICT (character_key) DO NOTHING;
```

Production deploy updates `supertone_voice_id` once DEP-01 lands (via a small migration, never via `UPDATE` in app code).

### 7.3 Sample seed SQL (intro audio — placeholders)

```sql
INSERT INTO intro_audio_clips
  (id, category, character_key, audio_r2_key, subtitle_text, duration_ms, birth_time_known_variant, is_active)
VALUES
  (uuidv7(), 'love',  'nuna', 'static/intro_audio/love/v1_known.mp3',   '어디 한번 봅시다… 연애 운 보러 왔구나.', 15000, true,  true),
  (uuidv7(), 'love',  'nuna', 'static/intro_audio/love/v1_unknown.mp3', '시간을 모른다고? 큰 줄기는 보지만 디테일은 흐릿해. 연애부터 봅시다.', 15000, false, true),
  (uuidv7(), 'work',  'nuna', 'static/intro_audio/work/v1_known.mp3',   '음… 직장 운, 재미있겠네.', 15000, true,  true),
  (uuidv7(), 'work',  'nuna', 'static/intro_audio/work/v1_unknown.mp3', '시간 모름 모드. 그래도 직장은 일주로도 봐줄게.', 15000, false, true),
  (uuidv7(), 'money', 'nuna', 'static/intro_audio/money/v1_known.mp3',  '돈 얘기네. 좋아, 매운맛으로 가자.', 15000, true,  true),
  (uuidv7(), 'money', 'nuna', 'static/intro_audio/money/v1_unknown.mp3','시간 모름 모드. 통장은 그래도 봐줄게.', 15000, false, true)
ON CONFLICT DO NOTHING;
```

---

## 8. Query Patterns

SQL examples for each major access pattern. All examples assume `asyncpg` parameter style (`$1`, `$2`, …).

### 8.1 AP-01 — Session resolve

Redis primary:

```
GET vs_sess:<sid>  -> JSON {user_id, csrf, exp, ...}
```

DB fallback (only on Redis miss + cookie carries signed user_id):

```sql
SELECT id, display_locale, deleted_at
FROM users
WHERE id = $1 AND deleted_at IS NULL;
```

- Index used: `users_pkey`. Expected ≤ 1 row, ≤ 1 ms.

### 8.2 AP-02 — Kakao OAuth callback

```sql
SELECT id FROM users WHERE kakao_sub = $1 LIMIT 1;
```

- Index: `users_kakao_sub_uq`. ≤ 1 row.

### 8.3 AP-09 — Read current profile (with decrypt)

```sql
SELECT p.id, p.birth_dt_enc, p.birth_is_lunar, p.birth_time_known,
       p.gender, p.name_optional, p.correction_count
FROM profiles p
WHERE p.user_id = $1 AND p.deleted_at IS NULL;
```

- Index: `profiles_user_uq`. ≤ 1 row.
- Decrypt happens in app layer via `security/envelope.py` (KMS Decrypt call cached for 60 s per worker process).
- Audit row written via `audit_events(action='profile_read')` (sampled).

### 8.4 AP-11 — Cache-hit / compute saju chart

Cache hit:

```sql
SELECT id, pillars, time_known, engine_version
FROM saju_charts
WHERE chart_hash = $1;
```

Insert on miss:

```sql
INSERT INTO saju_charts (id, user_id, chart_hash, engine_version, pillars, time_known)
VALUES ($1, $2, $3, $4, $5::jsonb, $6)
ON CONFLICT (chart_hash) DO UPDATE SET chart_hash = EXCLUDED.chart_hash  -- no-op for race
RETURNING id, pillars, time_known, engine_version;
```

- Index: `saju_charts_hash_uq`.
- `ON CONFLICT` makes this safe under concurrent identical compute (cache stampede).

### 8.5 AP-12 — Read user's current chart

```sql
SELECT id, pillars, time_known, engine_version
FROM saju_charts
WHERE user_id = $1
ORDER BY created_at DESC
LIMIT 1;
```

- Index: `saju_charts_user_created_idx`. Single row.

### 8.6 AP-16 / AP-17 — Paywall: list entitlements

Composite query (1 round-trip, used by `/reading/paywall`):

```sql
WITH ft AS (
  SELECT id, kind FROM free_tokens
  WHERE user_id = $1 AND consumed_at IS NULL
),
sub AS (
  SELECT id, status, current_period_end, monthly_saju_remaining
  FROM subscriptions
  WHERE user_id = $1
    AND status IN ('active','cancel_at_period_end','past_due')
)
SELECT
  (SELECT json_agg(ft.*) FROM ft) AS tokens,
  (SELECT row_to_json(sub.*) FROM sub) AS subscription;
```

- Indexes: `free_tokens_user_active_idx`, `subscriptions_user_active_uq`. ≤ 2 logical rows.
- Eliminates N+1 vs separate calls (self-review check).

For non-members:

```sql
SELECT id FROM free_tokens
WHERE device_id = $1 AND kind = 'nonmember_trial' AND consumed_at IS NULL;
```

- Index: `free_tokens_device_active_idx`.

### 8.7 AP-20 — Consume free token

```sql
UPDATE free_tokens
SET consumed_at = now(), consumed_by_reading_id = $2
WHERE id = $1 AND consumed_at IS NULL
RETURNING id;
```

- Index: PK. Single-row update; the `consumed_at IS NULL` guard makes it idempotent under retry (returns 0 rows on second attempt).

### 8.8 AP-23 — Create Reading (idempotent)

```sql
INSERT INTO readings (
  id, user_id, device_id, chart_id, category,
  entitlement_kind, payment_id, subscription_id, free_token_id,
  status, idempotency_key, tone_prompt_version, engine_version, model_main
)
VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, 'queued', $10, $11, $12, $13)
ON CONFLICT (idempotency_key) DO UPDATE SET idempotency_key = EXCLUDED.idempotency_key
RETURNING id, status;
```

- Index: `readings_idempotency_uq`.
- Returning row whether new or existing → caller treats as "session exists".

### 8.9 AP-22 — Lifetime single-purchase count (upsell trigger)

```sql
SELECT COUNT(*) AS paid_count
FROM payments
WHERE user_id = $1 AND type = 'single' AND status = 'paid';
```

- Index: `payments_user_single_paid_idx` (partial — only scans relevant rows).
- ≤ 1 ms even at 50k users.

### 8.10 AP-27 — History replay load

```sql
SELECT
  r.id, r.category, r.created_at, r.finished_at,
  rt.main_text,
  ra.r2_key, ra.duration_ms, ra.expires_at,
  json_agg(
    json_build_object(
      'slot_index', rf.slot_index,
      'question', rf.question_text,
      'answer', rf.answer_text,
      'audio_key', rf.audio_r2_key,
      'duration_ms', rf.audio_duration_ms
    )
    ORDER BY rf.slot_index
  ) FILTER (WHERE rf.id IS NOT NULL) AS followups
FROM readings r
LEFT JOIN reading_transcripts rt ON rt.reading_id = r.id
LEFT JOIN reading_audio        ra ON ra.reading_id = r.id
LEFT JOIN reading_followups    rf ON rf.reading_id = r.id AND rf.tapped_at IS NOT NULL
WHERE r.id = $1 AND r.user_id = $2 AND r.status = 'done'
GROUP BY r.id, rt.main_text, ra.r2_key, ra.duration_ms, ra.expires_at;
```

- Indexes: `readings_pkey`, the PKs of 1:1 children, `reading_followups_reading_slot_uq`.
- One round trip, no N+1.

### 8.11 AP-28 — History list paginated

```sql
SELECT id, category, created_at, status
FROM readings
WHERE user_id = $1 AND status = 'done' AND created_at < $2
ORDER BY created_at DESC
LIMIT 20;
```

- Index: `readings_user_created_idx`. Keyset pagination via `created_at` cursor.

### 8.12 AP-31 — Today's tarot (idempotent, single-card-per-day)

Member:

```sql
INSERT INTO tarot_draws (id, user_id, date_kst, card_index, entitlement_kind, tone_prompt_version, model_used)
VALUES ($1, $2, $3, $4, $5, $6, 'claude-haiku-4-5')
ON CONFLICT (user_id, date_kst) DO UPDATE SET user_id = EXCLUDED.user_id
RETURNING id, card_index, status, audio_r2_key;
```

- Index: `tarot_draws_user_date_uq`. ≤ 1 ms.

Device equivalent uses the device partial unique.

### 8.13 AP-33 — Weekly free tarot quota (Redis primary)

Redis Lua (atomic; quota = 1/week, Monday 00:00 KST reset):

```
KEY:    tarot:freequota:{subject_id}:{iso_week_kst}
ATOMIC: GET; if absent SET 1 EX <until next Monday seconds>; if present GET → if >=1 reject
```

DB fallback (consistency check on Redis miss):

```sql
SELECT 1 FROM tarot_draws
WHERE
  (user_id = $1 OR device_id = $2)
  AND date_kst >= $3   -- this week's Monday in KST
  AND entitlement_kind = 'free_quota'
LIMIT 1;
```

- Index: `tarot_draws_user_date_desc_idx`.

### 8.14 AP-36 — Confirm payment via webhook (idempotent)

```sql
UPDATE payments
SET status = 'paid', paid_at = now(), toss_payment_key = $2
WHERE toss_order_id = $1 AND status = 'pending'
RETURNING id, user_id, type, amount_krw;
```

- Index: `payments_toss_order_uq`. Idempotent: rerunning the webhook does nothing if already paid.

### 8.15 AP-39 — Payment history list

```sql
SELECT id, type, method, amount_krw, category, status, paid_at, refunded_at, refunded_amount_krw
FROM payments
WHERE user_id = $1
ORDER BY created_at DESC
LIMIT 20 OFFSET $2;
```

- Index: `payments_user_created_idx`. Pagination by `created_at`.

### 8.16 AP-43 — Public quote card lookup

```sql
SELECT q.id, q.source_kind, q.category_or_card, q.quote_text,
       q.character_key, q.og_r2_key, q.og_status, q.expires_at
FROM quote_cards q
WHERE q.share_slug = $1
  AND (q.expires_at IS NULL OR q.expires_at > now());
```

- Index: `quote_cards_slug_uq`. ≤ 1 row. Cached in Redis with TTL 5 min.

### 8.17 AP-45 — Tarot card lookup

```sql
SELECT card_index, slug, display_name_kr, meaning_short_kr, meaning_full_kr, art_r2_key
FROM tarot_cards
WHERE card_index = $1;
```

- Index: `tarot_cards_pkey`. Process-local memoization (immutable seed data).

### 8.18 AP-46 — Intro audio resolution

```sql
SELECT audio_r2_key, subtitle_text, duration_ms
FROM intro_audio_clips
WHERE category = $1 AND character_key = $2
  AND birth_time_known_variant = $3 AND is_active = true
ORDER BY created_at DESC
LIMIT 1;
```

- Index: `intro_audio_clips_category_active_idx`. Process-local memoization with 5-min TTL.

### 8.19 AP-48 — Active tone prompt for surface

```sql
SELECT id, version, system_prompt, character_key, model
FROM tone_prompt_versions
WHERE prompt_key = $1 AND is_active = true
LIMIT 1;
```

- Index: `tone_prompt_versions_active_uq`. In-memory cache with version-pin invalidation.

### 8.20 AP-51 — CI tone evalset read

```sql
SELECT id, label, prompt_key, input_context, expected_behavior
FROM tone_eval_cases
WHERE case_set_version = $1
ORDER BY prompt_key, label;
```

- Index: `tone_eval_cases_set_idx`. Batch read (≥ 50 rows).

---

## 9. Caching Layer (Redis 7)

### 9.1 Cache key conventions

All keys prefixed with namespace `vs:`. Underscore separators. TTL is **explicit per key** (no global default).

### 9.2 Cache catalog

| Purpose | Key shape | Value | TTL | Invalidation |
|---------|-----------|-------|-----|--------------|
| **Session store** | `vs:sess:<sid>` | JSON `{user_id, csrf, last_seen}` | 30d rolling | On logout / soft-delete. |
| **Device session** | `vs:did:<sid>` | JSON `{device_id}` | 1y | On signup-and-link. |
| **CSRF secret** | `vs:csrf:<sid>` | random 32 bytes | 30d | Bound to session. |
| **Saju chart cache** | `vs:saju:chart:<chart_hash>` | JSON `SajuChart` | 24h | Cleared on `ENGINE_VERSION` bump (architecture §9.4). |
| **Active prompt cache** | `vs:tone:active:<prompt_key>` | JSON `{version, system_prompt, model}` | 5m | On `tone_prompt_versions` row activation (pub/sub). |
| **Tarot card metadata** | `vs:tarot:card:<index>` | JSON | 24h | On `tarot_cards` migration deploy. |
| **Intro audio resolution** | `vs:intro:<category>:<character>:<known>` | JSON `{audio_r2_key, subtitle, ms}` | 5m | On `intro_audio_clips` row activation. |
| **Today's tarot index (derived)** | `vs:tarot:idx:<subject_id>:<date_kst>` | INT `0..21` | until end of day KST | None (pure derivation; cache only). |
| **Weekly tarot free quota** | `vs:tarot:freequota:<subject_id>:<iso_week_kst>` | INT (count used; 0 or 1) | until Monday 00:00 KST | Atomic Lua increment; reset by TTL. |
| **Paywall entitlement summary** | `vs:ent:<user_id>` | JSON `{tokens:N, sub:{status, end}}` | 60s | On token consume / payment confirm / subscription change (pub/sub). |
| **Lifetime paid-single count** | `vs:upsell:paidcount:<user_id>` | INT | 5m | On payment confirm. |
| **Quote card public lookup** | `vs:quote:slug:<slug>` | JSON projection of row | 5m | On row update. |
| **Idempotency dedup (short)** | `vs:idem:<scope>:<key>` | "1" | 24h | TTL. |
| **Rate limit token bucket** | `vs:rl:<scope>:<subject>` | counter | window-based | TTL. |
| **arq worker queue** | `vs:arq:*` (managed by `arq`) | — | — | — |
| **OG bake lock** | `vs:og:lock:<quote_card_id>` | "1" | 60s | TTL. |

### 9.3 Cache invariants

- **Cache is never the source of truth.** Every cache miss must produce the same answer as a cache hit (correctness via Postgres).
- **Determinism caches are scoped to determinism inputs.** The saju chart cache key is `chart_hash` which includes `ENGINE_VERSION`; bumping the version automatically invalidates without manual purge.
- **Tarot determinism is not cached for correctness.** The SHA256 derivation is cheap; Redis is for read-skipping only (architecture §10). A Redis flush does not change the card a user sees.
- **Quota is Redis-primary with DB fallback.** If Redis is down, we fall back to the `tarot_draws_user_date_desc_idx` DB query (AP-33). Both must agree — Redis is incremented atomically only after DB INSERT succeeds.
- **PII never enters Redis.** Birth date plaintext is read once per session into the request context and dropped; never `SET` to Redis.

### 9.4 Pub/Sub channels (for cache busting)

- `vs:invalidate:prompt:<prompt_key>` — fires on `tone_prompt_versions` row activation; all app instances drop the cached prompt.
- `vs:invalidate:ent:<user_id>` — fires on token consume / payment confirm / subscription change.

---

## 10. Constraints & Validation

### 10.1 Database-level constraints (already in §4)

- All FKs declared; cascade rules explicit.
- All `NOT NULL` defaults are intentional choices, not omissions.
- All `CHECK` constraints on enum-like text columns (refunds reason, og_status, etc.).
- Partial uniques to enforce idempotency (signup grant, non-member trial, today's tarot, single active subscription).
- `birth_time_known` denormalized to avoid decrypt on hot path.

### 10.2 Application-level validation (Pydantic v2)

Items that cannot be expressed as DB constraints:

- **Birth date sanity**: not in future, year ∈ [1900, current_year]. (Onboarding form.)
- **Birth date solar/lunar conversion validity**: the `korean-lunar-calendar` library is asked to convert; failure → 400.
- **`Profile.name_optional`**: stripped of leading/trailing whitespace; rejected if contains control chars; max 10 chars (also DB-enforced).
- **Idempotency-Key header**: validated as UUIDv4/v7 format.
- **Tarot card index 0–21**: enforced both at app side (FR-013 derivation) and DB CHECK.
- **Audio duration bounds**: FR-007 (60–120 sec), FR-010/015 (25–45 sec); enforced at app side at upload time and DB CHECK on `reading_audio` and `tarot_draws`.
- **Cost ceiling NFR-007**: not a DB constraint; daily metrics job alerts if violated.

### 10.3 Cross-table integrity

| Rule | Enforcement |
|------|-------------|
| Reading.entitlement_kind ↔ exactly one of payment/subscription/free_token | DB CHECKs (§4.8). |
| Reading owner is `user_id` if signed-in, else `device_id` if free_token from device | DB CHECK (`device_id IS NULL OR entitlement_kind='free_token'`). |
| FreeToken owner is exactly one of user/device | DB CHECK (§4.7). |
| QuoteCard source_kind ↔ reading_id XOR tarot_id | DB CHECK (§4.16). |
| Subscription monthly_saju_remaining resets on period roll | Application: nightly cron + Toss webhook on period roll. Audit row written. |
| FR-029 correction_count never exceeds 2 | DB CHECK + application enforcement (server-only, never trusted from client). |

### 10.4 Idempotency surfaces

| Surface | Mechanism |
|---------|-----------|
| `POST /readings` | `readings.idempotency_key` UNIQUE. |
| `POST /tarot/today/flip` | `tarot_draws (user_id, date_kst)` partial UNIQUE. |
| `POST /payments/checkout` | `payments.toss_order_id` UNIQUE (client-generated). |
| Toss webhook | `payments.toss_payment_key` UNIQUE (partial). |
| Toss refund webhook | `refunds.toss_refund_id` UNIQUE (partial). |
| Signup grant | `free_tokens (user_id) WHERE kind='signup_grant'` partial UNIQUE. |
| Non-member trial grant | `free_tokens (device_id) WHERE kind='nonmember_trial'` partial UNIQUE. |
| Quote card share slug | `quote_cards.share_slug` UNIQUE. |

---

## 11. Data Retention & Privacy

### 11.1 Sensitive PII inventory

| Field | Classification | Storage | At rest |
|-------|---------------|---------|---------|
| `profiles.birth_dt_enc` | **Sensitive PII** (생년월일·시각, RRN-adjacent) | Postgres | envelope encrypted (NFR-005) |
| `profiles.name_optional` | Low-sensitivity PII (optional, ≤ 10 chars, no last name guaranteed) | Postgres | plaintext (architecture §5.3) |
| `users.email_hash` | Pseudonym | Postgres | hashed (SHA-256 of lowercased email) |
| `users.kakao_sub`, `apple_sub`, `toss_id` | Provider IDs | Postgres | plaintext (opaque, not by themselves identifying) |
| `payments.*` | Transaction metadata only | Postgres | plaintext; **no card data** (NFR-006) |
| TTS audio | Voice content + reading text echo | R2 (signed URL only) | server-side encryption (R2 default) |
| Reading transcripts | Reading content (no PII) | Postgres | plaintext |
| `audit_events` | PII access log | Postgres | plaintext (event metadata only, never PII payloads) |

### 11.2 Soft delete vs hard delete

- **`users` and `profiles`**: soft delete (`deleted_at`). 30-day grace window for undo.
- **All other tables**: hard delete via worker (cascade per ON DELETE rules) **at the end of the grace window** or **immediately on user-confirmed hard erasure**.
- **Soft delete is invisible to the app** — all read paths filter `deleted_at IS NULL`. Auth middleware short-circuits a soft-deleted user with 401.

### 11.3 GDPR / PIPA right-to-be-forgotten flow

User-initiated erasure (`/me/account` → "탈퇴"):

```
1. UI confirms intent twice (FR-029 pattern: confirm modal with copy + checkbox).
2. App writes audit_events(action='soft_delete', subject_user_id=...) and sets users.deleted_at + profiles.deleted_at.
3. Session invalidated (Redis SESS key DEL).
4. Schedule arq job `erase_user(user_id)` at deleted_at + 30 days.
5. erase_user job:
   a. Read all R2 keys to delete: reading_audio.r2_key, reading_followups.audio_r2_key,
      tarot_draws.audio_r2_key, quote_cards.og_r2_key.
   b. Issue R2 DELETE batch.
   c. DELETE FROM cascade root: users (cascades via FK rules where defined; for other tables,
      app-coded order — readings → reading_followups → reading_transcripts → reading_audio →
      tarot_draws → quote_cards → free_tokens → payments → subscriptions → refunds → profiles → users).
   d. Insert audit_events(action='hard_delete', subject_user_id=...) BEFORE deleting the row (so the audit row outlives the user; subject_user_id may then point at a nonexistent FK — see below).
6. AuditEvents.subject_user_id FK is declared `ON DELETE SET NULL` so the audit row survives the erasure.
```

For force-immediate erasure (regulatory request): skip step 4, run step 5 immediately.

### 11.4 Encryption envelope rotation (NFR-005)

- KEK is held by KMS; rotation policy: every 12 months OR on incident.
- Rotation = `kek_version` bump + lazy re-wrap on next profile read (write back). No batch re-encryption needed (ciphertext stays the same since DEK is unchanged).
- DEK rotation is a separate, rarer operation (decrypt with old DEK → re-encrypt with new DEK → re-wrap with current KEK). Only performed on key compromise.

### 11.5 Logging redaction

Per architecture §12.1: structured JSON logs apply a redaction filter that strips fields named `birth_dt*`, `name_optional`, `paymentKey`, `cardNumber*`, `cvv*`. Plaintext PII never reaches logs.

### 11.6 Audio retention (A-07 open)

- v1 default: indefinite (FR-028 history replay; `reading_audio.expires_at IS NULL`).
- When policy is adopted (e.g., 12-month aging), a scheduled worker scans `reading_audio` for `created_at < now() - interval '12 months'`, sets `expires_at`, and on the next sweep deletes the R2 object + sets the audio key to NULL on the Postgres row. The history row remains visible; FR-028 AC handles the "expired" UI state.

### 11.7 Data export (PIPA Art. 35)

- User can request export. `audit_events(action='export_data')` written; arq job generates a JSON dump of all user-owned rows (decrypted birth date included, since the user owns the data). Delivered via signed R2 URL valid for 24 h.

---

## 12. Entity-Relationship Diagram

```mermaid
erDiagram
  USERS ||--o| PROFILES                : "1:1 (profile_user_uq)"
  USERS ||--o{ SAJU_CHARTS             : "1:N (new chart per FR-029 edit)"
  USERS ||--o{ READINGS                : "1:N"
  USERS ||--o{ FREE_TOKENS             : "1:N (member-owned)"
  USERS ||--o{ PAYMENTS                : "1:N"
  USERS ||--o| SUBSCRIPTIONS           : "1:0..1 active"
  USERS ||--o{ TAROT_DRAWS             : "1:N (member)"
  USERS ||--o{ AUDIT_EVENTS            : "1:N (subject)"
  DEVICES }o--o| USERS                 : "0..1:1 (linked_user_id)"
  DEVICES ||--o{ FREE_TOKENS           : "1:N (nonmember)"
  DEVICES ||--o{ TAROT_DRAWS           : "1:N (nonmember)"
  DEVICES ||--o{ READINGS              : "1:N (nonmember trial only)"

  SAJU_CHARTS ||--o{ READINGS          : "1:N (chart_id)"

  READINGS ||--|| READING_TRANSCRIPTS  : "1:1"
  READINGS ||--|| READING_AUDIO        : "1:1"
  READINGS ||--o{ READING_FOLLOWUPS    : "1:0..3"
  READINGS ||--o| QUOTE_CARDS          : "1:0..1"
  READINGS ||--o{ TONE_VIOLATION_EVENTS : "1:N"
  READINGS }o--|| FREE_TOKENS          : "0..1 entitlement"
  READINGS }o--|| PAYMENTS             : "0..1 entitlement"
  READINGS }o--|| SUBSCRIPTIONS        : "0..1 entitlement"

  TAROT_DRAWS ||--o| QUOTE_CARDS       : "1:0..1"
  TAROT_DRAWS ||--o{ TONE_VIOLATION_EVENTS : "1:N"
  TAROT_DRAWS }o--o| PAYMENTS          : "0..1"
  TAROT_DRAWS }o--o| SUBSCRIPTIONS     : "0..1"

  PAYMENTS ||--o{ REFUNDS              : "1:N"
  PAYMENTS }o--o| SUBSCRIPTIONS        : "0..1 (recurring billing)"
  REFUNDS }o--o| FREE_TOKENS           : "0..1 (fallback grant)"
  REFUNDS }o--o| READINGS              : "0..1 (cause)"

  TAROT_CARDS ||--o{ TAROT_DRAWS       : "1:N (card_index)"

  TONE_PROMPT_VERSIONS ||--o{ READINGS : "1:N (snapshot)"
  TONE_PROMPT_VERSIONS ||--o{ TAROT_DRAWS : "1:N (snapshot)"

  USERS {
    uuid id PK
    text kakao_sub
    text apple_sub
    text toss_id
    char64 email_hash
    timestamptz created_at
    timestamptz deleted_at
  }

  PROFILES {
    uuid id PK
    uuid user_id FK
    jsonb birth_dt_enc "envelope encrypted"
    bool  birth_is_lunar
    bool  birth_time_known
    text  gender
    text  name_optional
    int   correction_count
  }

  SAJU_CHARTS {
    uuid id PK
    uuid user_id FK
    char64 chart_hash UQ
    jsonb pillars
    text engine_version
    bool time_known
  }

  FREE_TOKENS {
    uuid id PK
    uuid user_id FK
    uuid device_id FK
    text kind
    timestamptz consumed_at
    uuid consumed_by_reading_id FK
  }

  READINGS {
    uuid id PK
    uuid user_id FK
    uuid device_id FK
    uuid chart_id FK
    text category
    text entitlement_kind
    uuid payment_id FK
    uuid subscription_id FK
    uuid free_token_id FK
    text status
    uuid idempotency_key UQ
    text tone_prompt_version
    int cost_krw
  }

  READING_FOLLOWUPS {
    uuid id PK
    uuid reading_id FK
    smallint slot_index
    text question_text
    text answer_text
    text audio_r2_key
    timestamptz tapped_at
  }

  READING_AUDIO {
    uuid reading_id PK FK
    text r2_key UQ
    int duration_ms
    timestamptz expires_at
  }

  TAROT_DRAWS {
    uuid id PK
    uuid user_id FK
    uuid device_id FK
    date date_kst
    smallint card_index
    text entitlement_kind
    text audio_r2_key
    text status
  }

  TAROT_CARDS {
    smallint card_index PK
    text slug UQ
    text display_name_kr
    text meaning_full_kr
    text art_r2_key
  }

  PAYMENTS {
    uuid id PK
    uuid user_id FK
    text type
    text method
    int amount_krw
    text toss_order_id UQ
    text toss_payment_key
    text status
  }

  SUBSCRIPTIONS {
    uuid id PK
    uuid user_id FK
    text status
    text toss_billing_key UQ
    int monthly_amount_krw
    timestamptz current_period_end
    smallint monthly_saju_remaining
  }

  REFUNDS {
    uuid id PK
    uuid payment_id FK
    uuid reading_id FK
    int amount_krw
    text reason
    text status
    uuid fallback_token_id FK
  }

  QUOTE_CARDS {
    uuid id PK
    text share_slug UQ
    text source_kind
    uuid reading_id FK
    uuid tarot_id FK
    text quote_text
    text og_r2_key
    text og_status
  }

  TONE_PROMPT_VERSIONS {
    uuid id PK
    text prompt_key
    text version
    text character_key
    text model
    text system_prompt
    bool is_active
  }

  TONE_VIOLATION_EVENTS {
    uuid id PK
    uuid reading_id FK
    uuid tarot_id FK
    text layer
    text severity
    text category_tag
  }

  TONE_EVAL_CASES {
    uuid id PK
    text case_set_version
    text label
    text prompt_key
    jsonb input_context
  }

  INTRO_AUDIO_CLIPS {
    uuid id PK
    text category
    text character_key
    text audio_r2_key
    text subtitle_text
    int  duration_ms
    bool birth_time_known_variant
    bool is_active
  }

  CHARACTER_VOICES {
    text character_key PK
    text supertone_voice_id
    numeric speech_rate
    numeric pitch_shift
  }

  DEVICES {
    uuid id PK
    uuid device_id_client UQ
    uuid linked_user_id FK
  }

  AUDIT_EVENTS {
    uuid id PK
    text actor_kind
    uuid actor_user_id FK
    uuid subject_user_id FK
    text action
    jsonb detail
  }
```

---

## 13. Scaling Notes

### 13.1 Current design — 12-month target (50k signups, ~20k MAU)

- **Postgres**: single primary, 4 vCPU / 8 GB RAM is comfortable. Row counts:
  - `users` ~50k, `profiles` ~50k, `saju_charts` ~75k (avg 1.5 due to FR-029 edits + cache reuse).
  - `readings` ~150k (3 lifetime per active user), `reading_followups` ~300k (avg 2 taps).
  - `tarot_draws` ~1.2M (60 per active user-year × 20k MAU).
  - `payments` ~50k.
  - All comfortably under 100 GB total table size.
- **Redis**: Upstash pay-per-request tier. Session + entitlement caches dominate; well under 1 GB working set.
- **R2**: ~1.5 MB per main reading mp3 × 150k = 225 GB. Egress is the cost lever, not storage.

### 13.2 At 10× scale (~200k MAU)

**Reads (predominant)**:

- Postgres single primary still serviceable for writes; add **1 read replica** for:
  - `/me/history` list and replay reads (AP-27, AP-28)
  - `/me/billing` payment history (AP-39)
  - Public `/share/[slug]` (AP-43)
- Move read-only endpoints to replica via SQLAlchemy execution options.

**Writes**:

- `tarot_draws` becomes the hottest table (~12M rows/year). **Partitioning candidate: monthly partitions by `date_kst`.** Each partition ~1M rows, easy to age out.
- `readings` reaches ~1.5M lifetime; not yet partition-worthy but watch index size on `readings_user_created_idx`.
- `audit_events` becomes high-volume; **partition monthly by `created_at`** and archive partitions > 12 months old to R2 as Parquet.

**Caching**:

- Entitlement cache TTL can be increased to 5 min once invalidation pub/sub is proven reliable.
- Add a per-instance LRU for tarot card metadata + prompts (already process-local memoized).

**Compute**:

- Saju engine (`compute_chart`) is the only CPU-bound hot path. At 10× still cheap (< 50 ms / call). No service split needed.
- Reading pipeline: scale FastAPI to 6–10 instances (architecture §16). SSE is stateless.

### 13.3 At 100× scale (~2M MAU) — what breaks

| Component | Pressure | Action |
|-----------|----------|--------|
| `tarot_draws` writes | ~100M rows/year | Time-partitioning (monthly) becomes mandatory; consider moving the hot week to a smaller table and aging to compressed partitions. |
| `readings` audio storage | ~5 TB/year on R2 | Adopt audio retention policy (A-07): cold-tier after 90 days, delete after 12 months unless user paid for "keep forever" (v2 feature). |
| `audit_events` | ~500M rows | Move to a separate logging DB (ClickHouse) or stream-only (Logtail). |
| Postgres write throughput | Approaches managed Postgres ceiling | Vertical scale primary; if still insufficient, **shard `tarot_draws` by `user_id` hash** (most queries are per-user, sharding is clean). |
| Redis | Hot keys on `vs:ent:<user_id>` | Use Redis Cluster; shard by `user_id`. |
| Webhook fanout | Toss recurring billing scale | Move webhook handler to dedicated process group to isolate from streaming traffic. |
| LLM rate limits | Anthropic concurrency at peak (OQ-10) | Multi-region Anthropic clients + queueing layer with user-facing wait UI (not in v1). |
| Saju engine | Still cheap | First component to **peel out as a stateless microservice** for compute scaling (architecture §16 #4). |

At 100×, v1's modular monolith is the wrong shape. The migration to per-domain services is signposted; the schema does not need to change to support that migration — each table maps cleanly to a future service boundary (`users`/`auth`, `profiles`+`saju_charts`/`saju`, `readings`+`reading_*`/`reading`, `tarot_*`/`tarot`, `payments`+`subscriptions`+`refunds`/`billing`, `quote_cards`/`content`, `tone_*`/`guardrail`).

---

## 14. Open Questions / Items Deferred

| ID | Question | Resolved when |
|----|----------|---------------|
| DQ-01 | Exact price tier (A-01) — affects `payments.amount_krw` defaults and refund handling. Schema is price-agnostic; only seed config changes. | A/B selection by Product. |
| DQ-02 | Audio retention policy (A-07) — drives whether `reading_audio.expires_at` is populated at insert or by a backfill. | Storage costs review at 6 months post-launch. |
| DQ-03 | Whether `email_hash` is collected from Kakao at all (Kakao does not always expose verified email). If not, drop column or accept always-NULL. | Kakao OAuth scope confirmed. |
| DQ-04 | Should `audit_events.subject_user_id` survive `users` hard-delete? Current design uses `ON DELETE SET NULL`. PIPA requires audit log retention — this is correct. Re-confirm with legal. | Pre-launch legal review. |
| DQ-05 | Toss recurring billing in WebView (R-04) — if disallowed, `subscriptions` rows simply never get created from Toss WebView channel; no schema change required. | Toss policy confirmation (DEP-02). |
| DQ-06 | Subscriber entitlement for tarot — `subscriptions.monthly_saju_remaining` is tracked but daily tarot is unlimited; tracked only by absence of `free_quota` enforcement. Confirm no per-day cap is intended. | Confirmed: PRD §5.5 and FR-022 say unlimited. |
| DQ-07 | `tone_eval_cases.case_set_version` strategy — pinning the version per release to make CI runs deterministic. Schema supports it; release process defines it. | CI pipeline build (architecture §13.2). |

---

## 15. Self-Review

### 15.1 Access-pattern coverage

Walked every screen in `ux_spec.md` §3 and every API endpoint in `architecture.md` §6:

- All 26 screens have at least one query pattern (AP-01 through AP-54) serving them. Specifically:
  - Onboarding (Screens 2–5): AP-10 (write profile), AP-11 (compute chart), AP-19 (grant non-member trial).
  - Category/Intro/Paywall (Screens 6, 7, 8): AP-09, AP-16/AP-17, AP-21, AP-46.
  - Reading player (Screen 9): AP-23, AP-12, AP-24, AP-30, AP-48.
  - Followups (Screen 10): AP-26.
  - Reading end / quote (Screen 11, 23): AP-42, AP-43, AP-44.
  - Tarot screens (Screens 12, 13, 14, 24): AP-31, AP-32, AP-33, AP-34, AP-45.
  - Auth (Screen 15): AP-02, AP-03, AP-04, AP-05.
  - My Page (Screens 16, 17, 18, 19, 20, 21): AP-09, AP-12, AP-27, AP-28, AP-39, AP-14, AP-15.
  - Upsell (Screen 22): AP-22.
  - Signup modal (Screen 25): AP-05, AP-07, AP-18.
  - Error screens (26): AP-49 (telemetry).
- LLM/TTS pipeline ops: AP-48 (prompt), AP-47 (voice), AP-30 (cost), AP-49 (tone events). All covered.
- Background workers: AP-29 (audio finalize), AP-44 (OG bake), AP-41 (refund), AP-54 (erasure). All covered.

No uncovered access patterns identified.

### 15.2 Index justification re-check

Every index in §5 was traced to a specific AP-#. Indexes that were considered and **rejected** because no access pattern justified them:

- `readings_chart_id_idx` — no query reads readings by chart_id alone. Cascade isn't a query.
- `payments_status_idx` (global) — no admin view in v1 requires it; replaced by user-scoped partial indexes.
- `reading_followups_question_text_gin` — no full-text search.
- `users_created_at_idx` — no list-all-users endpoint.
- `audit_events_actor_idx` — current rollups are by subject and action only.

### 15.3 Constraint audit

For every column I asked "should this be NOT NULL?" and "should this have a UNIQUE/CHECK?". Notable choices:

- **NOT NULL by default**: every timestamp `created_at`, every status enum, every owner ID where the table is owner-required.
- **NULL allowed** only when business-meaningfully optional: `name_optional`, `consumed_at` (NULL = available token), `paid_at` (NULL = not yet paid), `cancel_requested_at`, `expires_at`, partial-unique provider IDs.
- **Partial uniques** used liberally to express "at most one of X per scope" invariants in the database itself rather than relying on app code.
- **Owner-XOR checks** on `free_tokens`, `tarot_draws`, `quote_cards`, and the entitlement triplet on `readings` — these are correctness boundaries, not stylistic choices.

### 15.4 N+1 / performance trace

I traced three key read paths:

1. **`/reading/paywall` load** — one composite CTE (§8.6) returns tokens + subscription. No N+1.
2. **`/me/history/[id]` replay load** — one JOIN with `json_agg` over followups (§8.10). Single round trip.
3. **`/me/billing` page** — two queries (subscription + payments list); both indexed; payments list paginated. Acceptable; could be fused into one round trip if needed but readability wins.

Tarot quota check (AP-33) is Redis-primary with DB fallback (§8.13). Eliminates a Postgres read on every page load of `/tarot`.

Entitlement summary (AP-16/21) is cached in Redis with explicit invalidation (§9.2 `vs:ent:<user_id>`).

### 15.5 Confidence

**High.** The schema follows directly from the documented access patterns, the encryption envelope structure matches NFR-005, idempotency boundaries are explicit, and the migration policy is forward-only consistent with architecture §15. Open questions in §14 are configuration / policy items, not structural risks.
