# UX Spec — VoiceSaju

Version: 1.0
Source: PRD.md (2026-05-29), requirements.md (17 user stories, 36 FRs, 17 NFRs), business_analysis.md
Designer confidence: **High** — flows align tightly with PRD §5 and requirements §3–4. Open variables (exact prices, Toss WebView capability) are flagged inline as assumptions and do not block IA/flow definition.

Scope notes:
- Two channels: **Web** (Next.js app, mobile-first responsive) and **Toss mini-app WebView** (same codebase, runtime-detected adaptations).
- Two characters: **시니컬 누님** (saju reader — spicy/blunt MZ adult female) and **신비로운 노인 도사** (tarot reader — mystical elderly sage).
- Voice + subtitle simultaneous display is a load-bearing accessibility commitment (NFR-015): every audio surface must render synced Korean captions.

---

## 1. Information Architecture

### 1.1 Sitemap (Top-level)

```
VoiceSaju
├── / (Landing — hero + CTA "지금 풀이 받기" / "오늘의 타로")
├── /onboarding
│   ├── /onboarding/birth-date         (Step 1: 양력/음력 토글 + 생년월일)
│   ├── /onboarding/birth-time         (Step 2: 시각 + "모름")
│   ├── /onboarding/gender             (Step 3: 여/남)
│   └── /onboarding/name               (Step 4: 이름 옵셔널)
├── /reading
│   ├── /reading/category              (연애 / 직장 / 금전 선택)
│   ├── /reading/intro                 (15초 누님 인트로 + skip)
│   ├── /reading/paywall               (결제 옵션 + 무료 토큰)
│   ├── /reading/play                  (본 풀이 1~2분, 자막+음성+명식)
│   ├── /reading/followup              (꼬리질문 3개 + 답변 재생)
│   └── /reading/end                   (세션 종료 + 명대사 카드)
├── /tarot
│   ├── /tarot                         (오늘의 카드 — face-down)
│   ├── /tarot/play                    (뒤집힌 카드 + 노인 도사 음성)
│   ├── /tarot/paywall                 (주 1회 소진 시 결제)
│   └── /tarot/end                     (세션 종료 + 명대사 카드)
├── /share/[cardId]                    (명대사 카드 공유 랜딩 — OG 이미지)
├── /auth
│   ├── /auth/login                    (카카오 + 애플)
│   ├── /auth/signup-prompt            (비회원 후 1초 가입 CTA — 모달이 기본)
│   └── /auth/callback                 (OAuth 콜백)
├── /me                                (마이페이지 홈)
│   ├── /me/saju                       (내 사주 명식)
│   ├── /me/history                    (풀이 히스토리)
│   ├── /me/history/[id]               (히스토리 재생)
│   ├── /me/billing                    (결제·구독 관리)
│   ├── /me/billing/subscribe          (구독 결제)
│   ├── /me/edit-saju                  (사주 정보 수정 — 2회 무료)
│   └── /me/account                    (로그아웃·탈퇴)
├── /upsell/subscription               (단건 2회차 결제 후 자동 노출)
├── /legal
│   ├── /legal/terms                   (이용약관 — "오락 목적" 면책)
│   ├── /legal/privacy                 (개인정보 처리방침)
│   └── /legal/refund                  (환불 정책)
└── /error
    ├── /error/404
    ├── /error/payment-failed
    └── /error/llm-failed              (캐릭터 캐싱 멘트)
```

### 1.2 Navigation (Two-bar pattern, mobile-first)

**Bottom Tab Bar** (always visible on logged-in users; hidden during full-screen audio playback to maximize reading focus):
1. 사주 (`/reading/category` or last reading entry point)
2. 오늘의 타로 (`/tarot`)
3. 마이 (`/me`)

**Top App Bar** (per-screen contextual):
- Left slot: back arrow (during multi-step flows) or character avatar (on home/tarot).
- Center slot: screen title or step indicator ("1/4").
- Right slot: skip (during intro), share (post-reading), or close-X (during modals).

Non-members see the bottom tab bar with a "마이" slot that opens the signup modal instead of `/me`.

### 1.3 Toss Mini-App WebView adaptations

- Detect WebView context via `navigator.userAgent` containing `Toss/` + Toss JS bridge presence.
- **Hide** web-only auth screens (`/auth/login`) — Toss ID handoff is automatic.
- **Replace** payment options on `/reading/paywall` and `/tarot/paywall` with TossPay one-click only (no KakaoPay).
- **Replace** "Apple로 시작하기" / "카카오로 시작하기" buttons on signup prompts with "토스로 계속하기" (single-button).
- **Constrain** share buttons on `/reading/end` and `/tarot/end` to channels the WebView supports (subject to A-04 confirmation — design fallback: "이미지 저장" + "링크 복사" minimum).
- **Top bar**: defer to Toss native chrome — hide our top app bar where it would collide with Toss header.

### 1.4 Content hierarchy principles

- **Voice content is primary** — character illustration, subtitle, and player controls are the visual stack on any playback screen. Saju chart and metadata are secondary (collapsed by default on small viewports, expandable).
- **One decision per screen** during paid flows (category → intro → paywall → play). No competing CTAs.
- **Free → paid → share** is the canonical loop: every paid session must terminate at the quote card share screen (US-08).

---

## 2. Key User Flows

Every flow includes a happy path, error paths, and edge cases. Step numbering is one user action per step.

---

### Flow A: First-time Visitor → Non-member Free Saju Reading

**Trigger**: User lands on `/` from organic search, shared link, or Toss mini-app discovery.

**Steps (happy path)**:
1. User taps **"지금 풀이 받기"** CTA on `/` → routes to `/onboarding/birth-date`.
2. User picks 양력 or 음력 toggle, selects birth date → taps **"다음"** → `/onboarding/birth-time`.
3. User selects birth hour + minute OR taps **"시간은 모르겠어요"** checkbox → taps **"다음"** → `/onboarding/gender`.
4. User taps 여 or 남 → routes to `/onboarding/name`.
5. User types name (or taps **"건너뛰기"**) → taps **"완료"** → routes to `/reading/category`.
6. User taps one of three category cards (연애 / 직장 / 금전) → routes to `/reading/intro`, 15-sec 누님 인트로 audio + subtitle plays automatically.
7. At intro end (or on skip), routes to `/reading/paywall`. Free trial token detected (device-stored) → **"무료로 풀이 받기"** CTA is the primary button.
8. User taps **"무료로 풀이 받기"** → token consumed → routes to `/reading/play` and 본 풀이 begins streaming within 3 sec (NFR-001).
9. User listens to 1–2 min voice + subtitle + 명식 sidebar.
10. Reading ends → 3 follow-up buttons auto-render within 1 sec (FR-009).
11. User taps a follow-up → 30–40 sec answer plays. (Repeat up to 3 times, or tap **"이만 마칠게요"**.)
12. Routes to `/reading/end` → quote card generated within 3 sec → share CTAs revealed.
13. **Signup prompt modal appears** with copy "결과 저장하려면 1초 가입" (US-02 / FR-003).

**Success outcome**: User has completed first paid-equivalent reading without payment, sees signup CTA, has shareable quote card.

**Error paths**:
- Step 2: Invalid date (e.g., Feb 30) → inline validation error: "유효한 날짜를 입력해주세요" — block "다음".
- Step 6: Intro audio fails to load → fallback to subtitle-only intro with banner "음성을 준비 중이에요" + auto-advance to paywall after 15 sec.
- Step 7: User refreshes during paywall → free trial token state restored from localStorage; if localStorage cleared → user is now treated as new device with fresh token (Assumption A-09 accepted behavior).
- Step 8: LLM call fails → display "별기운이 잠시 약하네…" character message + auto-credit a retry token (no payment was taken) + offer "다시 시도" button (FR-033). Routes back to `/reading/category` on second failure.
- Step 8: TTS first chunk > 5 sec → subtitle-only fallback banner "음성 서비스가 일시적으로 불가합니다. 텍스트로 풀이를 제공합니다" (FR-034). Reading continues as text. Quote card still generates.
- Step 9: Network drops mid-playback → audio pauses, banner "네트워크 연결이 끊겼습니다", auto-resume on reconnect within 60 sec (FR-035). After 60 sec → "다시 시작" button.
- Step 11: User double-taps a follow-up button → second tap ignored while generating (FR-010 AC).
- Step 12: Quote card generation fails → fallback static category-themed card with hard-coded spicy quote for that category (FR-018).

**Edge cases**:
- User has `birth_time_unknown=true` → intro audio variant must include "시간을 모르면 큰 줄기는 보지만…" canned phrase (FR-002).
- User navigates back during `/reading/play` → confirm modal "풀이를 중단하시겠어요? 무료 토큰은 복구되지 않아요." (free trial branch shows different copy: "체험 풀이를 다시 받을 수 없어요. 정말 나갈까요?")
- User backgrounds the tab during playback → audio pauses (browser default); on resume, user must tap play button (Safari autoplay policy edge).
- User signs up mid-flow via the prompt: do NOT regrant free token (FR-003 AC — non-member token and member token are separate but a user who already consumed non-member free trial does not get a duplicate member free token).

