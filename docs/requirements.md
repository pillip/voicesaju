# Requirements — VoiceSaju

Version: 1.0  
Source PRD: `PRD.md` (작성일 2026-05-29)  
Analyst confidence: **Medium** — pricing ranges not finalized, Toss WebView policy unconfirmed, Supertone API cost/rate limits uncontracted. See Assumptions §8 and Risks §9.

---

## 1. Goals (Specific, Measurable, Time-bound)

Derived from PRD §2.2 and §8.

| Horizon | Goal | Metric | Target |
|---------|------|--------|--------|
| Launch gate (pre-MVP) | Tone validation interview passes | Pass rate | ≥ 3/5 on all 4 criteria (PRD §10.1) |
| 3 months | User acquisition | Cumulative signups | 5,000 |
| 3 months | Revenue validation | Paid transactions | 200 |
| 3 months | Retention signal | D7 return visit rate | ≥ 30% |
| 6 months | Growth | Cumulative signups | 20,000 |
| 6 months | Monetization | Paid conversion rate | ≥ 7% |
| 6 months | Subscription | Active subscribers | 100 |
| 6 months | Engagement | DAU/MAU ratio | ≥ 0.10 |
| 12 months | Scale | Cumulative signups | 50,000 |
| 12 months | Monetization | Paid conversion rate | ≥ 8% |
| 12 months | Subscription | Active subscribers | 500 |
| 12 months | Engagement | DAU/MAU ratio | ≥ 0.15 |
| 12 months | Revenue | Annual revenue | 500M–1.5B KRW |

---

## 2. Primary User

**P1 — Hyoju, 28, office worker (main target):**  
IT/marketing professional, Seoul. Current user of Postellar/HelloBot. Pain: existing tone is traditional/stiff, HelloBot paywalls aggressively. Willing to pay 5,000–7,000 KRW per reading, up to 15,000 KRW/month subscription.

**P2 — Miju, 24, university/job seeker (viral engine):**  
Heavy Instagram saju content consumer. Pain: long input flows, wants short content. Impulsively pays 3,900–5,900 KRW. High share intent.

**P3 — Jiwon, 33, working mom (ARPU lifter):**  
Uses saju for major decisions. Pays up to 10,000 KRW per reading. Lower spicy-tone affinity; values credibility of reading.

---

## 3. User Stories

Stories are ordered Must → Should → Could within each feature area. Each story maps to one or more FRs.

### 3.1 Onboarding (Must)

**US-01** (Must — P1, P2, P3)  
As a first-time visitor, I want to enter my birth date (solar/lunar toggle), birth time (with "unknown" option), gender, and optional name in a step-by-step card flow so that I can start my saju reading with minimal friction.

Acceptance Criteria:
- Given I land on the onboarding page, when I see Step 1, then a date picker with solar/lunar toggle is displayed and both modes are selectable.
- Given I am on Step 2 (birth time), when I tap "I don't know my birth time," then the time selector is hidden and a flag `birth_time_unknown=true` is stored.
- Given `birth_time_unknown=true`, when my reading is generated, then the system excludes the Hour Pillar (시주) from the saju chart and the intro includes the canned phrase "시간을 모르면 큰 줄기는 보지만 디테일은 흐릿해."
- Given I complete all required steps, when I tap "Next" on Step 4, then I am navigated to the category selection screen.
- Given I am a non-member, when I complete onboarding, then I am NOT required to sign up before seeing the category selection screen.

Maps to: FR-001, FR-002, FR-003

---

**US-02** (Must — P2)  
As a non-member, I want to experience one complete saju reading without signing up so that I can decide whether the service is worth registering for.

Acceptance Criteria:
- Given I have never visited the site before, when I complete onboarding and select a category, then I can proceed through the intro and paywall using the "free trial token" path without creating an account.
- Given I am non-member and have used my free trial, when I try to start a second reading, then a sign-up prompt is displayed before the paywall.
- Given I complete the free trial reading, when I choose to save my result, then a "1-second sign-up" CTA is displayed with social login options.

Maps to: FR-003, FR-016, FR-017

---

### 3.2 Saju Reading Flow (Must)

**US-03** (Must — P1)  
As a signed-in user, I want to select a reading category (연애/직장/금전), hear a 15-second spicy-tone intro, pass through the paywall, and then receive a 1–2 minute voiced reading with simultaneous subtitles so that I can consume my personalized saju during a lunch break.

Acceptance Criteria:
- Given I am on the category selection screen, when I tap one of the three categories (연애, 직장, 금전), then the character intro audio begins playing within 1 second of tap.
- Given the 15-second intro has played, when the intro ends, then the paywall screen is displayed showing single-purchase and subscription options.
- Given I complete payment (or consume a free token), when the reading begins, then the first TTS audio chunk starts playing within 3 seconds of payment confirmation.
- Given the reading is playing, when the audio is active, then Korean subtitles are displayed in sync with the audio at all times.
- Given the reading is playing, when I tap "pause," then audio pauses and subtitles freeze; when I tap "play," then audio resumes from the same position.
- Given the reading is playing, when I tap "replay," then the full reading restarts from the beginning.

Maps to: FR-004, FR-005, FR-006, FR-007, FR-008

---

**US-04** (Must — P1)  
As a user who has received a reading, I want three suggested follow-up questions to appear automatically after the main reading ends so that I can go deeper without typing anything.

Acceptance Criteria:
- Given the main reading audio has finished, when the audio ends, then exactly 3 follow-up question buttons are displayed within 1 second.
- Given the 3 buttons are displayed, when I tap one, then that button is disabled and a follow-up answer audio (30–40 seconds) starts playing within 2 seconds of tap.
- Given I have tapped one follow-up, when the answer finishes, then the remaining 2 buttons remain active and tappable.
- Given all 3 follow-up questions have been used, when the last answer finishes, then all follow-up buttons are disabled and the session-end UI is shown.
- Given any follow-up button is active, when I tap "이만 마칠게요," then all follow-up buttons are disabled and the session-end UI is shown.
- Given a follow-up answer is generating, when I tap another follow-up button, then the tap is ignored (no duplicate request).

Maps to: FR-009, FR-010

---

**US-05** (Should — P3)  
As a user, I want to see my saju chart (천간·지지 table) alongside the reading so that I can understand the basis of the interpretation.

Acceptance Criteria:
- Given my saju reading screen is displayed, when the reading is playing, then the 사주 명식 (four pillars: Year/Month/Day/Hour with 천간 and 지지) is shown as a visible table or card component.
- Given `birth_time_unknown=true`, when the chart is displayed, then the Hour Pillar column is empty and labeled "모름."
- Given the chart is displayed, when I tap any pillar cell, then a tooltip shows the 오행 (five elements) classification of that character.

Maps to: FR-011

---

### 3.3 Daily Tarot (Must)

**US-06** (Must — P2)  
As a user (member or non-member), I want to flip a daily tarot card and hear a 30–40 second voiced reading from the "노인 도사" character so that I get a short moment of daily entertainment.

Acceptance Criteria:
- Given I open the daily tarot screen, when the screen loads, then a face-down tarot card is displayed.
- Given the face-down card is displayed, when I tap it, then a card-flip animation plays and the face-up card art is revealed.
- Given the card is revealed, when the flip animation ends, then the 노인 도사 voice reading starts playing automatically within 2 seconds.
- Given I have already flipped a card today (KST calendar date), when I reload the page, then the same card face is shown (deterministic result).
- Given I am a non-member, when I access the daily tarot, then usage is tracked by device ID (not user ID) for free-tier enforcement.

Maps to: FR-012, FR-013, FR-014

---

**US-07** (Must — P2)  
As a free-tier user, I want to see how many free tarot views I have left this week so that I know when I need to pay to continue.

Acceptance Criteria:
- Given I am on the daily tarot screen, when the screen loads, then a banner reading "이번 주 무료 N회 남음" is displayed at the top.
- Given my free weekly quota is exhausted (1 view used), when I tap the card, then a paywall is shown instead of the card flip.
- Given the paywall is shown, when I tap "구독하기" or "단건 결제," then I am routed to the appropriate payment flow.

Maps to: FR-014, FR-015

