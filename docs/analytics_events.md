# Analytics Events — VoiceSaju

Version: 1.0 (ISSUE-080)
PRD-Ref: NFR-016 (success metrics §10.2).
Architecture-Ref: §12.1 (observability stack).

This document is the **single source of truth** for the analytics event schema.
Both the frontend SDK (`web/src/lib/analytics/events.ts`) and the backend
emitter (`api/voicesaju/analytics/events.py`) MUST stay aligned with this table.
A change here = a change in BOTH SDKs in the same PR.

---

## Design principles

1. **Vendor-agnostic.** Phase-1 ships a Noop / Logging adapter; the real
   provider (Mixpanel, PostHog, Amplitude — pending DEP-XX) is swapped in by
   replacing the adapter, never by editing call sites.
2. **Never crash the caller.** Every emit path swallows transport errors and
   logs a warning. Analytics is fire-and-forget.
3. **Typed at the source.** TypeScript discriminated unions on the frontend,
   typed helper functions on the backend. Adding a new event is a type
   change, not a magic-string change.
4. **PII discipline.** No `birth_dt`, no payment keys, no JWT body fragments.
   Event properties are the bare minimum needed for funnel analysis.

---

## Frontend events

Frontend emits funnel events from the SPA. See
`web/src/lib/analytics/events.ts`.

| Event | Properties | Fired from | AC |
|-------|-----------|-----------|-----|
| `onboarding_step` | `{ step: 1 \| 2 \| 3 \| 4 }` | `/onboarding/birth-date`, `/onboarding/birth-time`, `/onboarding/gender`, `/onboarding/name` (mount) | AC1 — 4 events per complete onboarding |
| `signup` | `{ provider: 'kakao' \| 'apple' }` | OAuth callback success handler | NFR-016 |
| `paywall_view` | `{ category: string }` | Paywall screen mount | NFR-016 |
| `paywall_pay` | `{ category: string; amount_krw: number }` | Pay CTA tap | NFR-016 |
| `reading_complete` | `{ category: string }` | Reading SSE `done` event | NFR-016 |
| `quote_share` | `{ channel: 'instagram' \| 'kakao' \| 'download' }` | Share sheet tap (Screen 17) | AC2 |

Step ordering matches the onboarding flow in `docs/wireframes.md`:

1. `birth-date` — Screen 2.
2. `birth-time` — Screen 3.
3. `gender` — Screen 4.
4. `name` — Screen 5.

---

## Backend events

Backend emits transactional events that the frontend cannot see (payment
webhooks, subscription lifecycle). See `api/voicesaju/analytics/events.py`.

| Event | Properties | Fired from | AC |
|-------|-----------|-----------|-----|
| `payment_completed` | `{ payment_id: str; amount_krw: int; category: 'single' \| 'subscription' }` | `payment/webhook.py::_handle_payment_done` (after commit) | AC3 |
| `subscription_started` | `{ subscription_id: str; plan: str }` | Subscription becomes active (creation or `SUBSCRIPTION_RENEWED`) | NFR-016 |
| `subscription_cancelled` | `{ subscription_id: str; reason: str \| null }` | Webhook `SUBSCRIPTION_CANCELED` or self-serve cancel | NFR-016 |

All backend events include `user_id` at the envelope level (not in
`properties`).

---

## Acceptance criteria → event mapping

- **AC1: Complete onboarding → 4 `onboarding_step` events sent.**
  Verified by `web/src/lib/analytics/__tests__/events.test.ts::trackOnboardingStep — AC1` (asserts steps 1..4 are emitted) and is wired into the four onboarding pages via mount `useEffect`.

- **AC2: Share quote card → `quote_share` event with `channel=...`.**
  Verified by `web/src/lib/analytics/__tests__/events.test.ts::trackQuoteShare — AC2` (one test per channel value).

- **AC3: Payment completes → `payment_completed` event with amount + category.**
  Verified by `api/tests/integration/payment/test_webhook.py::test_payment_done_emits_payment_completed_event` (full webhook → handler → analytics emit path).

---

## Adding a new event

1. Add the event to the table above (this file).
2. Frontend: extend `AnalyticsEvent` in `web/src/lib/analytics/events.ts` +
   add a typed helper (`trackXxx`).
3. Backend: add a typed helper to `api/voicesaju/analytics/events.py`.
4. Add tests on both sides — one happy-path, one failure-mode.
5. Reference the event in PRD or requirements.md if it represents a new
   metric.