---

### Flow B: Logged-in User → Paid Saju Reading + Follow-ups

**Trigger**: Logged-in user taps **사주** tab or "또 한 번 풀이 받기" from `/me`.

**Steps**:
1. Routes to `/reading/category` (saju data is pre-loaded — no onboarding re-entry per US-15).
2. User taps a category → `/reading/intro` plays 15-sec audio.
3. Intro ends → `/reading/paywall`. Paywall shows three rows:
   - **무료 토큰 사용** (if available — new member single-use, FR-017)
   - **단건 결제** ([5,900원] — exact price A-01) with category badge
   - **구독으로 더 저렴하게** (월 [9,900원])
4. User taps **단건 결제** → Toss Payments SDK modal opens.
5. Web: user selects 토스페이 OR 카카오페이 → confirms.
6. Payment webhook verified server-side → reading unlocks → `/reading/play` streams within 3 sec.
7. Same playback + follow-up + quote card sequence as Flow A steps 9–12.
8. If this is the user's **2nd lifetime single purchase** → after `/reading/end`, automatically routes to `/upsell/subscription` once (FR-025, US-11).

**Success outcome**: Paid session completed, payment receipt stored, audio cached for replay in history (FR-028).

**Error paths**:
- Step 5: Payment fails (insufficient funds, card error) → Toss SDK returns error → user remains on `/reading/paywall` with banner "결제가 실패했어요. 카드를 확인해주세요." + "다시 결제하기" button (FR-036).
- Step 6: Webhook verification fails (rare race) → reading blocked, banner "결제 확인 중이에요. 잠시 후 다시 시도해주세요." Auto-retry every 10 sec for 60 sec.
- Step 6: LLM fails post-payment → "별기운이 잠시 약하네…" message + auto-refund initiated within 60 sec OR free reading token credited as fallback (FR-023). Notification: "환불 또는 무료 이용권이 지급되었습니다."
- Step 7: TTS fails post-payment → text fallback (FR-034). NO refund — text is deemed equivalent value (FR-034 AC).
- Step 8: User dismisses upsell → routes to `/me` (does not re-show — FR-025 "exactly once").

**Edge cases**:
- User has both an unused free token AND chooses to pay anyway → only one charge happens; token stays. UI should not silently consume the token.
- User triggers payment in Toss WebView: KakaoPay button must be hidden (FR-024). Only TossPay one-click is shown.
- Subscriber takes this flow → paywall is bypassed entirely; `/reading/paywall` routes through and immediately consumes the monthly saju entitlement (FR-022). Show inline note: "이번 달 구독 풀이 1회를 사용합니다."
- Subscriber whose monthly saju entitlement is consumed → paywall shows "이번 달 사주는 이미 받으셨어요. 다음 갱신일 [date]" + offer single-purchase top-up.

---

### Flow C: Daily Tarot

**Trigger**: User taps **오늘의 타로** bottom tab, or lands on `/tarot` from external share link.

**Steps**:
1. Routes to `/tarot`. Top banner: **"이번 주 무료 1회 남음"** (or 0회 if used).
2. Center: face-down tarot card illustration, "오늘의 카드를 뒤집어보세요" subtitle below.
3. User taps the card.
4. Card-flip animation (300–600 ms, FR-012) plays → card front (one of 22 major arcana) revealed.
5. Within 2 sec of animation end (NFR-003), 노인 도사 voice begins, subtitle synced.
6. 30–40 sec reading plays with 노인 도사 illustration adjacent to card.
7. Reading ends → routes to `/tarot/end` → quote card (purple variant) generated and share CTAs shown.

**Success outcome**: User has consumed their free daily tarot (quota decremented), has shareable quote card.

**Error paths**:
- Step 1: Quota is 0 (used) AND user is not a subscriber → tapping the card routes to `/tarot/paywall` (no flip). Paywall shows 단건 + 구독 options.
- Step 4: Card art asset fails to load → fallback to category-color tinted card silhouette with card name text overlay.
- Step 5: LLM/TTS fails → text-only reading fallback (FR-034). No refund (free tier).
- Step 6: Network drop → pause + resume per FR-035.

**Edge cases**:
- Same user re-loads `/tarot` on same KST date → same card index, same flip state preserved. If audio already played to completion that day, show "오늘의 카드는 이미 뒤집었어요. 풀이를 다시 들어보시겠어요?" with "다시 듣기" button.
- Cross-midnight KST: at 00:00:00 KST, page auto-refreshes (or banner appears: "새로운 카드가 준비됐어요. 새로고침").
- Subscriber: no quota banner shown; unlimited replays allowed.
- Non-member: device ID seeds card. If user signs up later that same day, the card seed switches to user_id — card may change. Edge handled by: "가입을 환영해요! 새로운 카드가 준비됐어요." (acceptable behavior per FR-013).

---

### Flow D: Payment (Web — split for KakaoPay vs TossPay)

**Trigger**: User taps a paid CTA on any paywall (`/reading/paywall` or `/tarot/paywall` or `/me/billing/subscribe`).

**Steps**:
1. Toss Payments SDK modal opens with two payment buttons: **토스페이** / **카카오페이**.
2. User selects a method, confirms amount.
3. Toss redirects to provider (e.g., kakaopay.com) for auth.
4. Provider returns success → Toss webhook fires to our backend.
5. Backend verifies webhook signature, marks transaction completed, grants entitlement.
6. Client polls or receives socket message → entitlement unlocked → routes to playback.

**Success outcome**: Receipt stored in `/me/billing`; reading entitlement granted.

**Error paths**:
- Step 2: User cancels modal → returns to paywall, no error message (silent dismiss).
- Step 3: Provider auth fails → Toss returns failure code → SDK modal shows error → on close, banner on paywall: "결제가 실패했어요. 다시 시도하시겠어요?"
- Step 4: Webhook delayed > 30 sec → show loading state with "결제 확인 중..." spinner; timeout at 60 sec → "결제 확인이 지연되고 있어요. 마이페이지에서 확인해주세요" + manual retry.
- Step 5: Webhook signature verification fails (security incident) → log + block entitlement + user-facing error "결제 처리 중 문제가 발생했어요. 고객센터로 문의해주세요" with linked email.

**Edge cases**:
- Subscription recurring billing failure (card expired) → Toss webhook fires `billing.failed` → graceful degrade: subscriber retains access until end of paid period + email notification + banner on `/me/billing` "결제 갱신이 실패했어요. 결제수단을 업데이트해주세요."
- User triggers payment twice rapidly (double-tap) → idempotency: client disables button on first tap; server idempotency key prevents duplicate charges.

---

### Flow E: Payment (Toss Mini-app — TossPay one-click)

**Trigger**: Same paywall surfaces but inside Toss WebView.

**Steps**:
1. Paywall shows ONLY "토스페이로 1초 결제" button (no KakaoPay).
2. User taps button → Toss JS bridge invokes native TossPay sheet.
3. User confirms with biometric or PIN in native sheet.
4. Native sheet returns success → webhook + entitlement grant (same as Flow D step 5).
5. Routes to playback.

**Error paths**:
- Step 3: User cancels native sheet → return to paywall silently.
- Step 3: Biometric fails → Toss native handles retry; on final cancel, return to paywall.
- Step 4: Webhook verification fails → same as Flow D.

**Edge cases**:
- Toss policy denies recurring billing in mini-app (R-04) → `/me/billing/subscribe` becomes single-purchase only in Toss context; subscription CTA hidden.

---

### Flow F: Quote Card Share

**Trigger**: User reaches `/reading/end` or `/tarot/end`.

**Steps**:
1. Quote card image (1080×1920) auto-generates within 3 sec (FR-018).
2. Card displays full-bleed in card preview area.
3. User sees three primary share buttons: **인스타 공유** / **카카오 공유** / **이미지 저장**.
4. User taps **인스타 공유**:
   - On iOS: native share sheet opens with image pre-loaded.
   - On Android: same native share intent.
   - User selects Instagram Stories from share sheet.
5. Image opens in Instagram Stories editor.
6. User posts, returns to our app.

**Success outcome**: User has shared a viral asset; OG meta on `/share/[cardId]` enables rich link previews when card URL is sent in KakaoTalk.

**Error paths**:
- Step 1: OG image generation fails → fallback static category-color card with hard-coded fallback quote (3 per category prepared at launch — FR-018 AC).
- Step 4: Native share sheet not available (older browser) → fallback to "이미지 저장" + "링크 복사" + textual guidance modal "이미지를 저장한 후 인스타에 직접 올려주세요."
- Step 4 (Toss WebView): Share intent blocked by WebView sandbox (A-04 dependent) → degrade gracefully to "이미지 저장" + "링크 복사" only.