---

### 3.4 Quote Card / Viral Share (Must)

**US-08** (Must — P2)  
As a user who has just finished a saju reading or daily tarot, I want an automatically generated quote card to appear so that I can share it to Instagram Stories or KakaoTalk without any extra steps.

Acceptance Criteria:
- Given a saju reading or tarot session has ended, when the session-end screen appears, then a quote card image is automatically generated and displayed within 3 seconds.
- Given the quote card is displayed, when I view it, then it contains: (1) one extracted spicy quote line from the reading, (2) the character illustration, (3) the category or card name, and (4) the VoiceSaju watermark.
- Given the quote card is displayed, when I tap "인스타 공유," then the image is formatted as 1080×1920 and the Instagram share sheet opens.
- Given the quote card is displayed, when I tap "카카오 공유," then the KakaoTalk sharing dialog opens.
- Given the quote card is displayed, when I tap "이미지 저장," then the 1080×1920 image is saved to the device's camera roll.
- Given the category is 연애, when the card is generated, then the card background color is pink; 직장 → blue; 금전 → gold; 타로 → purple.
- Given the quote card URL is shared, when a social platform fetches the OG preview, then the 1080×1920 server-generated image is returned as the OG image.

Maps to: FR-018, FR-019, FR-020

---

### 3.5 Payment and Subscription (Must)

**US-09** (Must — P1)  
As a web user, I want to pay for a single saju reading using KakaoPay or TossPay so that I can complete the transaction quickly.

Acceptance Criteria:
- Given I am on the web paywall screen, when the screen loads, then both "카카오페이" and "토스페이" payment buttons are visible.
- Given I select a payment method and confirm, when the payment succeeds, then I am immediately routed to the reading screen.
- Given I select a payment method and the transaction fails, when the failure occurs, then an error message is shown and the reading does NOT start.
- Given a payment succeeds, when I view my payment history in My Page, then the transaction appears with date, amount, and category.

Maps to: FR-021, FR-022, FR-023

---

**US-10** (Must — P1)  
As a Toss mini-app user, I want to complete payment with Toss Pay one-click so that I do not need to re-enter payment details.

Acceptance Criteria:
- Given I am accessing VoiceSaju through the Toss mini-app WebView, when I reach the paywall, then only the Toss Pay payment option is presented (no KakaoPay).
- Given I tap "토스페이로 결제," when the Toss Pay SDK confirms payment, then the reading starts within 3 seconds of confirmation.

Maps to: FR-021, FR-024

---

**US-11** (Should — P1)  
As a user who has made two single-purchase payments, I want to see a subscription upsell prompt so that I can recognize that a subscription is more cost-effective.

Acceptance Criteria:
- Given a user has completed their 2nd single-purchase payment, when the post-payment screen loads, then a subscription upsell banner is displayed showing the message "매달 사주 + 매일 타로가 [구독가]원에 다 됩니다."
- Given the upsell banner is displayed, when I tap "구독 시작하기," then I am routed to the subscription checkout flow.

Maps to: FR-025

---

**US-12** (Must — P1)  
As a subscriber, I want to manage my subscription (view status, cancel) from My Page so that I remain in control of my billing.

Acceptance Criteria:
- Given I am a subscriber, when I navigate to My Page → 결제·구독 관리, then I see my current subscription tier, next billing date, and amount.
- Given I am on the subscription management screen, when I tap "구독 해지," then a confirmation dialog appears.
- Given I confirm cancellation, when cancellation completes, then I retain subscriber benefits until the end of the current billing period and my status updates to "해지 예정."

Maps to: FR-026

---

### 3.6 Authentication and Member Management (Must)

**US-13** (Must — P1)  
As a web user, I want to sign up and log in using KakaoTalk or Apple ID so that I do not need to create a new password.

Acceptance Criteria:
- Given I am on the web sign-up screen, when the screen loads, then "카카오로 시작하기" and "Apple로 시작하기" buttons are both visible.
- Given I complete KakaoTalk OAuth, when authorization succeeds, then I am redirected to the service as a signed-in user with a newly created account.
- Given I complete Apple OAuth, when authorization succeeds, then I am redirected as a signed-in user.
- Given I have an existing account linked to an OAuth provider, when I log in with the same provider, then I am logged in to my existing account (no duplicate account created).

Maps to: FR-016

---

**US-14** (Must — Toss in-app)  
As a Toss mini-app user, I want to be automatically authenticated via my Toss ID so that I do not need a separate login step.

Acceptance Criteria:
- Given I open VoiceSaju from the Toss mini-app, when the WebView loads, then authentication via Toss ID is initiated automatically.
- Given Toss ID authentication succeeds, when the service loads, then I am in a signed-in state without any manual login action.

Maps to: FR-016, FR-024

---

### 3.7 My Page (Must/Should)

**US-15** (Must — P3)  
As a signed-in user, I want my saju data to be permanently stored so that I do not have to re-enter my birth information on subsequent visits.

Acceptance Criteria:
- Given I have signed in and completed onboarding, when I return to the service on any device, then my saju information (birth date, time, gender, name) is pre-filled.
- Given I access the service from a different device using the same account, when I log in, then my saju data and reading history are available.

Maps to: FR-027

---

**US-16** (Must — P3)  
As a signed-in user, I want to replay past saju readings so that I can revisit advice I received.

Acceptance Criteria:
- Given I have at least one completed reading, when I navigate to My Page → 풀이 히스토리, then a list of past readings is displayed with date and category.
- Given I tap a past reading entry, when the reading loads, then the original TTS audio streams and plays (no regeneration).
- Given the audio streams, when the full audio has not yet loaded, then a loading indicator is shown.

Maps to: FR-028

---

**US-17** (Should — P1)  
As a signed-in user, I want to correct my saju birth information up to 2 times for free so that I can fix input errors.

Acceptance Criteria:
- Given I have made 0 or 1 prior corrections, when I navigate to My Page → 사주 정보 수정, then an edit form is available.
- Given I submit a correction, when the save succeeds, then the correction counter increments (1 of 2 used or 2 of 2 used).
- Given I have used 2 corrections, when I navigate to My Page → 사주 정보 수정, then the edit form is replaced with the message "추가 수정은 운영 문의로 가능합니다" and a contact link.
- Given a correction is saved, when I return to the reading flow, then all subsequent readings use the updated saju data.

Maps to: FR-029

---

## 4. Functional Requirements

### Feature Area A: Onboarding

**FR-001 — Step-by-step onboarding input form**  
Priority: Must | PRD ref: §5.1  
Description: A 4-step card-based onboarding collects (1) birth date with solar/lunar toggle, (2) birth time with hour+minute selectors and a "모름" checkbox, (3) gender (여/남), (4) optional name.  
Dependencies: None  
AC:
- Each step is a separate screen/card; tapping "Back" returns to the previous step without data loss.
- Step 4 (name) is skippable; if skipped, the character addresses the user without a name.
- Onboarding state is stored in session for non-members; persisted to DB for members after sign-up.

**FR-002 — Birth time unknown mode**  
Priority: Must | PRD ref: §5.1  
Description: When `birth_time_unknown=true`, the saju engine omits the Hour Pillar (시주) and the LLM system prompt is modified to exclude 시주-based interpretation. A canned phrase about reduced accuracy is included in the intro.  
Dependencies: FR-001, FR-004, FR-006  
AC:
- The saju chart displayed in the UI (FR-011) shows the Hour Pillar column as empty and labeled "모름."
- The LLM system prompt does not contain any 시주 data.
- The canned phrase "시간을 모르면 큰 줄기는 보지만 디테일은 흐릿해" appears in the intro audio or subtitle.

**FR-003 — Non-member single free trial token**  
Priority: Must | PRD ref: §5.1, §5.6  
Description: A non-member who has never used the service receives one implicit free trial token (tracked by device fingerprint/browser storage) allowing them to complete one full saju reading without payment.  
Dependencies: FR-016  
AC:
- The free trial token is consumed when the user advances past the paywall screen.
- If a second reading is attempted as a non-member (token consumed), the paywall blocks access and a sign-up CTA is shown.
- If the user signs up after consuming the free trial as a non-member, their signed-in account does NOT receive an additional free trial token (the account token is separate — see FR-017).
- Token state is stored in `localStorage` or equivalent browser storage; cleared only on explicit logout or privacy-clear.