**Edge cases**:
- LLM-extracted quote contains profanity → guardrail filter (FR-032) substitutes fallback quote before card render.
- User shares quote card link → recipient who clicks loads `/share/[cardId]` (a read-only marketing landing) — NOT the original reading. Page has "나도 풀이 받아보기" CTA → `/onboarding/birth-date`.
- Quote card link 90+ days old: card image retention TBD (A-07). Show fallback: "이 풀이의 명대사는 만료됐어요. 새로 풀이 받아보세요."

---

### Flow G: Signup (Web — post-trial conversion)

**Trigger**: Non-member completes free trial reading and reaches `/reading/end`; signup modal opens automatically.

**Steps**:
1. Modal slides up from bottom with title "결과 저장하려면 1초 가입" + body "지금까지 들은 풀이를 마이페이지에 저장해드려요."
2. Modal shows two buttons: **카카오로 시작하기** / **Apple로 시작하기**.
3. User taps Kakao → OAuth flow opens in same tab.
4. User authorizes in KakaoTalk → redirect to `/auth/callback?provider=kakao`.
5. Backend exchanges code → creates account → migrates non-member session data (saju info, history, quote card) to new account ID.
6. Routes back to `/reading/end` with logged-in state; modal closes; toast "가입 완료! 풀이가 저장됐어요."

**Success outcome**: Account created; saju data + this reading's history attached to account.

**Error paths**:
- Step 4: User denies authorization → return to modal with banner "가입이 취소됐어요. 다시 시도하시겠어요?"
- Step 5: Account creation fails (duplicate email edge) → backend links to existing account, returns "이미 가입된 계정으로 로그인했어요" toast.
- Step 5: Session migration fails → still log user in but show banner "히스토리 이전이 실패했어요. 마이페이지에서 확인해주세요."

**Edge cases**:
- User dismisses signup modal → still on `/reading/end`, can share quote card, but cannot navigate to `/me` (modal re-prompts on `/me` tap).
- Toss WebView context: modal shows single "토스로 계속하기" button; auto-auth via Toss ID handoff completes without OAuth redirect.

---

### Flow H: Saju Info Correction (2 free)

**Trigger**: User on `/me` taps "사주 정보 수정".

**Steps**:
1. Routes to `/me/edit-saju`. Counter banner: "무료 수정 N/2회 남음."
2. Form pre-fills current birth date, time, gender, name.
3. User edits fields, taps **저장**.
4. Confirmation modal: "수정 후엔 새 사주로 풀이가 나와요. 과거 히스토리는 그대로 남아요. 진행할까요?" (FR-029 AC).
5. User confirms → new 명식 computed → counter decremented server-side → toast "사주 정보가 수정됐어요."
6. Routes back to `/me`.

**Success outcome**: Saju data updated; future readings use new chart; history retains original chart.

**Error paths**:
- Step 1: Counter at 0/2 → form is replaced with empty state: "추가 수정은 운영 문의로 가능합니다" + 메일 버튼 (FR-029 AC).
- Step 4: User cancels modal → no change saved.
- Step 5: 명식 computation fails (manseryeok edge case) → "사주 계산에 실패했어요. 입력값을 확인해주세요" + form restored.

**Edge cases**:
- User edits to `birth_time_unknown=true` → next reading uses 3-pillar interpretation (FR-002).
- User attempts to bypass counter via direct URL → server enforces counter regardless of client state.

---

### Flow I: Subscription Cancel

**Trigger**: Subscriber on `/me/billing` taps **구독 해지**.

**Steps**:
1. Confirmation modal: "구독을 해지하시겠어요? 다음 결제일 [date]까지 모든 혜택을 그대로 이용할 수 있어요."
2. User taps **해지하기**.
3. Backend calls Toss recurring billing cancel API → status updated.
4. `/me/billing` reloads with status pill **"해지 예정 — [date]까지 이용 가능"** (FR-022 / US-12).

**Error paths**:
- Step 3: Toss cancel API fails → banner "해지 처리에 실패했어요. 잠시 후 다시 시도해주세요" + auto-retry option.

**Edge cases**:
- Subscription already in "해지 예정" state → CTA changes to "구독 재개하기" → tap reactivates within current billing period.

---

## 3. Screen List (≥ 10 core, each with 5 states)

State convention per screen: **default | loading | empty | error | success/edge**. For screens without a meaningful "empty" state (e.g., playback), "empty" is mapped to the "first-visit / never-used" variant. For screens without a meaningful "success" state (e.g., a viewer), "success" is mapped to a relevant "completed/edge" condition. This keeps all five states uniformly defined.

---

### Screen 1: Landing (`/`)

- **Route**: `/`
- **Purpose**: Convert organic / shared / Toss-discovery visitors into onboarding.
- **Components**: Hero illustration (시니컬 누님 + 노인 도사 silhouette), tagline ("매운맛 사주, 음성으로 들어봤어?"), primary CTA "지금 풀이 받기", secondary CTA "오늘의 타로 한 장", trust strip (사용자 후기 N건, 사주 N건 풀이 완료).
- **Data**: Anonymous device fingerprint to check free trial token; lightweight social proof counter (cached).
- **States**:
  - **default**: All sections render; CTA visible above fold.
  - **loading**: Hero shimmer placeholder for 200ms while character illustration loads.
  - **empty**: Same as default — landing always has content.
  - **error**: If social proof API fails, hide trust strip silently (do not block CTA).
  - **success/edge**: Returning visitor with active session → CTA copy swaps to "이어서 풀이 받기" → routes directly into `/reading/category`.
- **User actions**: Tap primary CTA → `/onboarding/birth-date`. Tap tarot CTA → `/tarot`. Tap "로그인" link in top right → `/auth/login`.

---

### Screen 2: Onboarding — Birth Date (`/onboarding/birth-date`)

- **Route**: `/onboarding/birth-date`
- **Purpose**: Collect birth date with calendar system toggle (US-01 / FR-001).
- **Components**: Step indicator "1/4", title "언제 태어났어?", solar/lunar toggle (segmented control), date picker (year/month/day spinners on mobile, single date input on desktop), "다음" primary button, "건너뛰기 없음" footer note.
- **Data**: None (no API).
- **States**:
  - **default**: Toggle defaults to 양력; date picker shows current date – 25 yrs as starting visual hint.
  - **loading**: Brief disable on form submit while validating.
  - **empty**: User has not picked a date → "다음" button disabled.
  - **error**: User picks invalid date (e.g., Feb 30, future date) → inline red text below picker "유효한 생일을 입력해주세요" + button stays disabled.
  - **success**: Valid date selected → button enabled with gentle pulse animation; on tap → routes to step 2.
- **User actions**: Toggle 양력/음력, scroll/pick date, tap 다음, tap back arrow → return to `/` with confirm modal "입력을 취소할까요?".

---

### Screen 3: Onboarding — Birth Time (`/onboarding/birth-time`)

- **Route**: `/onboarding/birth-time`
- **Purpose**: Collect birth time with "unknown" branch (US-01 / FR-002).
- **Components**: Step indicator "2/4", title "몇 시에 태어났어?", hour + minute spinners, large "시간은 모르겠어요" checkbox below spinners, hint text "시간을 모르면 큰 줄기는 보지만 디테일은 흐릿해", "다음" button.
- **States**:
  - **default**: Spinners visible, checkbox unchecked.
  - **loading**: Submit transition state.
  - **empty**: No time picked AND checkbox unchecked → button disabled.
  - **error**: N/A (no validation can fail here; spinners constrain to 00–23 / 00–59).
  - **success/edge**: Checkbox checked → spinners visually fade and disable; hint text changes to "시주 없이 풀이를 받게 돼요. 괜찮아!" → button enables.
- **User actions**: Pick hour/min, toggle "모름" checkbox, tap 다음 → `/onboarding/gender`, back arrow → `/onboarding/birth-date`.

---

### Screen 4: Onboarding — Gender (`/onboarding/gender`)

- **Route**: `/onboarding/gender`
- **Purpose**: Collect gender (FR-001).
- **Components**: Step indicator "3/4", title "성별이 어떻게 돼?", two large tappable cards "여" / "남", footer note "사주 명식 계산에만 사용돼요."
- **States**:
  - **default**: Two cards visible, neither selected.
  - **loading**: Submit transition state.
  - **empty**: No selection → can't proceed (tapping a card auto-advances; no separate "next" button).
  - **error**: N/A.
  - **success**: User taps a card → card fills with category color → auto-advances to step 4 after 200ms.
- **User actions**: Tap card → auto-advance, back arrow → `/onboarding/birth-time`.

---

### Screen 5: Onboarding — Name (`/onboarding/name`)