**FR-016 — User authentication**  
Priority: Must | PRD ref: §5.6, §9.1  
Description: Authentication is provider-separated by channel. Web: KakaoTalk OAuth 2.0 and Apple Sign-In. Toss mini-app: Toss ID automatic session handoff.  
Dependencies: None  
AC:
- Web sign-in with Kakao completes the full OAuth 2.0 flow and stores a session token server-side.
- Web sign-in with Apple completes Sign In with Apple and stores a session token server-side.
- Toss mini-app authentication uses the Toss WebView bridge; no manual login screen is shown.
- Duplicate account prevention: if two OAuth providers return the same verified email, they are linked to one account (subject to Toss policy confirmation — see Assumption A-03).

**FR-017 — New member free saju token**  
Priority: Must | PRD ref: §5.5, §5.6  
Description: Upon first account creation, one free saju reading token is credited to the user's account.  
Dependencies: FR-016  
AC:
- The token is credited exactly once per account (idempotent: duplicate sign-up attempts do not grant additional tokens).
- Token is displayed in the paywall screen as "신규 가입 1회 무료 토큰 사용" option.
- Token is consumed when the user proceeds past the paywall using this option.
- Token has no expiry date (v1).

---

### Feature Area B: Saju Reading Flow

**FR-004 — Category selection screen**  
Priority: Must | PRD ref: §5.2  
Description: After onboarding, the user sees a category selection screen with three options: 연애, 직장, 금전. Exactly one category must be selected to proceed.  
Dependencies: FR-001  
AC:
- All three category buttons are displayed simultaneously.
- Exactly one category can be selected at a time (single-select behavior).
- Tapping a selected category does not deselect it (at least one must remain selected).
- The selected category is passed as a parameter to all subsequent LLM and TTS calls.

**FR-005 — Character intro (pre-paywall)**  
Priority: Must | PRD ref: §5.2  
Description: After category selection, a 15-second pre-recorded audio intro plays featuring the 시니컬 누님 character voice. This plays before the paywall appears.  
Dependencies: FR-004  
AC:
- Intro audio is served from a CDN (not generated by LLM/TTS at runtime).
- Intro audio is category-specific (3 categories × minimum 1 intro clip each; PRD §11 indicates 5–10 clips per category — this is a content production dependency, not a system requirement for launch).
- The intro plays automatically on navigation without requiring a user tap.
- A skip button is present; tapping it immediately navigates to the paywall without waiting for the intro to finish.
- After the intro finishes (or is skipped), the paywall screen is displayed.

**FR-006 — Paywall screen**  
Priority: Must | PRD ref: §5.2, §5.5  
Description: After the intro, a paywall screen shows the available purchase options: single-purchase (4,900–7,900 KRW; exact price TBD), monthly subscription (9,900–14,900 KRW; exact price TBD), or free token redemption (if available).  
Dependencies: FR-005, FR-021, FR-022  
AC:
- If the user has a free token (member: FR-017; non-member: FR-003), a "무료 토큰 사용" CTA is prominently displayed.
- Single-purchase price and subscription price are both displayed.
- Tapping a purchase option initiates the payment flow (FR-021).
- A non-member who has no free token sees a sign-up prompt alongside purchase options.

**FR-007 — Main saju reading generation and playback**  
Priority: Must | PRD ref: §5.2, §9.1, §9.3  
Description: After payment/token redemption, the system (1) calls the saju engine to compute the 명식, (2) injects the 명식 into the Claude Sonnet 4.6 system prompt, (3) streams LLM output, (4) sends chunks to Supertone TTS, and (5) streams audio to the client. Target duration: 1–2 minutes.  
Dependencies: FR-001, FR-006, FR-011  
AC:
- The saju 명식 is computed by the `manseryeok`-based engine, not by Claude.
- The LLM system prompt includes the full 명식 (천간, 지지, 오행, 십신) and the selected category.
- The first TTS audio chunk reaches the client and begins playing within 3 seconds of payment confirmation (measured from server receipt of payment webhook to client audio start event).
- Reading duration is between 60 and 120 seconds.
- Audio plays automatically without requiring a user tap.
- Subtitles are displayed in Korean in sync with audio throughout playback.
- Playback controls: pause/resume and replay-from-start are functional. Seek (scrubbing) is NOT implemented in v1.

**FR-008 — Character illustration during playback**  
Priority: Should | PRD ref: §5.2  
Description: The 시니컬 누님 character illustration is displayed on the reading playback screen alongside the subtitle and a one-line saju 명식 summary.  
Dependencies: FR-007  
AC:
- The character illustration asset is loaded before audio begins (preloaded with the paywall or intro screen).
- A one-line 명식 summary (e.g., "무자년 갑오월 경신일 [시주]") is displayed below the illustration during playback.

**FR-009 — Follow-up question buttons**  
Priority: Must | PRD ref: §5.2  
Description: Upon main reading completion, exactly 3 follow-up question buttons are automatically generated by the LLM (Claude Haiku 4.5) and displayed. Each button represents a question relevant to the selected category and user's 명식.  
Dependencies: FR-007  
AC:
- Follow-up questions are generated by Claude Haiku 4.5 and returned to the client within 2 seconds of main reading audio end.
- Exactly 3 questions are displayed; if generation fails, 3 fallback hardcoded questions are shown (one per category).
- Each question text fits within one line of the button UI (max 30 Korean characters; overflow is truncated with "…").

**FR-010 — Follow-up question answer playback**  
Priority: Must | PRD ref: §5.2  
Description: Tapping a follow-up question button triggers a Claude Haiku 4.5 call for the answer, which is then synthesized by Supertone TTS and streamed to the client. Answer duration: 30–40 seconds.  
Dependencies: FR-009  
AC:
- The first follow-up answer audio chunk begins playing within 2 seconds of button tap.
- A tapped button is immediately set to disabled state (visually distinct) and cannot be re-tapped.
- Remaining untapped buttons stay enabled during answer playback.
- Answer audio is accompanied by subtitles in sync.
- Answer duration is between 25 and 45 seconds (±5 second tolerance on LLM output variability).
- Tapping "이만 마칠게요" at any time during the follow-up phase ends the session and navigates to the session-end screen.
- After all 3 follow-up answers are consumed, the session-end screen is shown automatically.
- No additional follow-up question recommendations are shown after a follow-up answer (v1 constraint).

**FR-011 — Saju chart (명식) visualization**  
Priority: Should | PRD ref: §5.2, §5.7  
Description: The saju four-pillar chart (year/month/day/hour, 천간 and 지지 for each) is displayed visually as a table or card during reading playback and in My Page.  
Dependencies: FR-001, FR-007  
AC:
- Chart shows 4 columns (Year, Month, Day, Hour) each with 천간 (top) and 지지 (bottom).
- Hour column is empty and labeled "모름" when `birth_time_unknown=true`.
- 오행 classification is shown per character (either always visible or on tap).
- Chart is rendered before audio begins playing (not a blocking dependency on LLM output).

---

### Feature Area C: Daily Tarot

**FR-012 — Daily tarot card display and flip interaction**  
Priority: Must | PRD ref: §5.3  
Description: The daily tarot screen shows a face-down card. The user taps to reveal the card with a flip animation.  
Dependencies: FR-013  
AC:
- The card back face is shown on screen load; the card front (art) is hidden until tap.
- On tap, a CSS/animation flip transition reveals the card front.
- The flip animation duration is between 300ms and 600ms.
- Card art corresponds to the deterministically selected card (FR-013).

**FR-013 — Deterministic daily tarot card selection**  
Priority: Must | PRD ref: §5.3  
Description: The card shown for a given user (or device) on a given KST calendar date is always the same. Computed as `SHA256(date_KST + user_id_or_device_id)[:8] mod 22` selecting from 22 Major Arcana cards.  
Dependencies: None  
AC:
- Given the same `date_KST` and `user_id_or_device_id`, the algorithm always returns the same card index (deterministic, no randomness).
- Given a member user, the seed uses `user_id`; given a non-member, the seed uses `device_id` (browser fingerprint).
- The card index is an integer in range [0, 21] inclusive.
- At midnight KST, the card changes to the next day's card.