- **Route**: `/onboarding/name`
- **Purpose**: Optional name input (FR-001).
- **Components**: Step indicator "4/4", title "이름 알려주면 누님이 불러줄게", text input field (max 10 chars), "완료" primary button, "건너뛰기" secondary button.
- **States**:
  - **default**: Empty input, both buttons enabled.
  - **loading**: Submit state while saving to session.
  - **empty**: Input empty → "완료" button copy changes to "이름 없이 계속하기" (visually same as 건너뛰기).
  - **error**: Input > 10 chars → inline error "이름은 10자 이내로 적어줘".
  - **success**: Valid name → button copy "[이름]이로 시작하기"; on tap → `/reading/category`.
- **User actions**: Type name, tap 완료, tap 건너뛰기, back arrow → `/onboarding/gender`.

---

### Screen 6: Category Selection (`/reading/category`)

- **Route**: `/reading/category`
- **Purpose**: Select one of three reading categories (FR-004).
- **Components**: Top app bar with 누님 avatar + greeting "오늘은 뭐가 궁금해, [이름]?", three large category cards (연애 / 직장 / 금전 — each with color band, emoji, one-line teaser), bottom bar showing current entitlement status ("무료 토큰 1회" or "단건 결제 필요" or "구독 중").
- **Data**: User saju info (for greeting personalization), entitlement state.
- **States**:
  - **default**: Three cards visible, none selected.
  - **loading**: Page load shimmer for cards.
  - **empty**: First-time member with no readings yet → small toast "신규 가입 무료 토큰이 발급됐어!"
  - **error**: Entitlement check fails → cards still tappable but bottom bar shows "잠시 후 다시 시도해주세요" — paywall step handles fallback.
  - **success/edge**: Subscriber → bottom bar shows "구독 중 — 이번 달 사주 X/1회 남음".
- **User actions**: Tap category → `/reading/intro`, tap back → `/me` or `/`.

---

### Screen 7: Character Intro Player (`/reading/intro`)

- **Route**: `/reading/intro`
- **Purpose**: Play 15-sec spicy intro before paywall (FR-005).
- **Components**: Full-screen 누님 illustration center, subtitle band at bottom 30% with karaoke-style synced text, "건너뛰기" button top-right (becomes "결제하기" after 12 sec to nudge), progress bar (15 sec).
- **Data**: Category-specific pre-recorded audio URL from CDN.
- **States**:
  - **default**: Illustration + subtitle + audio playing autoplay.
  - **loading**: 200ms shimmer while audio buffers; subtitle area shows "...".
  - **empty**: Audio URL missing (content not yet produced for this category) → fallback generic intro audio + banner "이 카테고리 전용 인트로는 곧 추가돼요!"
  - **error**: Audio fails to play (autoplay blocked, network) → big "탭해서 듣기" button + subtitle fallback text rendered; on tap → play.
  - **success**: Audio completes naturally → auto-routes to `/reading/paywall`.
- **User actions**: Tap 건너뛰기 → immediate skip to `/reading/paywall`, tap subtitle area → pause/resume, back arrow → confirm modal "풀이를 중단할까요?".

---

### Screen 8: Paywall — Saju (`/reading/paywall`)

- **Route**: `/reading/paywall`
- **Purpose**: Present payment options or free token redemption (FR-006).
- **Components**: Top bar with locked-padlock illustration, title "본 풀이는 결제하고 들어봐", three option cards stacked:
  1. **무료 토큰 사용** (only if available — primary highlighted)
  2. **단건 [5,900원]** (with category badge + "꼬리질문 3개 포함" sub-copy)
  3. **구독으로 매달 풀이 + 매일 타로 [9,900원]/월** (with "단건 2회 가격으로 다 됨" sub-copy)
  Footer: legal links + refund policy link + "비회원이면 가입 먼저" prompt for non-members without trial token.
- **Data**: User entitlements (token count, subscription status), price list from server.
- **States**:
  - **default**: All applicable options shown; primary CTA highlighted.
  - **loading**: Cards rendered as skeletons while entitlement check runs.
  - **empty**: User is non-member AND has no trial token left → cards 2 and 3 require signup first → "1초 가입 후 결제" CTA replaces direct purchase.
  - **error**: Price fetch fails → show last-cached prices + small banner "최신 가격을 불러오지 못했어요. 결제 진행 시 확인해주세요."
  - **success/edge**: Subscriber lands here → auto-routes to `/reading/play` with no paywall shown (entitlement consumes monthly saju credit) + toast "구독 풀이를 시작합니다."
- **User actions**: Tap an option → triggers respective flow (free-token redemption, single-purchase Toss SDK, subscription flow). Tap legal link → opens in new view. Back arrow → confirm modal.

---

### Screen 9: Reading Player — Main Saju (`/reading/play`)

- **Route**: `/reading/play`
- **Purpose**: Stream 1–2 min saju voice with simultaneous subtitle and 명식 (FR-007, FR-008, FR-011).
- **Components**:
  - Top: 누님 character illustration (animated subtle breathing loop).
  - Middle: subtitle band — rolling 2-line caption synced to TTS chunks (NFR-015).
  - Right collapsible sidebar (or bottom drawer on mobile): 사주 명식 4-pillar table (year/month/day/hour with 천간/지지/오행). One-line summary always visible: "무자년 갑오월 경신일 — [시주 or 모름]".
  - Bottom: player controls — pause/play toggle, replay-from-start button (no scrub bar in v1 per PRD §7), elapsed/total time indicator.
  - Hidden until end: 3 follow-up question buttons placeholder.
- **Data**: Streaming audio chunks from Supertone, LLM-generated text from Claude Sonnet 4.6, computed 명식.
- **States**:
  - **default**: Audio playing, subtitle scrolling, illustration animating, 명식 visible.
  - **loading**: 0–3 sec post-payment before first audio chunk → 누님 illustration with "별기운을 모으는 중…" subtitle + breathing-dot spinner.
  - **empty**: N/A (this screen never has "no content"; if no content → error state).
  - **error**: LLM fails → "별기운이 잠시 약하네…" full-screen takeover + auto-refund/token notification (FR-033). TTS fails → subtitle-only mode banner "음성 서비스가 일시적으로 불가합니다. 텍스트로 풀이를 제공합니다" (FR-034). Network drop → "네트워크 연결이 끊겼습니다" banner, audio paused (FR-035).
  - **success/edge**: Audio reaches end → controls fade out → follow-up button area animates in.
- **User actions**: Tap pause/play, tap replay (full restart), tap any 명식 cell → tooltip showing 오행 + 십신, tap back → confirm exit modal.

---

### Screen 10: Follow-up Phase (`/reading/followup`)

- **Route**: shares `/reading/play` route (state extension) OR `/reading/followup` (if routed separately).
- **Purpose**: Present 3 LLM-generated follow-up questions and play answers (FR-009, FR-010).
- **Components**: 누님 illustration (smaller, top-left), subtitle area (centered), three follow-up buttons stacked vertically (each ≤ 30 chars), "이만 마칠게요" tertiary button at bottom, player controls (pause/replay during answer playback).
- **Data**: LLM-generated 3 question texts (Haiku 4.5); per-question answer streaming on tap.
- **States**:
  - **default**: 3 buttons enabled, no audio playing yet (waiting for tap after main reading ended).
  - **loading**: After tap, before first chunk → button shows inline spinner "답하는 중…" (≤ 2 sec target per NFR-004).
  - **empty**: LLM follow-up generation failed → 3 hardcoded fallback questions per category render instead (FR-009 AC).
  - **error**: Answer audio fails mid-playback → text fallback subtitle + banner; button remains disabled (already consumed).
  - **success/edge**: All 3 buttons tapped OR "이만 마칠게요" tapped → routes to `/reading/end`.
- **User actions**: Tap a question button (disables button + plays answer), tap "이만 마칠게요" (ends session), tap pause/play during answer, tap an enabled button while another is generating → tap ignored (FR-010 AC).

---

### Screen 11: Reading End / Quote Card (`/reading/end`)

- **Route**: `/reading/end`
- **Purpose**: Show generated quote card + share CTAs + post-session navigation (FR-018, FR-019, US-08).
- **Components**: Centered quote card preview (full visual: spicy quote line + 누님 illustration + category label + watermark + category color background), three share buttons (인스타 공유 / 카카오 공유 / 이미지 저장), secondary CTAs ("또 풀이 받기" → `/reading/category`, "마이페이지로" → `/me`), if non-member: signup modal auto-opens after 1 sec.
- **Data**: Generated card URL from server, share metadata.
- **States**:
  - **default**: Card visible, share buttons enabled.
  - **loading**: 0–3 sec while card generates → skeleton card with shimmer.
  - **empty**: First-time user → tooltip on share button "친구한테 공유해봐! 인스타 스토리에 딱이야."
  - **error**: Quote card generation fails → fallback static category-themed card with one of 3 fallback quotes loaded (FR-018 AC); share buttons still work with fallback image.
  - **success/edge**: Share completed → toast "공유했어! 친구들 반응 기대해봐." If this is the user's 2nd lifetime single-purchase → after 5 sec auto-routes to `/upsell/subscription`.