**FR-014 — Tarot free quota enforcement**  
Priority: Must | PRD ref: §5.3  
Description: Free users (member and non-member) are limited to 1 tarot view per calendar week (Monday 00:00 KST to Sunday 23:59 KST). Quota is tracked server-side for members and by device ID for non-members.  
Dependencies: FR-012, FR-013  
AC:
- A banner at the top of the tarot screen shows "이번 주 무료 N회 남음" (N = 1 if quota unused, 0 if used).
- When quota is 0 and the user taps the card, a paywall is shown (no flip animation).
- Quota resets to 1 at Monday 00:00 KST.
- Subscribers (monthly plan) have unlimited daily tarot access (no quota restriction).

**FR-015 — Tarot audio playback**  
Priority: Must | PRD ref: §5.3  
Description: After the card flip, the 노인 도사 character voice reading is generated by Claude Haiku 4.5 and synthesized by Supertone TTS, then played automatically.  
Dependencies: FR-012, FR-013  
AC:
- Audio starts playing automatically within 2 seconds of flip animation completion.
- Reading duration is between 25 and 45 seconds.
- Korean subtitles are displayed in sync with audio.
- The 노인 도사 character illustration is displayed during playback.
- No category selection is required for daily tarot (category-agnostic).

---

### Feature Area D: Quote Card (Viral Share)

**FR-018 — Automatic quote card generation**  
Priority: Must | PRD ref: §5.4  
Description: At the end of a saju reading session or daily tarot session, a quote card image (1080×1920 px) is automatically generated server-side. The quote line is extracted by the LLM from the reading content.  
Dependencies: FR-007 or FR-015  
AC:
- The quote card is generated within 3 seconds of session end (from the moment the last audio chunk ends to card image availability on client).
- The quote card contains: (1) one extracted spicy quote line ≤ 40 Korean characters, (2) character illustration (시니컬 누님 for saju, 노인 도사 for tarot), (3) category label or card name, (4) "VoiceSaju" watermark.
- Background color is category-specific: 연애=pink (#F9A8D4 or equivalent), 직장=blue (#93C5FD or equivalent), 금전=gold (#FCD34D or equivalent), 타로=purple (#C4B5FD or equivalent). (Note: exact hex values are subject to design spec — flag as Assumption A-06.)
- If quote extraction fails, a fallback generic spicy quote for the category is used (3 fallback quotes per category defined at launch).

**FR-019 — Quote card sharing**  
Priority: Must | PRD ref: §5.4  
Description: The generated quote card can be shared to Instagram Stories, KakaoTalk, or saved as an image.  
Dependencies: FR-018  
AC:
- "인스타 공유" button triggers the OS/browser native share sheet with the 1080×1920 image pre-loaded; on iOS this opens Instagram Stories if installed.
- "카카오 공유" button triggers the KakaoTalk sharing SDK with the image and service link.
- "이미지 저장" button saves the 1080×1920 PNG to the device camera roll (uses `download` attribute or native media save API).
- All three share options are available on both web and Toss mini-app WebView (subject to Toss WebView capability confirmation — see Assumption A-04).

**FR-020 — OG image for social link previews**  
Priority: Must | PRD ref: §5.4  
Description: The server generates an OG (Open Graph) meta image for quote card share URLs so that social platforms (Instagram, KakaoTalk, etc.) show the quote card as the link preview.  
Dependencies: FR-018  
AC:
- The share URL returns an HTML page with `og:image` meta tag pointing to the 1080×1920 server-generated image.
- The OG image is generated at the time the quote card is created and served from CDN (not regenerated per social platform crawl).
- `og:title` includes the category and service name; `og:description` includes a teaser line.

---

### Feature Area E: Payment and Subscription

**FR-021 — Payment flow (web)**  
Priority: Must | PRD ref: §5.5, §9.1  
Description: Web users can pay via Toss Payments SDK supporting TossPay and KakaoPay.  
Dependencies: FR-006  
AC:
- Both TossPay and KakaoPay are presented as payment options on the web paywall.
- On payment success, the Toss Payments webhook is verified server-side before the reading is unlocked.
- On payment failure, no reading access is granted and a user-facing error with a retry option is shown.
- Payment data (card numbers, etc.) is not stored on VoiceSaju servers; all payment data is managed by Toss Payments.
- A payment receipt (transaction ID, amount, date) is stored in VoiceSaju DB linked to the user account.

**FR-022 — Subscription management**  
Priority: Must | PRD ref: §5.5  
Description: Monthly subscriptions are managed via Toss Payments recurring billing. Subscriptions grant unlimited daily tarot and one saju reading per calendar month.  
Dependencies: FR-021  
AC:
- On subscription activation, user's tarot quota is set to unlimited (no weekly cap).
- Subscriber is entitled to 1 saju reading per calendar month (resets on the same day-of-month as subscription start).
- Cancellation takes effect at end of current billing period; access is maintained until then.
- Subscription status is updated via Toss Payments webhook (not client-side assertion).

**FR-023 — Automatic refund / compensation on service failure**  
Priority: Must | PRD ref: §5.5, §6.4  
Description: If the LLM or TTS service fails after payment is collected, the user automatically receives either a full refund or a free reading token.  
Dependencies: FR-021, FR-007  
AC:
- If the LLM call fails (returns error or timeout after 10 seconds) after payment is confirmed, the system initiates a Toss Payments refund within 60 seconds.
- If the refund API call fails, a free reading token is credited to the user's account as fallback.
- The user is shown a notification: "별기운이 잠시 약하네… 환불 또는 무료 이용권이 지급되었습니다."
- Failure and compensation events are logged to the monitoring system.

**FR-024 — Toss mini-app payment and auth integration**  
Priority: Must | PRD ref: §5.5, §9.4  
Description: Within the Toss mini-app WebView, authentication uses Toss ID and payment uses TossPay one-click (no KakaoPay option).  
Dependencies: FR-016, FR-021  
AC:
- Only TossPay is displayed as a payment option in the Toss mini-app context.
- The WebView context is detected at app initialization (e.g., via user-agent or Toss JS bridge).
- TossPay one-click does not require re-entry of card details (assumes pre-registered Toss payment method).
- NOTE: This requirement is contingent on Toss mini-app payment policy confirmation (Assumption A-03).

**FR-025 — Subscription upsell after second single purchase**  
Priority: Should | PRD ref: §5.5  
Description: After a user's second single-purchase payment completes, a subscription upsell screen is shown.  
Dependencies: FR-021, FR-022  
AC:
- The upsell screen appears exactly once, after the second lifetime single-purchase transaction per account.
- The screen displays the monthly subscription price and the message showing cost comparison.
- The user can dismiss the screen to proceed to their reading without subscribing.
- If the user taps "구독 시작하기," the subscription checkout flow begins.

**FR-026 — Subscription and payment history in My Page**  
Priority: Must | PRD ref: §5.7  
Description: My Page shows the user's current subscription status and full single-purchase history.  
Dependencies: FR-021, FR-022  
AC:
- If subscribed: shows tier name, next billing date, and monthly amount.
- If not subscribed: shows a "구독하기" CTA.
- Single-purchase history shows each transaction: date, category, amount, status (completed/refunded).
- "구독 해지" button is present when subscribed; tapping shows a confirmation modal before cancelling.

---

### Feature Area F: My Page

**FR-027 — Persistent saju data storage**  
Priority: Must | PRD ref: §5.6, §5.7  
Description: A signed-in user's saju data (birth date, time, gender, name) is stored persistently in the DB and synced across devices.  
Dependencies: FR-016  
AC:
- Data is available on any device after sign-in.
- Birth date and birth time are stored encrypted (AES-256 at column level — see NFR-005).
- Deleting account permanently deletes all stored saju and reading data (GDPR/privacy compliance baseline).

**FR-028 — Reading history replay**  
Priority: Must | PRD ref: §5.7  
Description: Past saju reading audios are accessible for replay from My Page. Audio is streamed from storage; it is NOT regenerated.  
Dependencies: FR-007, FR-027  
AC:
- History list shows: date, category, and a thumbnail/icon.
- Tapping a history entry streams the original TTS-generated audio file.
- If the audio file has been deleted (data retention policy TBD — see Assumption A-07), a message "이 풀이는 더 이상 재생할 수 없습니다" is shown.
- Daily tarot audio is NOT stored in listening history (v1 — only saju readings).

**FR-029 — Saju data correction (2 free)**  
Priority: Should | PRD ref: §5.7  
Description: Users may correct their saju birth data up to 2 times for free. Further corrections require contacting support.  
Dependencies: FR-027  
AC:
- Correction counter is stored server-side (not client-side) to prevent manipulation.
- After 2 corrections, the edit form is replaced with a support contact link.
- A correction creates a new 명식 computation; it does not invalidate or modify past readings in history.
- The correction counter is per account (not per device or per session).

---

### Feature Area G: Saju Engine

**FR-030 — Rule-based saju 명식 computation**  
Priority: Must | PRD ref: §9.3  
Description: The saju four-pillar chart (사주 명식) is computed by a deterministic rule-based engine using the `manseryeok` Python library (and `korean-lunar-calendar` for lunar conversion). LLM is never used for 명식 computation.  
Dependencies: None  
AC:
- Given the same birth date, time, and gender, the engine always returns the same 명식 (deterministic).
- The engine handles both solar (양력) and lunar (음력) input dates via `korean-lunar-calendar` conversion.
- The engine returns: Year/Month/Day/Hour Pillar each with 천간 (Heavenly Stem), 지지 (Earthly Branch), 오행 (Five Elements), and 십신 (Ten Gods).
- When `birth_time_unknown=true`, the engine returns 3 pillars (Year/Month/Day) and the Hour Pillar is null.
- The engine's output is validated against a test suite of ≥ 50 known correct 명식 examples before production launch.

**FR-031 — LLM prompt injection of 명식**  
Priority: Must | PRD ref: §9.3  
Description: The computed 명식 is passed to Claude Sonnet 4.6 (main reading) and Claude Haiku 4.5 (follow-up, tarot) as part of the system prompt. The LLM is instructed to interpret, not compute.  
Dependencies: FR-030  
AC:
- The system prompt explicitly instructs the LLM: "당신은 해석만 담당합니다. 명식 계산은 이미 완료되었습니다."
- The system prompt includes the full structured 명식 JSON.
- The character tone specification (시니컬 누님 / 노인 도사) is part of the system prompt.
- No LLM output that contains a 명식 claim different from the injected 명식 is permitted to reach the TTS or user (guardrail — see FR-032).

**FR-032 — LLM tone guardrail**  
Priority: Must | PRD ref: §6.5, §9.2  
Description: All LLM outputs are filtered through a real-time tone guardrail before TTS synthesis. Outputs containing prohibited content (profanity, hate speech, sexual harassment, discrimination) are blocked and replaced with a safe fallback.  
Dependencies: FR-031  
AC:
- A deny-list of Korean profanity, hate speech markers, and sexual terms is defined and applied to every LLM output chunk.
- If a chunk triggers the deny-list, it is replaced with a pre-written safe substitute phrase for that character.
- A tone evaluation set of ≥ 50 test cases (labeled acceptable/violation) is defined before launch.
- All 50+ cases pass automated regression before each production deployment.
- Tone violation events are logged with the triggering content (sanitized) for audit.

---

### Feature Area H: Error Handling

**FR-033 — LLM failure handling**  
Priority: Must | PRD ref: §6.4  
Description: If the LLM call fails (timeout or error) during a paid reading, the user sees a character-voiced fallback message and receives automatic compensation.  
Dependencies: FR-023  
AC:
- LLM calls timeout after 10 seconds with no response.
- On timeout or error, the fallback message "별기운이 잠시 약하네…" is displayed as text (TTS of fallback is attempted but not required).
- Compensation (refund or token) is triggered automatically per FR-023.

**FR-034 — TTS failure fallback**  
Priority: Must | PRD ref: §6.4  
Description: If Supertone TTS fails, the reading text (subtitle) is displayed as a text-only fallback. The user is informed that audio is unavailable.  
Dependencies: FR-007  
AC:
- TTS failure is detected when the first audio chunk is not received within 5 seconds of the TTS API call.
- On TTS failure, the full reading text is displayed in the subtitle area without audio.
- A banner informs the user: "음성 서비스가 일시적으로 불가합니다. 텍스트로 풀이를 제공합니다."
- TTS failure during a paid reading does NOT trigger an automatic refund (text fallback is provided as equivalent value).

**FR-035 — Network interruption handling**  
Priority: Must | PRD ref: §6.4  
Description: If the network drops during audio playback, the audio pauses. When connectivity is restored, playback resumes from the last successful position.  
Dependencies: FR-007  
AC:
- Network disconnection is detected within 3 seconds using browser connectivity events.
- On disconnection, audio pauses and a banner "네트워크 연결이 끊겼습니다" is displayed.
- On reconnection, the audio stream resumes from the last buffered position (not from the start).
- If reconnection takes more than 60 seconds, the session is marked as interrupted; the user is shown a "다시 시작" option that replays from the beginning.

**FR-036 — Payment failure handling**  
Priority: Must | PRD ref: §6.4  
Description: If payment fails, no reading access is granted and the user is shown an actionable error.  
Dependencies: FR-021  
AC:
- Payment failure is determined by the Toss Payments SDK callback (not a timeout on the client).
- On failure, the user remains on the paywall screen.
- An error message describes the failure reason (e.g., "잔액 부족," "카드 오류") if provided by the PG.
- A "다시 결제하기" button is shown.

---

### Feature Area I: v2 Design System (Ink, Amber & 印)

> The following FRs (FR-037..FR-044) are part of the v2 "Ink, Amber & 印" design system refinement batch. They specify visual identity, motion, copy, and shareable artefact behaviour that complement the functional flows defined in FR-001..FR-036. Source: `docs/design_philosophy.md`, `docs/design_system.md`, `docs/wireframes.md`, `docs/interactions.md`, `docs/copy_guide.md`.

**FR-037 — v2 design tokens (Ink, Amber & 印 palette + typography)**  
Priority: Must | PRD ref: design_system.md §Tokens  
Description: The frontend applies the v2 design tokens: vermilion (인주) scale `{100, 300, 500}`, hanji (한지) scale `{900, 800, 700, 500, 300}`, baekrim-200 accent, brush/mincho Korean type system (`Nanum Brush Script`, `Noto Serif KR 900`, `Cormorant Garamond`), `--grain-strong` SVG noise texture, and the `vignette-edge` body utility.  
Dependencies: None (foundation for FR-038..FR-044)  
AC:
- All token names are exposed via `tokens.css` as CSS custom properties and re-exported from a typed `tokens.ts` module.
- Google Fonts (`Nanum Brush Script`, `Noto Serif KR` weight 900, `Cormorant Garamond`) are loaded via `next/font` with `font-display: swap` and pre-connect headers.
- A `.vignette-edge` utility applied to `<body>` produces a radial-gradient overlay that visibly darkens screen corners (visual regression baseline).
- A `--grain-strong` token resolves to an inline SVG noise data URI that is reusable via `background-image: var(--grain-strong)`.
- WCAG AA contrast preserved: hanji-900 text on baekrim-200 background meets ≥ 4.5:1; vermilion-500 on hanji-800 meets ≥ 4.5:1 for normal text (NFR-012).

**FR-038 — Vermilion seal (印) component**  
Priority: Must | PRD ref: design_system.md §Components, design_philosophy.md §Visual signature  
Description: A reusable `<Seal hanja size tilt>` component renders a vermilion stamp with rotation, shadow, and grain blend. Used at the end of any "누님이 서명한" moment (reading end, follow-up answer end, quote card corner, tarot reveal).  
Dependencies: FR-037  
AC:
- `<Seal hanja="戀" />` renders a vermilion-500 background, hanja character in `--font-mincho`, default rotation `-2.5deg`.
- `tilt="right"` sets rotation `+2.5deg`; default and `tilt="left"` set `-2.5deg`.
- Sizes `sm | md | lg` correspond to fixed pixel grids: 48 / 72 / 112 px.
- Category-to-hanja default mapping is auto-applied when `category` prop is provided: `love=戀, work=業, money=財, tarot=月, reading-end=明`.
- `--grain-strong` is applied as `background-blend-mode: multiply` to give the printed ink texture.
- Component is purely presentational (no state), passes axe-core with `aria-hidden="true"` by default (decorative) and a focusable `aria-label` mode for screen-readers when used as a content signature.

**FR-039 — Hanja monument + Saju chart tile components**  
Priority: Must | PRD ref: design_system.md §Components, wireframes.md (landing, onboarding 1-3, category, reading-play, my-page)  
Description: Two reusable display components: `<HanjaMonument>` for hero-scale single-character display and `<SajuChartTile>` for the 4-pillar grid cell that combines hanja, element, and "missing" state.  
Dependencies: FR-037  
AC:
- `<HanjaMonument char="命">` renders the character at `font-size: clamp(120px, 28vw, 240px)` in `--font-mincho` color `hanji-900`.
- Character set supports at minimum `命 生 時 性 戀 業 財 月 我 門` (mapped to landing/onboarding/category screens per wireframes).
- `<SajuChartTile pillar element hanja missing>` renders in a 4-column responsive grid; `missing=true` shows the "모름" overlay with vermilion-300 stroke per FR-002.
- Both components are reused across landing, onboarding steps 1–3, category screen, reading-play, and `/me/saju` (visual consistency check across screens).
- Tiles support keyboard navigation per NFR-013 and announce element + ten-god via `aria-label` to screen-readers.

**FR-040 — Tarot 5-card spread + 3D flip sequence**  
Priority: Must | PRD ref: design_system.md §Components, interactions.md §Flow C (Tarot Reveal)  
Description: Replaces the single-card UI with a 5-card fan spread (-22°, -11°, 0°, +11°, +22°) using a 3-layer CSS transform separation. Tapping any card triggers a deterministic sequence: 4 cards discard, the tapped card centres, then flips (rotateY) to reveal. Reveal card is still the deterministic SHA256-derived card (FR-013).  
Dependencies: FR-013, FR-037  
AC:
- `.tarot-spread` parent sets `perspective: 2400px` (desktop) / `1800px` (≤ 430px) and `transform-style: preserve-3d`.
- 5 `<SpreadCard data-pos>` elements with `position: absolute; top: 50%; left: 50%; margin-top: -h/2; margin-left: -w/2` use 3 nested layers — `.spread-card` (translate), `.__pose` (rotate fan position), `.__inner` (rotateY flip). Both inner and pose use `transform-style: preserve-3d`.
- `.spread-card__back` and `.spread-card__front` must NOT set `position: relative` (faces inherit `position: absolute` from `.spread-card__face`); regression note recorded in implementation notes.
- On user tap: timing sequence runs (1) discard 4 non-tapped cards (650ms `is-moving`), (2) centre tapped card (450ms `is-centered`), (3) flip via `aria-pressed=true` (500ms `rotateY(180deg)`), (4) reveal section fade-in (`reveal-visible`).
- Reveal card identity is computed by `daily_card_index(date_KST, subject_id)` per FR-013 and is **identical** regardless of which of the 5 fan cards the user taps (deterministic guarantee).
- Mobile viewport (375 px) keeps the fan within the visible area with reduced spread angles or scale — no card overflows the viewport.

**FR-041 — Quote card v2 (9:16 export + vermilion seal corner)**  
Priority: Must | PRD ref: design_system.md §Components, wireframes.md (reading-end, tarot-end), interactions.md §Flow F  
Description: The quote card image (existing FR-018) gains v2 styling: 9:16 aspect ratio (1080×1920 export), category-specific borderline (`love=마른장미 #B7414B, work=잉크블루 #16344E, money=황동 #B68B3F, tarot=가지색 #5A3666`), auto-tilt `-1.5deg`, grain texture overlay, and a vermilion seal in the bottom-right corner mapped from the FR-038 category-to-hanja table. Server-side OG image generation uses `@vercel/og` (edge) or Pillow (worker) to produce the deterministic 1080×1920 PNG.  
Dependencies: FR-018, FR-020, FR-037, FR-038  
AC:
- Quote card component renders 1080×1920 (or visual equivalent at lower DPR) with the category borderline colour matching the spec hex.
- Card has a `-1.5deg` automatic tilt (uncanny placement) and a `var(--grain-strong)` overlay on the photo layer.
- A `<Seal>` (FR-038) is composited in the bottom-right corner with the category-default hanja and `tilt="right"`.
- Server-side render produces a pixel-identical PNG (within visual regression < 0.1% threshold) at 1080×1920 dimensions, returned via `/api/og/[slug]`.
- Share affordances (Instagram Story via `navigator.share`, Kakao SDK, PNG download) all use the same 1080×1920 asset per FR-019.

**FR-042 — Per-screen navigation variants**  
Priority: Must | PRD ref: design_system.md §Navigation, wireframes.md (landing, category, reading-play, my-page)  
Description: Navigation chrome changes per route per the v2 wireframes: landing has no nav (only brand-mark top-right + back top-left), category uses `.nav-vertical` (left vertical writing-mode for Toss-funnel entry), reading-play uses `.nav-bottom-v2` (sticky bottom for immersion), my-page uses a hanja tab bar (`家 / 命 / 月 / 我` for 홈/사주/타로/마이).  
Dependencies: FR-037  
AC:
- A `<RouteShell variant>` component selects the correct nav chrome based on `usePathname()` or an explicit prop; no nav leaks across screen boundaries.
- `.nav-vertical` uses `writing-mode: vertical-rl` and is anchored to the left edge; tap targets remain ≥ 44 px (NFR-012/013).
- `.nav-bottom-v2` is sticky to `bottom: 0` and shrinks the audio-controls primary-row visibility on small viewports; never overlaps subtitle area.
- My-page tab bar shows hanja labels with romanised aria-label (e.g., `aria-label="홈"`).
- Landing has zero nav chrome other than the brand mark and a back affordance.

**FR-043 — Copy tone system (횡설수설 누님 + signed mark)**  
Priority: Must | PRD ref: copy_guide.md §Voice & Tone  
Description: A typographic copy system that operationalises the "누님이 횡설수설" voice. Components: `<HandwrittenPrice>` and `<HandwrittenNote>` (brush script, `rotate: -1.5deg..-3deg`), `<SignedMark>` (closes any reading/follow-up with "signed, 누님" + vermilion seal), an auto `pause` element that inserts a visual line break for landing 횡설수설, and an `<em>` rule that paints a `linear-gradient(180deg, transparent 60%, rgba(155,42,26,0.22) 60%)` 마커-style highlight.  
Dependencies: FR-037, FR-038  
AC:
- `<HandwrittenPrice>` renders in `--font-brush` with `rotate(-1.5deg)` and vermilion-500 ink colour.
- `<HandwrittenNote>` accepts a `tilt` prop (`-1.5deg | -3deg`) and uses brush script.
- `<SignedMark>` renders "signed, 누님" in mincho italic and an inline `<Seal hanja="明" size="sm" />` at the end of every main reading and follow-up answer (visible on `/reading/play` and `/reading/end`).
- Any `<em>` inside an article-scoped container receives the 마커 highlight via the global `@layer copy-system` CSS.
- `<pause />` (or `<br data-pause>`) inserts a visible line break with adjusted leading so 횡설수설 reads as intentional pause, not random wrap.
- Copy strings adhere to the copy_guide.md tone matrix; reviewer can run `pnpm copy:lint` (placeholder script in implementation notes) without errors.

**FR-044 — Tilted card utilities + reveal-section fade-in pattern**  
Priority: Should | PRD ref: design_system.md §Utilities, interactions.md §Flow C, F  
Description: A small utility-class system that operationalises the "uncanny tilt" feel and a reveal-section pattern that orchestrates content fade-ins after the flip animation in FR-040 ends.  
Dependencies: FR-037, FR-040  
AC:
- `.tilted` applies `rotate(-1.5deg)`; `.tilted--right` applies `+1.5deg`; `.tilted--more` applies `-3deg`.
- `.reveal-hidden` sets `opacity: 0; visibility: hidden`; `.reveal-visible` sets `opacity: 1; visibility: visible` with a 400ms ease-out transition.
- The flip end event (FR-040 step 4) toggles `.reveal-hidden → .reveal-visible` on the reveal section root.
- Tap-hint pulse animation runs on the centred card before tap (1.6s `ease-in-out infinite`).
- Footer is hidden when `.reveal-show-hide` switches to `.reveal-hide` (no layout shift during reveal).

---

## 5. Non-functional Requirements

**NFR-001 — Reading start latency (end-to-end)**  
Priority: Must | PRD ref: §6.1  
Target: From payment webhook receipt (server) to first TTS audio chunk playing on client ≤ 3 seconds at p95.  
Measurement: Synthetic monitoring from test client; production APM traces.

**NFR-002 — TTS first chunk latency**  
Priority: Must | PRD ref: §6.1  
Target: Supertone TTS API first audio chunk response ≤ 1.5 seconds from API call at p95.  
Measurement: Server-side trace from TTS API call to first chunk received.

**NFR-003 — Tarot card flip to audio start latency**  
Priority: Must | PRD ref: §6.1  
Target: From card flip animation end to tarot audio playing on client ≤ 2 seconds at p95.  
Measurement: Client-side performance mark from animation end to `audio.play()` event.

**NFR-004 — Follow-up question answer latency**  
Priority: Must | PRD ref: §6.1  
Target: From follow-up button tap to first answer audio chunk playing ≤ 2 seconds at p95.  
Measurement: Client-side trace from tap event to audio play event.

**NFR-005 — Data encryption at rest**  
Priority: Must | PRD ref: §6.2  
Target: Birth date and birth time columns in PostgreSQL are encrypted with AES-256 at the column level. Encryption keys are stored in a separate secrets manager (not in the DB or application config files).  
Measurement: Database schema audit confirms encrypted column types; penetration test confirms plaintext is not readable from DB dump.

**NFR-006 — Payment data isolation**  
Priority: Must | PRD ref: §6.2  
Target: No raw card numbers, CVV, or full payment credentials are stored on VoiceSaju servers at any point. All such data is transmitted directly to Toss Payments.  
Measurement: Code review + network traffic audit confirms no payment credentials in application logs or DB.

**NFR-007 — LLM cost per reading**  
Priority: Must | PRD ref: §6.1, §9.5  
Target: Total LLM + TTS cost per paid reading (main reading + 3 follow-up questions) ≤ 20% of single-purchase price. At the lowest single-purchase price of 4,900 KRW, this is ≤ 980 KRW per session.  
Measurement: Cost is tracked per reading by logging API token counts and TTS character counts; averaged over 7-day rolling window.

**NFR-008 — TTS cost ratio**  
Priority: Must | PRD ref: §8.3  
Target: Total TTS API cost / total revenue ≤ 15% on a monthly basis.  
Measurement: Monthly financial report reconciling Supertone invoice against Toss Payments revenue.

**NFR-009 — Payment failure rate**  
Priority: Must | PRD ref: §8.3  
Target: Payment failure rate (failed transactions / total attempted transactions) < 2% measured weekly.  
Measurement: Toss Payments dashboard + server payment event logs.

**NFR-010 — Tone violation report rate**  
Priority: Must | PRD ref: §8.3  
Target: User-reported tone violations (inappropriate content complaints) / total sessions < 1% measured monthly.  
Measurement: In-app report button count / session count from analytics.

**NFR-011 — Reading P95 response time**  
Priority: Must | PRD ref: §8.3  
Target: Full reading pipeline (LLM generation + TTS + streaming) P95 end-to-end wall clock time < 5 seconds to first audio byte on client.  
Measurement: APM p95 trace for the reading pipeline request.

**NFR-012 — WCAG 2.1 AA color contrast**  
Priority: Must | PRD ref: §6.3  
Target: All text/background combinations throughout the service meet WCAG 2.1 Level AA minimum contrast ratio of 4.5:1 for normal text and 3:1 for large text.  
Measurement: Automated axe-core or Lighthouse accessibility scan with zero AA violations on all primary screens.

**NFR-013 — Keyboard navigation (web)**  
Priority: Must | PRD ref: §6.3  
Target: All interactive elements (buttons, links, form inputs) on the web version are reachable and operable via keyboard (Tab, Enter, Space, arrow keys). Focus indicators are visible.  
Measurement: Manual keyboard-only walkthrough of all primary user flows passes without unreachable interactive elements.

**NFR-014 — Mobile-first responsive design**  
Priority: Must | PRD ref: §6.3  
Target: All screens render correctly and are fully functional on viewport widths from 375px (iPhone SE) to 430px (iPhone 15 Pro Max) and on Toss mini-app WebView dimensions (subject to Toss WebView spec — see Assumption A-04). Tablet and desktop layouts are acceptable (not optimized) in v1.  
Measurement: Visual regression tests at 375px and 430px widths; Toss mini-app test device verification.

**NFR-015 — Subtitle display**  
Priority: Must | PRD ref: §6.3  
Target: Korean subtitles are displayed during 100% of audio playback (saju reading, follow-up answers, tarot reading). Subtitle text lag behind audio by ≤ 500ms.  
Measurement: Automated test comparing subtitle timestamp events against audio position events.

**NFR-016 — Service availability**  
Priority: Should | PRD ref: §6.4 (implied)  
Target: Service uptime ≥ 99.5% measured monthly (excluding scheduled maintenance windows announced ≥ 24 hours in advance).  
Measurement: External uptime monitoring (e.g., Uptime Robot) on the primary domain and API health endpoint.

**NFR-017 — Saju engine determinism**  
Priority: Must | PRD ref: §9.3  
Target: The saju 명식 engine returns bit-for-bit identical output for identical inputs across 100% of test cases (0 non-deterministic failures in regression suite).  
Measurement: CI test suite runs the engine 3 times for each of ≥ 50 known cases and asserts output equality.

---

## 6. Scope

### In Scope — v1

- Web app (Next.js, TypeScript, App Router) — desktop-accessible, mobile-optimized
- Toss mini-app WebView (same Next.js codebase, context-detected adaptations)
- Saju reading flow: 3 categories (연애, 직장, 금전)
- Characters: 2 fixed (시니컬 누님 for saju, 노인 도사 for tarot)
- Pre-recorded intro audio (≥ 1 clip per category at launch)
- Daily tarot: single card, 22 Major Arcana, deterministic
- Quote card: server-side OG image generation, 3 share channels
- Payment: single-purchase + monthly subscription (Toss Payments: TossPay + KakaoPay on web; TossPay only in Toss mini-app)
- Authentication: KakaoTalk + Apple Sign-In (web); Toss ID (Toss mini-app)
- Non-member free trial: 1 reading (device-tracked)
- Member free token: 1 reading on sign-up
- My Page: saju chart, reading history replay, payment/subscription management, 2 free corrections
- LLM: Claude Sonnet 4.6 (main saju reading) + Claude Haiku 4.5 (follow-up questions, tarot, quote extraction)
- TTS: Supertone API (2 character voices)
- Saju engine: `manseryeok` library + `korean-lunar-calendar`
- Tone guardrail: system prompt + real-time deny-list filter + ≥ 50-case regression test
- Automatic refund/token compensation on LLM failure
- TTS text fallback on TTS failure
- AES-256 column encryption for birth date/time

### Out of Scope — v2+

- STT (user voice input / microphone)
- Mobile native app (iOS / Android)
- Push notifications / KakaoTalk notifications
- Character selection (user chooses character)
- Additional saju categories (건강, 대인관계, 학업, 가족, etc.)
- Multi-card tarot spreads (3-card, Celtic Cross, etc.)
- Compatibility reading (궁합) / annual fortune (연간운세)
- Free-text follow-up question input (v1: 3 preset buttons only)
- Follow-up question recommendations after a follow-up answer
- Audio seek/scrubbing during playback (v1: pause + replay only)
- Tone intensity slider or character personality customization
- Scheduled maintenance alerts or push re-engagement

---

## 7. Dependencies

| ID | Dependency | Blocking FRs | Status |
|----|-----------|-------------|--------|
| DEP-01 | Supertone API contract (pricing, rate limits, voice IDs for 시니컬 누님 + 노인 도사) | FR-007, FR-010, FR-015, NFR-007, NFR-008 | Open — business contact required |
| DEP-02 | Toss mini-app policy approval (payment, auth, content, WebView capabilities) | FR-024, FR-019 (sharing in WebView) | Open — official confirmation required |
| DEP-03 | Toss Payments SDK integration (recurring billing, webhook, refund API) | FR-021, FR-022, FR-023 | Open — dev integration required |
| DEP-04 | `manseryeok` library accuracy validation (≥ 50 known correct 명식 test cases) | FR-030, NFR-017 | Open — validation required before launch |
| DEP-05 | Character illustration IP (시니컬 누님 + 노인 도사 artwork assets) | FR-008, FR-015, FR-018 | Open — production order required |
| DEP-06 | 22 Major Arcana tarot card illustrations (custom, matching 노인 도사 world) | FR-012 | Open — production order required |
| DEP-07 | Pre-recorded intro audio clips (≥ 1 per category, 시니컬 누님 voice) | FR-005 | Open — Supertone recording required |
| DEP-08 | Tone validation interview pass (≥ 3/5 on all 4 criteria, PRD §10.1) | All features (Go/No-go gate) | Open — must complete before build start |
| DEP-09 | KakaoTalk OAuth app approval | FR-016 | Open — Kakao developer registration required |
| DEP-10 | Apple Sign-In entitlement | FR-016 | Open — Apple developer account required |

---

## 8. Assumptions

**A-01** — Exact single-purchase price (4,900 / 5,900 / 7,900 KRW) and subscription price (9,900 / 14,900 KRW) are not finalized. Requirements use the ranges stated in PRD §5.5. A/B testing is planned per PRD §11. All price-referencing requirements must be updated when prices are confirmed.

**A-02** — `manseryeok` Python library on PyPI produces correct 사주 명식 output for all valid Korean birth dates within the supported range. This is unverified at requirements stage; DEP-04 must validate before launch.

**A-03** — Toss mini-app allows (a) TossPay as the sole payment method within the WebView, (b) Toss ID-based automatic authentication, and (c) the "매운맛" tone content to pass content policy review. If any of these are denied, FR-024 and potentially FR-016 require re-design. PRD §9.4 explicitly flags this.

**A-04** — The Toss mini-app WebView supports: (a) native image download to camera roll, (b) Instagram share sheet, (c) KakaoTalk SDK sharing. If any capability is restricted by the WebView sandbox, FR-019 share options must be reduced accordingly.

**A-05** — Supertone API response latency for the first audio chunk is ≤ 1.5 seconds (NFR-002) under normal load. This has not been contractually confirmed. NFR-002 is contingent on DEP-01.

**A-06** — Exact brand color hex values for quote card backgrounds (pink, blue, gold, purple) will be defined by the design spec. FR-018 references approximate values pending design system finalization.

**A-07** — TTS audio files for past readings are retained indefinitely in v1 (no automated deletion). If storage costs become prohibitive, a retention policy must be defined; FR-028 must be updated to reflect any expiry.

**A-08** — The `korean-lunar-calendar` library correctly converts lunar dates to solar dates for all dates within the supported input range (1900–2100). PRD does not specify the supported date range; assumed to be birth years 1930–2006 covering the P1–P3 personas.

**A-09** — "Device ID" for non-member tracking is implemented as a combination of browser fingerprint attributes stored in `localStorage`. This is an approximation; users who clear browser storage or use private browsing may lose their free trial state. This is accepted behavior in v1.

**A-10** — The Claude Haiku 4.5 and Claude Sonnet 4.6 models are available via Anthropic API with sufficient rate limits to serve the projected load at launch (estimated: ≤ 100 concurrent reading sessions). If rate limits are reached, a queue with user-facing wait indicator must be implemented; this is not specified in the PRD and is flagged as a gap.

---

## 9. Risks

| ID | Risk | Likelihood | Impact | Severity | Mitigation |
|----|------|-----------|--------|----------|-----------|
| R-01 | **Tone validation failure**: The "매운맛" spicy-tone voice sample fails the pre-MVP interview (fewer than 3/5 interviewees prefer it, or > 1/5 report it as offensive). This blocks the entire v1 build. | Medium | Critical | High | Conduct the 5-person tone interview immediately before committing engineering resources. Prepare a milder "중간맛" tone variant as a fallback pivot option. Pivot/Kill criteria are defined in PRD §10.1 and business_analysis §5.3. |
| R-02 | **TTS cost overrun**: Supertone API pricing (currently uncontracted) exceeds the 20% per-reading cost ceiling (NFR-007) or the 15% revenue ratio (NFR-008), making the unit economics unprofitable. | Medium | High | High | Finalize Supertone contract before writing LLM/TTS integration code. If pricing exceeds ceiling, evaluate: (a) shorter reading durations, (b) audio caching for repeated content, (c) alternative TTS provider fallback (Naver Clova Voice, ElevenLabs). |
| R-03 | **LLM tone guardrail failure**: Claude outputs content that violates Korean app store content policies (profanity, hate speech) and passes the deny-list filter, causing app store removal or reputational damage. | Low | Critical | High | (a) Build the tone regression test set (≥ 50 cases) before first deployment. (b) Implement both a deny-list AND a Claude moderation call for each output. (c) Run the regression suite in CI on every deployment. (d) Monitor tone violation report rate (NFR-010 < 1%). |
| R-04 | **Toss mini-app policy rejection**: Toss rejects VoiceSaju content (매운맛 tone), restricts payment options (no KakaoPay → expected, but no recurring billing = subscription impossible), or restricts WebView capabilities (no camera roll save). | Medium | High | High | Confirm Toss policy (DEP-02) in parallel with tone interview, before any Toss-specific code is written. If subscription is not allowed in Toss mini-app, limit Toss channel to single-purchase only. If WebView restrictions apply, reduce share feature scope in Toss channel. |
| R-05 | **Retention loop weakness**: DAU/MAU fails to reach 0.10 at 6 months because weekly-free tarot (1/week) provides insufficient daily return incentive. Subscription conversion rate stays below 7%. | Medium | High | High | (a) Monitor DAU/MAU weekly from launch. (b) If D7 return rate < 20% at month 2, test increasing free tarot quota to 2/week. (c) Prioritize v2 push notifications as the next retention lever. (d) Analyze daily tarot drop-off vs. saju reading drop-off to isolate cause. |

---

## 10. Success Metrics

### 10.1 Primary KPIs

| Metric | 3-Month Target | 6-Month Target | 12-Month Target |
|--------|---------------|---------------|----------------|
| Cumulative signups | 5,000 | 20,000 | 50,000 |
| Paid transactions | 200 | — | — |
| Paid conversion rate (paid users / signups) | — | ≥ 7% | ≥ 8% |
| Active subscribers | — | 100 | 500 |
| DAU/MAU | — | ≥ 0.10 | ≥ 0.15 |
| Annual revenue run-rate | — | — | 500M–1.5B KRW |

### 10.2 Secondary Metrics (Monitored Quarterly)

| Metric | Target |
|--------|--------|
| Activation rate (first reading completion / signup) | ≥ 70% |
| D7 return visit rate | ≥ 30% |
| D30 return visit rate | ≥ 15% |
| Quote card share rate (shares / completed sessions) | ≥ 5% |
| NPS score | ≥ 8.0 |
| Intro → payment conversion rate | ≥ 15% |
| Average order value (single-purchase) | ≈ 5,500 KRW |

### 10.3 Guardrail Metrics (Alert if Exceeded)

| Metric | Alert Threshold |
|--------|----------------|
| Tone violation complaint rate | > 1% of sessions |
| Payment failure rate | > 2% of attempts |
| Reading P95 latency (first audio byte) | > 5 seconds |
| TTS cost / revenue | > 15% monthly |
| LLM + TTS cost per session | > 20% of single-purchase price |