- **User actions**: Tap share button, tap save image, tap secondary CTA, swipe down to dismiss (mobile gesture).

---

### Screen 12: Daily Tarot — Face-down (`/tarot`)

- **Route**: `/tarot`
- **Purpose**: Present today's deterministic tarot card face-down (FR-012, FR-013, FR-014).
- **Components**: Top banner "이번 주 무료 N회 남음" (or 구독 중 badge), 노인 도사 illustration top-left peeking, large face-down card centered, subtitle below "오늘의 카드를 뒤집어보세요", date label "[YYYY년 MM월 DD일]".
- **Data**: Computed card index (deterministic), quota state.
- **States**:
  - **default**: Card face-down, tap-able, illustration breathing.
  - **loading**: 200ms while quota check runs → card shimmer.
  - **empty**: New user / first visit → small onboarding tip "매일 한 장씩 노인 도사가 봐주는 카드야!"
  - **error**: Quota check API fails → optimistic render face-down card; defer paywall check to tap moment.
  - **success/edge**: Quota = 0 (already used this week, not subscriber) → card shows lock overlay; tapping routes to `/tarot/paywall` instead of flipping. If already-flipped-today state exists → card shows face-up + "다시 듣기" button.
- **User actions**: Tap card → flip or paywall, tap 노인 도사 illustration → easter egg quote "기다리고 있었네…", back arrow → bottom tab.

---

### Screen 13: Tarot Player — Revealed (`/tarot/play`)

- **Route**: `/tarot/play`
- **Purpose**: Play 노인 도사 30–40 sec reading with synced subtitle (FR-015).
- **Components**: Revealed card art (top center), 노인 도사 illustration (right of card), subtitle band, simple player controls (pause/replay), card name + brief meaning label below subtitle.
- **Data**: Card index → card metadata + LLM Haiku 4.5 reading text + TTS audio stream.
- **States**:
  - **default**: Audio playing, subtitle synced.
  - **loading**: 0–2 sec post-flip → "노인 도사가 카드를 보는 중…" caption (NFR-003).
  - **empty**: N/A.
  - **error**: TTS fails → subtitle-only fallback (FR-034). LLM fails → static card-meaning text shown + banner "노인 도사의 풀이가 잠시 없어. 카드 의미만 봐."
  - **success/edge**: Audio completes → auto-routes to `/tarot/end`.
- **User actions**: Pause/play, replay, back arrow → confirm exit.

---

### Screen 14: Tarot End / Quote Card (`/tarot/end`)

- **Route**: `/tarot/end`
- **Purpose**: Share purple-variant quote card for tarot session.
- **Components**: Same as Screen 11 but: 노인 도사 illustration, card name as label, purple color variant.
- **States**: Same as Screen 11.
- **User actions**: Same as Screen 11; secondary CTA "내일 또 봐" (returns to `/`).

---

### Screen 15: Auth — Login (`/auth/login`)

- **Route**: `/auth/login`
- **Purpose**: Social login for web users (FR-016, US-13).
- **Components**: Centered logo, title "VoiceSaju에 오신 걸 환영해요", two large social login buttons "카카오로 시작하기" / "Apple로 시작하기", legal footer ("로그인 시 이용약관 및 개인정보 처리방침에 동의").
- **Data**: None (delegated to OAuth providers).
- **States**:
  - **default**: Both buttons enabled.
  - **loading**: After tap → button disabled + spinner.
  - **empty**: N/A.
  - **error**: OAuth fails / user cancels → banner "로그인이 취소됐어요" + buttons re-enabled.
  - **success/edge**: Already logged in → redirect to `/` or `redirect_uri` param.
- **User actions**: Tap a provider button, tap legal links.

---

### Screen 16: My Page — Home (`/me`)

- **Route**: `/me`
- **Purpose**: Hub for member account features (FR-026, FR-027, US-15, US-16).
- **Components**: Top section — 누님 greeting "또 왔구나, [이름]" + 사주 한 줄 요약. Stats strip — 풀이 N회 / 구독 상태 / 무료 토큰 N개. Navigation list — 내 사주 명식 / 풀이 히스토리 / 결제·구독 관리 / 사주 정보 수정 / 약관·개인정보 / 로그아웃.
- **Data**: User profile, entitlements, last-reading summary.
- **States**:
  - **default**: All sections rendered with data.
  - **loading**: Skeleton sections during initial fetch.
  - **empty**: New member with no readings → stats shows "0회"; CTA banner top "신규 가입 무료 토큰으로 첫 풀이 받아보기" → routes to `/reading/category`.
  - **error**: Profile fetch fails → "잠시 후 다시 시도해주세요" + retry button.
  - **success/edge**: Subscriber → status pill prominently shown "월 구독 중 — 다음 결제 [date]".
- **User actions**: Tap any list item → respective sub-page, tap 풀이 받기 CTA → `/reading/category`.

---

### Screen 17: My Page — Saju Chart (`/me/saju`)

- **Route**: `/me/saju`
- **Purpose**: Visualize user's 명식 (FR-011).
- **Components**: Title "내 사주 명식", 4-pillar table (year/month/day/hour, each with 천간 / 지지 / 오행 / 십신), legend explaining symbols, "정보 수정하기" link → `/me/edit-saju`.
- **States**:
  - **default**: Full chart rendered with all 4 pillars.
  - **loading**: Chart cells shimmer.
  - **empty**: User has `birth_time_unknown=true` → Hour Pillar column shows "모름" label and is visually de-emphasized.
  - **error**: 명식 fetch fails → "사주 정보를 불러올 수 없어요" + 새로고침 button.
  - **success/edge**: Tap on any cell → tooltip with 오행 explanation + relevant interpretation snippet.
- **User actions**: Tap cells for tooltips, tap 정보 수정 link, back to `/me`.

---

### Screen 18: My Page — History (`/me/history`)

- **Route**: `/me/history`
- **Purpose**: List of past saju readings for replay (FR-028, US-16).
- **Components**: Title "풀이 히스토리", list of reading rows (date / category badge / one-line summary / play icon), pagination or infinite scroll for > 20.
- **Data**: User reading history records.
- **States**:
  - **default**: List populated with reading rows.
  - **loading**: Skeleton rows.
  - **empty**: No past readings → illustration of 누님 with "아직 풀이가 없네. 첫 풀이 받아볼래?" + CTA to `/reading/category`.
  - **error**: History fetch fails → "히스토리를 불러올 수 없어요" + retry.
  - **success/edge**: An entry's audio file has expired (A-07) → row shows "재생 불가" label and is disabled.
- **User actions**: Tap row → `/me/history/[id]`, back to `/me`.

---

### Screen 19: My Page — History Player (`/me/history/[id]`)

- **Route**: `/me/history/[id]`
- **Purpose**: Stream past reading without regeneration (FR-028).
- **Components**: Same player layout as Screen 9, but with archive ribbon "[YYYY-MM-DD] 풀이", no follow-up question buttons (history of follow-ups stored as separate sub-items).
- **States**:
  - **default**: Audio streams from storage.
  - **loading**: Buffering indicator.
  - **empty**: N/A.
  - **error**: Audio file deleted/expired → "이 풀이는 더 이상 재생할 수 없습니다" message + back link (FR-028 AC).
  - **success/edge**: Reading completed → "다시 듣기" or "또 풀이 받기" CTAs.
- **User actions**: Pause/play/replay, back to `/me/history`.

---

### Screen 20: My Page — Billing (`/me/billing`)

- **Route**: `/me/billing`
- **Purpose**: Manage subscription + view single-purchase history (FR-026, US-12).
- **Components**: Subscription status card (tier / next billing date / amount OR "구독 중 아님" with CTA), "구독 해지" or "구독 시작하기" button, single-purchase history list (date / category / amount / status).
- **States**:
  - **default**: All sections rendered with payment data.
  - **loading**: Skeleton sections.
  - **empty**: No purchases and no subscription → empty state "결제 내역이 없어요" + "구독 시작하기" CTA.
  - **error**: Toss API fails → "결제 정보를 불러올 수 없어요. 잠시 후 다시 시도해주세요" + retry.
  - **success/edge**: Subscription in "해지 예정" state → status pill changes copy + "구독 재개하기" button shown.
- **User actions**: Tap 구독 시작 → `/me/billing/subscribe`, tap 구독 해지 → confirm modal then API call (Flow I), tap a history row → modal with receipt detail.

---

### Screen 21: My Page — Edit Saju (`/me/edit-saju`)

- **Route**: `/me/edit-saju`
- **Purpose**: Allow 2 free corrections to saju data (FR-029, US-17).
- **Components**: Counter banner "무료 수정 N/2회 남음", form fields (mirroring onboarding steps but flattened), 저장 button, 운영 문의 link (visible only when counter at 0/2).
- **States**:
  - **default**: Form pre-filled with current data; counter showing remaining.
  - **loading**: On 저장 tap → submit state.
  - **empty**: Counter at 0/2 → form replaced with empty-state "추가 수정은 운영 문의로 가능합니다" + 메일 button.
  - **error**: Save fails (validation, 명식 calc error) → inline errors + form preserved.
  - **success**: Save succeeds → toast "사주 정보가 수정됐어요" + routes back to `/me/saju`.
- **User actions**: Edit fields, tap 저장 (with confirm modal), tap 운영 문의 → mailto link.

---

### Screen 22: Subscription Upsell (`/upsell/subscription`)

- **Route**: `/upsell/subscription`
- **Purpose**: One-time upsell after 2nd single-purchase (FR-025, US-11).
- **Components**: 누님 illustration with sly smile, headline "또 결제하실 거잖아요?", body copy "단건 2번 가격으로 매달 사주 + 매일 타로 다 받을 수 있어요.", price comparison strip (단건 ₩5,900 × 2 = ₩11,800 vs 구독 ₩9,900/월), primary CTA "구독 시작하기", secondary CTA "다음에 할게요".
- **States**:
  - **default**: Full copy + CTAs visible.
  - **loading**: After 구독 시작 tap → routing state.
  - **empty**: N/A.
  - **error**: Pricing fetch fails → fallback static prices + small footnote "최종 가격은 결제 시 확인됩니다".
  - **success/edge**: User taps 다음에 할게요 → never shown again for this account (FR-025 AC); routes to `/me` or original destination.
- **User actions**: Tap primary → `/me/billing/subscribe` (payment flow), tap secondary → dismiss.

---

### Screen 23: Share Landing (`/share/[cardId]`)

- **Route**: `/share/[cardId]`
- **Purpose**: Public landing for shared quote card URLs; primary viral conversion surface (FR-020).
- **Components**: Full-bleed quote card image, "내 풀이도 받아보기" primary CTA, light explanation "VoiceSaju는 음성으로 듣는 매운맛 사주·타로 서비스야".
- **Data**: Card metadata fetched by ID; OG meta tags server-rendered.
- **States**:
  - **default**: Card + CTA visible.
  - **loading**: SSR delivers HTML; client-side analytics fires.
  - **empty**: N/A (always has a card or 404).
  - **error**: Card ID not found OR expired (A-07) → "이 풀이의 명대사는 만료됐어요" + CTA to onboarding.
  - **success/edge**: Crawler request (no JS) → OG meta + image returned; redirect bots get static HTML.
- **User actions**: Tap CTA → `/onboarding/birth-date`, social platforms render OG preview automatically.

---

### Screen 24: Tarot Paywall (`/tarot/paywall`)

- **Route**: `/tarot/paywall`
- **Purpose**: Convert tarot quota-exhausted free users (US-07 / FR-014).
- **Components**: Top illustration 노인 도사 hand raised, headline "이번 주 무료 타로는 다 봤어", two option cards "단건 결제 [3,900원]" and "구독으로 매일 무제한 [9,900원]", footer "다음 주 월요일에 다시 무료 1회".
- **Data**: User entitlement, prices.
- **States**:
  - **default**: Both options visible.
  - **loading**: Skeleton.
  - **empty**: N/A.
  - **error**: Price fetch fails → cached prices + warning.
  - **success/edge**: Subscriber path is impossible here (shouldn't see this screen), but defense in depth: if reached → auto-routes back to `/tarot`.
- **User actions**: Tap an option → payment flow, back arrow → `/tarot`.

---

### Screen 25: Signup Prompt Modal (overlay on multiple screens)

- **Route**: overlay (modal) — invoked on `/reading/end` for non-members and on `/me` tap by non-members.
- **Purpose**: 1-second signup conversion (FR-003 AC, US-02).
- **Components**: Bottom sheet modal, headline "결과 저장하려면 1초 가입", body "지금 들은 풀이를 마이페이지에 영구 저장해드려요.", two social login buttons (web: 카카오 + Apple; Toss WebView: 토스로 계속), "나중에 할게" tertiary link.
- **States**:
  - **default**: Modal visible, buttons enabled.
  - **loading**: After tap → OAuth redirect in progress.
  - **empty**: N/A.
  - **error**: OAuth fails → banner inside modal "로그인이 취소됐어요" + buttons re-enabled.
  - **success/edge**: Already logged in → modal auto-closes (state mismatch guard).
- **User actions**: Tap provider button, tap "나중에 할게" → modal dismisses (re-prompts on next `/me` tap).

---

### Screen 26: Error — LLM Failed (`/error/llm-failed`)

- **Route**: full-screen overlay (not URL-routed in v1; treated as state)
- **Purpose**: Graceful failure for LLM outages (FR-033, NFR-016).
- **Components**: 누님 illustration looking up at sky, big copy "별기운이 잠시 약하네…", body "환불 또는 무료 이용권이 지급되었어요", "다시 시도" + "마이페이지로" buttons.
- **States**:
  - **default**: Message + CTAs visible.
  - **loading**: After 다시 시도 tap → routing.
  - **empty**: N/A.
  - **error**: Compensation API itself fails → escalation copy "고객센터로 문의해주세요" + email button.
  - **success/edge**: After 60 sec auto-routes back to source screen.
- **User actions**: 다시 시도, 마이페이지로, 고객센터 이메일.

---

## 4. Copy Guidelines

### 4.1 Tone & Voice (per character)

**시니컬 누님** (사주 reader, default voice for all saju surfaces, paywalls touching saju, signup prompts on saju end):
- **Persona**: 28–32세 직장인 누님. 다정하지만 돌려 말하지 않는다. MZ 콜로키얼 + 약간의 시니컬한 한숨.
- **Pronouns/forms**: 반말이 기본 (해체). 예: "왔구나", "그랬구만", "괜찮아 봐줄게". 단, **결제·약관·환불·에러 메시지에는 반말+친근체 혼합**으로 안정감 확보 ("결제가 실패했어요" 같은 톤). 사용자 이름이 있으면 호명.
- **금지**: 욕설, 외모 평가, 혐오 표현, 성희롱, 차별 (FR-032 가드레일 일치).
- **샘플 마이크로카피**:
  - 인트로 시작: "어디 한번 봅시다… [생년]년생 [이름]이지? 음, 재미있네."
  - 카테고리 카드 (연애): "연애 — 그 사람 진심인지 봐줄까?"
  - 카테고리 카드 (직장): "직장 — 상사가 미운 이유 풀어줄게."
  - 카테고리 카드 (금전): "금전 — 통장 채워줄 운 있나 보자."
  - 무료 토큰 버튼: "무료로 풀이 받기 (1회만 줄게)"
  - 결제 CTA 보조 문구: "꼬리질문 3개까지 다 들을 수 있어"
  - 결제 실패: "결제가 실패했네… 카드 한 번 확인해줄래?"
  - 빈 히스토리: "아직 풀이가 없네. 첫 풀이 받아볼래?"
  - 풀이 종료 후: "이만하면 됐지? 친구한테도 자랑해봐."
  - 명식 모름 안내: "시간을 모르면 큰 줄기는 보지만 디테일은 흐릿해. 그래도 봐줄게."
  - 사주 정보 수정 카운터 0: "수정은 두 번까지 무료였어. 다음부터는 운영 문의로 부탁해."

**신비로운 노인 도사** (타로 reader, default voice for all tarot surfaces):
- **Persona**: 70대 후반 도사. 느릿하고 신비롭다. 한 박자 쉬는 말투. 격조 있지만 친근.
- **Pronouns/forms**: 반말+해체 ("왔는가", "그러하구만"), 가끔 옛스러운 표현 ("허허", "음…"). 결제·약관은 표준어 톤.
- **샘플 마이크로카피**:
  - 페이스다운 카드 안내: "오늘의 카드를 뒤집어보아라."
  - 페이스업 후 인트로: "허허, 오늘은 이 카드가 나왔구만…"
  - 빈 상태 (오늘의 카드 처음): "매일 한 장씩, 노인이 봐주는 카드일세."
  - 무료 소진: "이번 주 카드는 다 봤어. 다음 월요일에 또 오게나."
  - 카드 다시 듣기: "오늘의 카드는 이미 뒤집었네. 풀이를 다시 들어보겠는가?"
  - 종료: "내일 또 보자꾸나."

### 4.2 Tone Switching Matrix

| Surface | Voice | Form |
|---|---|---|
| 사주 카테고리, 인트로, 풀이, 꼬리질문 | 누님 | 반말 + MZ |
| 사주 종료 / 명대사 카드 | 누님 | 반말 |
| 타로 모든 surface | 노인 도사 | 반말 + 옛스러움 |
| 결제·구독·환불·법적 메시지 | 시스템 (중립) | 존댓말 |
| 에러·서비스 장애 | 캐릭터 (해당 surface 캐릭터) + 시스템 (보조) | 캐릭터는 본인 톤, 시스템은 존댓말 |
| 회원가입·로그인 | 시스템 (중립) | 존댓말 ("환영해요") |
| 마이페이지 시스템 라벨 (결제·약관 등) | 시스템 | 존댓말 |
| 마이페이지 인사 / 빈 상태 | 누님 | 반말 |

### 4.3 Button Label Patterns

- **Primary action** (결제, 시작, 받기): 동사형 짧게 — "결제하기", "지금 풀이 받기", "구독 시작하기", "공유하기"
- **Secondary action** (취소, 나중, 건너뛰기): "나중에 할게", "건너뛰기", "이만 마칠게요" (캐릭터 톤)
- **Destructive action** (해지, 삭제): 명확하게 — "구독 해지", "정말 해지하기"
- **Auth**: 제공자 + 동사 — "카카오로 시작하기", "Apple로 시작하기", "토스로 계속하기"

### 4.4 Error Message Pattern

Structure: **[캐릭터 한 줄 + 시스템 1줄 + 액션 버튼]**

Examples:
- LLM 실패: 누님: "별기운이 잠시 약하네…" / 시스템: "환불 또는 무료 이용권이 지급되었습니다." / 버튼: "다시 시도"
- 결제 실패: 누님: "결제가 안 됐네." / 시스템: "[Toss 에러 메시지: 잔액 부족]" / 버튼: "다시 결제하기"
- 네트워크 끊김: 시스템: "네트워크 연결이 끊겼습니다" / 자동: 60초 내 재연결 / 버튼 (timeout 후): "다시 시작"
- 사주 입력 오류: 시스템: "유효한 생일을 입력해주세요" (inline, 캐릭터 X)
- TTS 실패: 시스템: "음성 서비스가 일시적으로 불가합니다. 텍스트로 풀이를 제공합니다."

### 4.5 Empty State Pattern

Structure: **[캐릭터 일러스트 + 캐릭터 한 줄 + 액션 CTA]**

- 풀이 히스토리 empty: 누님 일러스트 + "아직 풀이가 없네. 첫 풀이 받아볼래?" + [지금 풀이 받기]
- 결제 내역 empty: 시스템 + "결제 내역이 없어요" + [구독 시작하기]
- 타로 무료 소진: 노인 도사 + "이번 주 카드는 다 봤어. 다음 월요일에 또 오게나." + [단건 결제하기] / [구독 시작하기]

### 4.6 Confirmation Dialog Pattern

Structure: **[제목 + 결과 안내 + 취소 + 진행]**

- 풀이 중단: "풀이를 중단할까요? 무료 토큰은 복구되지 않아요." / [취소] [중단]
- 구독 해지: "구독을 해지하시겠어요? 다음 결제일 [date]까지 모든 혜택을 그대로 이용할 수 있어요." / [취소] [해지하기]
- 사주 정보 수정: "수정 후엔 새 사주로 풀이가 나와요. 과거 히스토리는 그대로 남아요. 진행할까요?" / [취소] [수정하기]

---

## 5. Accessibility

Target: **WCAG 2.1 Level AA** across all primary flows. Voice content requires extra rigor — subtitles are not optional, they are the textual equivalent.

### 5.1 Subtitle Simultaneity (load-bearing)

- **Spec**: Korean subtitle lag ≤ 500ms behind audio at all times (NFR-015).
- **Render**: Two-line rolling caption box at bottom 25% of viewport. Min 16px (mobile) / 18px (desktop) font, 1.5 line-height, 90% white text on translucent black 70% background (≥ 7:1 contrast, beating AAA).
- **Sync**: TTS chunks emit time-coded text events; client buffers and renders 1.5 sec ahead with karaoke-style highlight on current phrase.
- **Fallback**: When TTS fails (FR-034), subtitle becomes the primary content surface — full text is shown statically (not animated), sized up by 25% for readability.
- **Pause behavior**: When user pauses, subtitle freezes at current position (no scroll-ahead).
- **Replay**: Subtitle resets to first chunk and re-syncs.

### 5.2 Focus Management

- **Onboarding steps**: Focus auto-moves to first interactive element on each step (date picker → time spinner → gender card → name input). Back navigation focuses the "back" button.
- **Modals**: Focus trapped within modal. ESC closes modal (where dismissible). First focus goes to primary action button. On close, focus returns to invoking element.
- **Player screens** (`/reading/play`, `/tarot/play`): Focus starts on play/pause button. Tab order: subtitle (announced via aria-live), play/pause, replay, 명식 cells (tabbable for tooltip access), back.
- **Follow-up phase**: After main audio ends, focus auto-moves to the first follow-up button (announces via aria-live "풀이가 끝났어요. 꼬리질문 3개가 준비됐어요.").
- **Quote card screen**: Focus moves to primary share button.

### 5.3 Keyboard Navigation (Web)

Required for NFR-013.

- **Tab order**: Logical top-to-bottom, left-to-right across each screen. Skip links: "본문으로 건너뛰기" at top of every page.
- **Enter / Space**: Activate buttons, toggles, and cards.
- **Arrow keys**: Date picker spinners (Up/Down for value, Left/Right for fields), category card selection (Left/Right between 연애/직장/금전), 명식 cells (arrow keys move tooltip focus across the grid).
- **ESC**: Close modal, exit playback (with confirm).
- **Space**: Pause/resume audio playback when player has focus.
- **R**: (Optional shortcut) Replay current audio.
- **Visible focus ring**: 2px solid focus ring color (TBD — design system) on all interactive elements; never `outline: none` without replacement.

### 5.4 Screen Reader Behavior

- **Voice content**: The TTS audio itself is auditory; for screen reader users, the subtitle text is announced via `role="log"` `aria-live="polite"` region on the subtitle band. New chunks announce; user can also navigate to a hidden "전체 풀이 텍스트 보기" toggle that exposes the full text for SR reading at user's own pace.
- **Player state**: Use `aria-label` on play/pause button (announces current state: "재생 중 — 일시정지하려면 누르세요"). `aria-pressed` on toggle.
- **Loading states**: `aria-busy="true"` on container while loading; spinner has `aria-label="로딩 중"`.
- **Errors**: Error banners use `role="alert"` to interrupt SR with the message.
- **Saju chart**: `role="table"` with proper `role="row"` / `role="cell"`. Each cell has `aria-label` with full reading: "년주 천간 무자, 오행 수, 십신 비견".
- **Tarot card**: Face-down card has `aria-label="오늘의 카드 — 탭해서 뒤집기"`. After flip: `aria-label="[카드명] — [카드 한 줄 의미]"`.
- **Quote card image**: `alt="[추출된 명대사 텍스트], 카테고리: [카테고리]"`.
- **Character illustrations**: Decorative — `aria-hidden="true"` to avoid noise; character intent communicated via copy and player labels.

### 5.5 Color & Contrast

- **Text**: Minimum 4.5:1 contrast against background (WCAG AA normal text), 3:1 for large text (≥ 18.66px / 24px bold).
- **Buttons**: Primary CTA buttons require 4.5:1 contrast on label vs button background.
- **Subtitle band**: ≥ 7:1 (exceeds AA, hits AAA) — text is the load-bearing channel.
- **Quote card backgrounds** (category color variants — FR-018):
  - 연애 pink: must verify chosen hex achieves 4.5:1 with quote text overlay (likely white text + soft shadow).
  - 직장 blue: same.
  - 금전 gold: gold + white can be tricky — use dark text or strong shadow.
  - 타로 purple: white text works at 4.5:1 with purple ≥ ~#7C3AED.
- **State indicators**: Disabled buttons not only fade color but add an icon or "비활성" label so contrast is not the only signal (WCAG 1.4.1 — color not used alone).
- **Error inline text**: Red on white must hit 4.5:1 (use #B91C1C or darker on white).

### 5.6 Motion & Animation

- **Respect `prefers-reduced-motion`**: Disable character breathing animation, card flip easing, modal slide-up, subtitle karaoke effects when user has reduced-motion preference set. Provide instant transitions instead.
- **Card flip**: 300–600ms (FR-012) — within preferred-motion-safe limits, but disable for reduced-motion users.
- **Auto-advancing content** (intro, quote card auto-route after 5 sec on upsell): Provide explicit "Skip" / "다음에" controls; never trap user in timed transitions.

### 5.7 Forms & Inputs

- **Labels**: Every input has a visible label (no placeholder-only labels).
- **Required fields**: Marked with both visual indicator (asterisk) and `aria-required="true"`.
- **Errors**: Associated to inputs via `aria-describedby` so SR reads error when input gains focus.
- **Date/time pickers**: Provide a text-input alternative as fallback for users who can't operate the spinner UI (especially for SR users).

### 5.8 Audio Player Accessibility

- **Volume control**: Use browser native (no custom volume UI in v1). System volume is the user's control.
- **No auto-play surprise**: Intro auto-plays on user navigation (user-initiated), not on cold page load — meets WCAG 1.4.2.
- **Pausable**: All audio is pausable. No content auto-restarts without user action.
- **Captions toggle**: Subtitle is always-on by default (NFR-015 mandates 100% playback). Provide explicit toggle to hide for sighted hearing users who prefer voice-only — but default ON.

### 5.9 Toss WebView Accessibility

- Inherits same WCAG requirements. Confirm Toss WebView passes through ARIA roles and keyboard events to embedded page (dependency on A-04).
- If TalkBack/VoiceOver is active inside WebView, ensure focus order is not broken by Toss native chrome.

---

## 6. Component Inventory (IA-level)

Components are described by responsibility and state contract, not pixel values. Visual spec belongs to `/uiux`.

### 6.1 Foundational

- **CategoryCard** — large tap target with color band, emoji, category name, one-liner teaser. States: default / selected / disabled / loading-skeleton.
- **OptionCard** (used in paywall) — stacked tappable rows with title, price/badge, sub-copy. States: default / primary-highlighted / disabled / loading.
- **StepIndicator** — "N/M" with optional progress bar; used in onboarding header.
- **BottomTabBar** — fixed bottom nav (사주 / 오늘의 타로 / 마이). Hidden during full-screen playback.
- **TopAppBar** — contextual back/title/action slots; hidden in Toss WebView when conflicting with Toss native chrome.
- **PrimaryButton / SecondaryButton / TertiaryLink** — three-tier action hierarchy.
- **Toast** — transient bottom notifications; auto-dismiss 3 sec; SR-announced.
- **Banner** — persistent top-of-content alerts (e.g., "이번 주 무료 1회 남음", "네트워크 연결이 끊겼습니다").
- **ConfirmModal** — title + body + cancel + destructive action. Focus-trapped.
- **BottomSheet** — slide-up modal for signup prompt, share options. Swipe-down dismiss on mobile.

### 6.2 Character & Voice

- **CharacterIllustration** — renders 누님 or 노인 도사 in defined size variants (full-screen / medium / small avatar / inline tooltip avatar). Supports breathing-loop animation (respects reduced-motion).
- **VoicePlayer** — composite component encapsulating:
  - Streaming audio element (HTMLAudioElement + MediaSource for chunked streaming)
  - Subtitle band (synced, two-line rolling, karaoke highlight)
  - Player controls (pause/play, replay, time display)
  - State management: loading / playing / paused / ended / error
  - Accessibility: aria-live subtitle log, aria-pressed toggle, keyboard shortcuts (Space, R)
  - Fallback mode: subtitle-only when TTS fails (FR-034)
- **SubtitleBand** — sub-component or standalone. Two-line rolling. Always-on default. Toggle-able via secondary control. Time-coded chunks input.

### 6.3 Saju-specific

- **SajuChart** — 4-pillar table (year/month/day/hour × 천간/지지/오행/십신). Each cell tappable for tooltip (오행 + 십신 explanation). Empty Hour Pillar with "모름" label when applicable.
- **SajuChartSummary** — one-line condensed version "무자년 갑오월 경신일 — [시주 or 모름]" for use in player header.
- **CategoryBadge** — small color-coded label (연애 pink / 직장 blue / 금전 gold) for use on cards, paywalls, history rows.
- **FollowUpButtonGroup** — vertically stacked 3 follow-up question buttons + "이만 마칠게요" tertiary. Manages disabled state per button after tap.

### 6.4 Tarot-specific

- **TarotCard** — face-down vs face-up state with flip animation. Props: card index (0–21), flipped boolean. Flip animation 300–600ms; respects reduced-motion. Face-down: stylized 노인 도사 sigil. Face-up: card art + name caption.
- **TarotQuotaBanner** — top banner showing "이번 주 무료 N회 남음" or 구독 중 badge.

### 6.5 Sharing

- **QuoteCardPreview** — renders the 1080×1920 card as a fit-to-viewport preview. Pulls server-generated image URL. Loading skeleton variant. Fallback static variant on error.
- **ShareButtonRow** — horizontal row of share CTAs (인스타 / 카카오 / 이미지 저장). Detects available channels at runtime (Toss WebView constraints).

### 6.6 Forms

- **DatePicker** — spinners (mobile) + input fallback (desktop, SR). Solar/lunar toggle integrated.
- **TimePicker** — hour + minute spinners + "모름" checkbox combo.
- **GenderToggle** — two-card single-select with auto-advance behavior.

### 6.7 Status & Feedback

- **EntitlementPill** — small status indicator: "무료 토큰 1회" / "구독 중" / "단건 결제 필요" / "구독 — 해지 예정 [date]".
- **PaymentReceiptRow** — list row in `/me/billing` history with date, category badge, amount, status.
- **HistoryReadingRow** — list row in `/me/history` with date, category badge, summary, play icon.

### 6.8 Error & Loading

- **SkeletonLoader** — generic shimmer placeholder; variants for cards, list rows, full-screen.
- **ErrorScreen** — full-screen takeover with character illustration + character one-liner + system message + action buttons. Used for LLM-failed, payment-failed.
- **InlineErrorText** — red text below inputs; ARIA-described.
- **EmptyState** — character illustration + character one-liner + CTA button. Used in history empty, billing empty.

---

## 7. Self-Review Summary

- **Screen completeness**: 26 screens defined including all secondary screens (onboarding 4 steps, paywall variants, share landing, upsell, signup modal, error screen). Modals treated as named components (Signup Prompt Modal — Screen 25). Confirmation modals are reusable component pattern, not separate screens.
- **State coverage**: Every screen has all 5 states defined per the spec, with "empty" and "success/edge" mapped pragmatically when the literal state does not apply (noted in screen sections).
- **Flow coverage**: 9 flows defined (Free Trial, Paid Reading, Daily Tarot, Web Payment, Toss Payment, Quote Share, Signup, Saju Correction, Subscription Cancel). Every flow has explicit error paths and edge cases.
- **PRD alignment cross-check**:
  - US-01 (onboarding): Flow A + Screens 2–5
  - US-02 (non-member trial): Flow A + Screen 25
  - US-03 (saju reading): Flow B + Screens 6–9
  - US-04 (follow-ups): Flow B + Screen 10
  - US-05 (saju chart visualization): Screens 9, 17
  - US-06 (daily tarot): Flow C + Screens 12, 13
  - US-07 (tarot quota): Screen 12 banner + Screen 24
  - US-08 (quote card share): Flow F + Screens 11, 14, 23
  - US-09 (web payment): Flow D + Screen 8
  - US-10 (Toss payment): Flow E + Screen 8 (Toss variant)
  - US-11 (subscription upsell): Flow B step 8 + Screen 22
  - US-12 (subscription cancel): Flow I + Screen 20
  - US-13 (web auth): Screen 15
  - US-14 (Toss auth): IA §1.3 + Screen 25 variant
  - US-15 (persistent saju data): Screen 16, 17
  - US-16 (history replay): Screens 18, 19
  - US-17 (saju correction): Flow H + Screen 21
  All 17 stories represented.
- **Confidence rating**: **High**. The PRD and requirements doc give strong constraints. Open variables (exact prices A-01, Toss WebView capabilities A-04, audio retention A-07, brand hex A-06) are flagged inline and do not block IA, flow, or state definitions. They will be resolved by `/uiux` (color hex), business contracts (Supertone, Toss), and content production (illustrations, intro recordings).

---

## 8. Flagged Assumptions Requiring Confirmation Before UI Spec

1. **Toss WebView share capability** (A-04) — current spec assumes "이미지 저장" + "링크 복사" minimum; if Instagram + KakaoTalk SDK both work, the full 3-button share row is preserved; if not, fallback degradation is defined.
2. **Toss recurring billing allowed in mini-app** (R-04) — if not allowed, hide subscription CTAs in Toss WebView (single-purchase only).
3. **Brand color hexes for quote card variants** (A-06) — UI spec must validate AA contrast on quote text overlay.
4. **Audio retention policy** (A-07) — affects `/me/history/[id]` expired state copy.
5. **Exact prices** (A-01) — all paywall copy uses bracketed placeholders `[5,900원]` until confirmed.
6. **Pre-recorded intro audio count** (DEP-07) — current empty-state copy in Screen 7 assumes some categories may launch without dedicated intros; if all 3 ship with audio, the empty state never triggers.
