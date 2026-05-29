# Interactions — VoiceSaju · Ink & Amber

> 모든 인터랙션은 design philosophy("기다림이 신비")와 design_system.md motion tokens를 기반.
> 모션의 미덕은 *과시*가 아니라 *침묵의 무게*.

---

## Motion Philosophy

| 원칙 | 의미 |
|------|------|
| **절제** | 100ms 이상은 의도가 있어야 함. 600ms 이상은 *기다림*을 위해서만. |
| **방향성** | 자막은 위에서 아래로, 카드는 호박색 향해, 페이지 전환은 좌에서 우로(이전), 우에서 좌로(다음). |
| **GPU only** | `transform` + `opacity` 만 트랜지션. `box-shadow`, `width`, `height` X. |
| **Reduced motion respect** | `prefers-reduced-motion: reduce` 시 모든 모션 ≤ 100ms로 자동 단축. |
| **Shared Element Transitions: 없음** | Aesop 절제와 충돌. 페이지 간 hero 객체 morphing 안 함. (rationale 아래) |

### Shared Element Transitions — None Planned

iOS/Material에서 흔한 카드 morphing(thumbnail → detail) 패턴은 **사용하지 않습니다**. 이유:
- "Ink & Amber"의 핵심은 *침묵과 분리* — 페이지가 변하는 순간 시각적 연속성을 강조하면 *기다림의 무게*가 깨짐.
- Aesop 사이트도 페이지 전환 시 fade 외 motion 없음.
- 대안으로 카테고리 → reading intro 진입 시 amber dot이 페이지 상단 동일 위치에 정적으로 등장 (이는 SET 아님, 단순 컴포넌트 재배치).

### Drag & Drop — N/A

PRD에 reordering/dragging 기능 없음 (히스토리 리스트, 마이페이지 모두 정적 순서). v1 + v2 범위 통틀어 drag & drop 없음.

---

## High-impact Motion Moments

이 5개 모먼트는 "Ink & Amber"의 *기억할 한 가지*를 만드는 핵심:

1. **Landing 헤드라인 등장** — 페이지 로드 후 "흠." 한 단어가 amber-300으로 1초 만에 fade-up.
2. **자막 한 문장 stream** — TTS 청크에 맞춰 한 문장씩 amber-300으로 fade-up, 이전 문장은 cream-300으로 흐려짐.
3. **타로 카드 뒤집기** — 600ms `ease-deliberate` 회전 + 회전 중간 50%에서 amber dot 한 번 깜빡.
4. **명대사 카드 quote reveal** — 카드 등장 후 **5초 정지**, 그 다음 한 줄 fade-up (1000ms `ease-deliberate`).
5. **결제 완료 후 reading/play 진입** — 결제 시트 fade-out → 0.4초 blank ink-900 → 캐릭터 silhouette fade-in (음성 첫 청크 시작).

---

## Page Transition Map

전체 페이지 전환은 **단 3가지 패턴**만 사용:

| 패턴 | Duration | Easing | When |
|------|----------|--------|------|
| **Fade** | 400ms | `--ease-out` | 같은 도메인 내 next screen (onboarding step) |
| **Slide-up** | 400ms | `--ease-out` | bottom sheet, modal open |
| **Cross-fade** | 600ms | `--ease-deliberate` | reading/intro → reading/play, tarot flip → reading |

> Hero zoom, parallax, scroll-linked animation 모두 사용 안 함.

---

## Flow A — Non-Member Free Trial (랜딩 → 첫 풀이)

**Goal**: 비회원이 가입 없이 첫 사주 풀이 1회 체험.

### Preconditions
- 신규 디바이스 (디바이스 쿠키 없음)
- 첫 무료 토큰 1개 자동 발급됨

### States & Transitions

```
[Landing] ─tap CTA─▶ [Onboarding/birth]
   │
   └─tap 타로 link─▶ [Tarot] (Flow C로 분기)

[Onboarding/birth] ─valid + next─▶ [Onboarding/time]
   │ ─invalid date─▶ [Onboarding/birth · error state]
   │ ─back─▶ [Landing]

[Onboarding/time] ─valid OR 시간모름─▶ [Onboarding/gender]
   │ ─back─▶ [Onboarding/birth]

[Onboarding/gender] ─select─▶ [Onboarding/name] OR [Category]
   │ (skip name optional)

[Onboarding/name] ─valid OR skip─▶ [Category]

[Category] ─select─▶ [Reading/intro]
   │ ─타로 link─▶ [Tarot]

[Reading/intro] ─intro ends─▶ [Paywall CTA active]
   │ ─tap "본격 풀이 받기"─▶ [Free Token Spend Confirm modal]
   │   ─confirm─▶ [Reading/play]  (no payment, token consumed)
   │   ─cancel─▶ [Reading/intro]

[Reading/play] ─reading ends─▶ [Reading/followup]
[Reading/followup] ─3 used OR "이만"─▶ [Reading/end]
[Reading/end] ─5s 후 quote reveal─▶ [Share CTA active]
   │ ─tap "처음으로"─▶ [Landing]
   │ ─tap 공유─▶ Flow F
   │ ─저장 hint─▶ "*가입하면 영구 저장.*" CTA
```

### Error Paths
- **온보딩 중 새로고침**: 입력값 sessionStorage 자동 저장 → 복귀 시 동일 step.
- **결제 전 free token 확인 실패** (서버 통신): 토스트 "*잠시 별기운이 약하네.*" + retry.
- **Reading 도중 네트워크 끊김**: 음성 일시정지 + "*재연결되면 이어서.*" 토스트. 재연결 시 audio resume + sub stream catch-up.
- **LLM 실패**: free token 차감 안 함 + "*다시 시도하자.*" + auto-refund (token re-credit).

### Motion Moments
- Onboarding 진행: `stepper-dot--active` color change 200ms.
- Category select tap: `chip` border-left 2px → 3px transition 200ms.
- Reading/intro → /play: cross-fade 600ms, 인트로 마지막 0.5초 + 본 풀이 첫 0.5초 오버랩.

### Edge Cases
- **24시간 안에 onboarding 미완료**: sessionStorage 만료 → Landing으로.
- **시각 모름 + 24시간 모르는 사용자**: 시주 자리에 "?" placeholder, 풀이 톤은 "시간 모르는 김에 큰 줄기만 보자."로 자동 조정.
- **Brave/Firefox private mode**: 디바이스 쿠키 차단 시 안내 "*시크릿 모드에선 결과 저장이 안 돼.*"

---

## Flow B — Logged-in Paid Saju Reading

**Goal**: 가입 회원이 카테고리 선택 → 결제 → 풀이 + 꼬리질문 3개.

### Preconditions
- 회원 로그인 상태
- 사주 정보 입력 완료
- 무료 토큰 소진 OR 추가 풀이 원함

### States

```
[Home/Me] ─tap "사주 풀러"─▶ [Category]
[Category] ─select─▶ [Reading/intro]
[Reading/intro] ─tap CTA─▶ [Payment sheet]
   │ ─구독자─▶ skip payment, [Reading/play] 바로
[Payment sheet] ─토스페이 OR 카카오페이─▶ [Payment Processing]
   │ ─cancel─▶ [Reading/intro]
[Payment Processing] ─success─▶ [Reading/play]
   │ ─fail─▶ [Payment sheet · error state]
[Reading/play] ─이하 Flow A와 동일─▶ [Reading/end]
```

### Form Validation (Payment)
- 토스/카카오 SDK가 처리. 클라이언트 자체 카드 입력 X.
- **Idempotency**: 동일 결제 시도 5초 이내 차단 (debounce 5000ms).

### Motion Moments
- Payment sheet open: slide-up 400ms.
- 결제 성공 → reading/play: cross-fade 600ms.

### Error Paths
- **결제 timeout (30s)**: "*결제 응답이 늦네. 다시 시도해줘.*"
- **카드 거절**: "*카드사에서 막혔어. 다른 카드로 해볼까?*"
- **결제 후 LLM 실패**: 자동 환불 + "*풀이는 다음에. 환불 처리됐어.*" + 토스트 5초 노출.

---

## Flow C — Daily Tarot

**Goal**: 매일 1장 → 결정적 카드 → 30~40초 음성 풀이.

### Preconditions
- (회원/비회원 무관) 디바이스/유저별 today's deterministic card 산출 가능
- 이번 주 무료 quota 잔여 1회 이상 OR 구독자

### States

```
[Tarot · card back] ─tap card─▶ [Tarot · flipping]
[Tarot · flipping] ─600ms 회전 + quota 차감 트랜잭션─▶ [Tarot · card front]
[Tarot · card front] ─0.5s 후 음성 자동 재생─▶ [Tarot · playing]
[Tarot · playing] ─재생 완료─▶ [Tarot · end (share CTA)]
   │ ─tap 공유─▶ Flow F
```

### Error Paths
- **Quota 소진**: 카드 회색 잠금 + lock icon, "*이번 주는 다 봤어. 구독 OR 다음 주.*"
- **결정적 시드 실패** (서버): client-side fallback 시드 생성 + 백엔드 reconcile.
- **TTS 실패**: 자막만 노출, 캐릭터 silhouette 정적.

### Motion Moments
- **Card flip**: 600ms `ease-deliberate` rotateY(180deg). 중간 50%에 amber dot 한 번 깜빡 (subtle, 100ms opacity 1→0).
- **Quota banner exhausted state 진입**: border-bottom color amber → error 400ms transition.

### Edge Cases
- **자정 KST 직후**: 새 카드 자동 노출 + "*새 날, 새 카드.*" caption 5초 표시 후 사라짐.
- **시간대 mismatch** (해외): server 명시적 KST 기준으로 fix.
- **동일 카드 7일 연속**: 결정적이라 가능. 무한 반복 없도록 일주일에 1번씩 hash salt 회전 (architecture §11 추가 검토).

---

## Flow D — Web Payment (Toss + Kakao)

**Goal**: 웹 채널에서 단건/구독 결제.

### States

```
[Reading/intro · CTA] ─tap─▶ [Payment sheet (Web)]
[Payment sheet (Web)]
   │  옵션 노출:
   │   ① 토스페이로 결제 (btn-primary)
   │   ② 카카오페이로 결제 (btn-secondary)
   │   ③ 가입 후 1회 무료 (ghost link)
   │
   ─tap 토스페이─▶ [Toss SDK overlay]
   ─tap 카카오─▶ [Kakao SDK overlay]
   ─tap 가입─▶ [Auth/login]

[Toss/Kakao SDK overlay] ─success─▶ [Webhook confirm wait (≤2s)] ─▶ [Reading/play]
   │ ─cancel─▶ [Payment sheet]
   │ ─fail─▶ [Payment sheet · error]
```

### Idempotency
- **Order ID**: client UUID 생성, 동일 ID 재요청 시 서버에서 멱등 처리.
- **Webhook**: 결제 confirm은 webhook으로 server-side, client에는 polling으로 결과 안내.

### Form Validation
- 결제 SDK 자체 validation에 위임. 자체 카드/PIN 입력 form 없음.

### Error Paths
- **SDK 로드 실패**: "*결제창이 안 열리네. 새로고침해줘.*"
- **Webhook timeout 5s**: client polling 시작, 10s 이상 → "*결제 확인 중이야. 잠시만.*" loading state.
- **Webhook 미수신 30s**: "*결제 처리에 시간이 걸리네. 마이페이지에서 확인할게.*" + redirect to /me.

---

## Flow E — Toss WebView Payment

**Goal**: 토스 인앱(WebView) 환경에서 토스페이 단일 결제 + Toss ID 인증.

### Preconditions
- Toss WebView UA 감지 (server-side User-Agent 검사 + client `window.toss` global)
- Toss ID handoff 토큰 받음

### States

```
[Reading/intro (WebView)] ─CTA tap─▶ [Payment sheet (WebView variant)]
[Payment sheet (WebView)]
   │  옵션 노출:
   │   ① 토스페이로 결제 (단일 노출, 카카오/애플 hidden)
   │
   ─tap 토스페이─▶ [Toss native bridge (postMessage)]

[Toss native bridge] ─toss 결제창 native open─▶ [User confirm in Toss]
   │ ─success postMessage─▶ [Webhook confirm] ─▶ [Reading/play]
   │ ─cancel postMessage─▶ [Payment sheet]
```

### Special Cases
- **WebView 인증 토큰 만료**: 5분 정도 idle 후 결제 시도 시 "*인증이 풀렸어. 토스에서 다시 진입해줘.*" + back action.
- **WebView 브릿지 미동작** (구버전 토스): graceful degrade — "*토스 앱을 최신 버전으로 업데이트해줘.*"
- **이미지 공유 제약**: WebView가 navigator.share API 미지원 시 §11 Flow F의 인스타 직접 호출 대신 "URL 복사" fallback.

### Motion Moments
- Toss native overlay 진입 시 webview content는 dim (opacity 0.4, 400ms).

---

## Flow F — Quote Card Share

**Goal**: 명대사 카드 → 인스타/카톡/저장.

### Preconditions
- Reading/end 또는 Tarot/end 도달
- Quote card OG 이미지 생성 완료 (서버 background job)

### States

```
[Reading/end · 5s 정지 후 quote reveal] ─share row 활성─▶ [Share CTA enabled]
[Share CTA]
   ─tap "인스타 스토리"─▶ [navigator.share API call]
   ─tap "카톡"─▶ [Kakao SDK share]
   ─tap "저장"─▶ [Client canvas → PNG download]
```

### Behavior
- **navigator.share (모바일 웹/Toss WebView)**: `text: amber line + URL`, `files: [PNG blob]`.
- **카톡 공유**: Kakao SDK `sendDefault` with template (대표 이미지 = OG URL, 텍스트 = amber line).
- **저장**: client canvas 1080×1920 → PNG → `<a download>` trigger.

### Error Paths
- **OG 생성 실패**: 클라이언트 canvas로 fallback + "*공유 미리보기가 안 보일 수 있어.*" 안내.
- **navigator.share 미지원** (구 브라우저): "URL 복사" 자동 fallback + 토스트 "*링크 복사됨.*"
- **카톡 SDK 로드 실패**: "*카톡 공유 안 되네. 링크 복사할게.*"

### Motion Moments
- Quote reveal: 5s 정지 후 1000ms `ease-deliberate` fade-up — *기다림의 무게*.
- 공유 버튼 hover: border amber 200ms.

---

## Flow G — Signup (소셜)

**Goal**: 카카오/애플 1초 가입 — 비회원 reading 후 데이터 저장 유도.

### Triggers
- Reading/end 의 "*가입하면 영구 저장*" CTA
- Tarot/end 의 동일 CTA
- 사주 두 번째 풀이 시 "*가입하고 가야 해*" modal

### States

```
[Auth/login]
   ─tap 카카오─▶ [Kakao OAuth redirect]
   ─tap Apple─▶ [Apple OAuth redirect]
   ─tap "이미 가입한 적 있어"─▶ same buttons (서버 idempotent — 자동 로그인)

[OAuth redirect] ─success callback─▶ [Account merge: device → user]
   │ ─existing user─▶ [Redirect to original intent OR /me]
   │ ─new user─▶ [Show "사주는 저장됐어 ✓" toast] ─▶ [Original intent OR /me]
   ─fail─▶ [Auth/login · error]
```

### Account Merge Logic
- 비회원으로 만든 사주/풀이/타로 결과는 디바이스 ID에 묶임.
- 가입 시 디바이스 ID → user ID로 ownership 이전.
- 한 디바이스에 여러 비회원 세션이 있었다면 가장 최근 30일 데이터만 merge.

### Error Paths
- **카카오 OAuth 거절**: "*카카오 로그인이 안 됐어.*" + retry.
- **email scope 거절**: 이메일 없이도 가입 허용 (kakao_id PK).
- **중복 가입 시도** (같은 카카오 ID): 자동 로그인 처리.

### Motion Moments
- OAuth redirect 동안 full-screen spinner + "*잠시만, 가입 중.*"
- Merge 완료 후 redirect: 작은 amber dot 한 번 깜빡 (success indicator).

---

## Flow H — Saju Correction (생일 수정)

**Goal**: 잘못 입력한 사주 정보 2회 무료 수정.

### Preconditions
- 가입 회원
- 수정 횟수 잔여 ≥ 1

### States

```
[Me] ─tap "생일 수정 (2회 남음)"─▶ [Edit-saju · confirm modal]
[Confirm modal]
   본문: "*사주 정보를 바꾸면 기존 풀이는 그대로 남아. 새 풀이부터 새 명식으로 봐.*"
   ─tap 확인─▶ [Edit-saju · 생년월일]
   ─tap 취소─▶ [Me]

[Edit-saju · 생년월일] ─onboarding 흐름 재사용─▶ [Edit-saju · 시각] ─▶ [Edit-saju · 성별] ─▶ [Edit-saju · 이름]
[Edit-saju · 이름] ─저장─▶ [Saju recomputed] ─▶ [Me]
   ─토스트: "*새 명식 저장됐어. 남은 수정 1회.*"
```

### Edge Cases
- **마지막 1회 수정 직전**: "*이번이 마지막이야. 신중하게.*" 강조 안내.
- **0회 남은 상태**: "생일 수정" 자체가 disabled + "*운영팀에 문의*" link.
- **수정 중 abort**: 변경값 미적용, 기존 명식 유지.

### Motion Moments
- "*남은 수정 N회*" caption color: amber → muted cream → error 단계별로 변화.

---

## Flow I — Subscription Cancel

**Goal**: 구독 해지 — 마찰을 두되 강요 없이.

### States

```
[Me] ─tap "구독 관리"─▶ [Billing]
[Billing]
   섹션: 현재 구독 상태 + 다음 결제일 + 해지 버튼
   ─tap "구독 해지"─▶ [Cancel confirm modal]

[Cancel confirm modal]
   본문: "*해지하면 이번 결제 주기 끝까지는 쓸 수 있어. 다음 결제 안 됨.*"
   양보 카피: "*매운맛이 너무 셌어? 한번만 다시 생각해줄래?*"
   ─tap "유지할게"─▶ [Billing]
   ─tap "해지하기"─▶ [Cancel processing] ─▶ [Billing · canceled state]
       │ 토스트: "*해지됐어. {next_billing_date}까지는 그대로 써.*"
```

### Behavior
- 즉시 해지 안 함 — 결제 주기 끝까지 access 유지 (현금 환불 없음).
- 해지 후 재가입 가능 (블록 X).

### Error Paths
- **해지 API 실패**: "*해지가 안 됐어. 잠시 후 다시.*" + retry.
- **이미 해지된 구독**: "*이미 해지됐어.*" 안내 + canceled state 노출.

### Motion Moments
- 해지 확인 modal slide-up 400ms.
- 해지 완료 후 billing state 색상 변화: amber → muted cream 400ms.

---

## Loading / Empty / Error Patterns (Cross-cutting)

### Loading

| 상황 | UX |
|------|----|
| **TTS first chunk wait** (≤1.5s) | 캐릭터 silhouette + 좌측 상단 작은 spinner |
| **LLM 첫 응답 wait** (≤3s) | 자막 영역에 "..." pulse + spinner |
| **결제 processing** | 결제 버튼 자체에 `aria-busy=true` spinner |
| **OG image generation** | quote card 자리에 skeleton 0.5s |
| **OAuth redirect** | full-screen spinner + caption "*잠시만.*" |

### Empty

| 상황 | UX |
|------|----|
| **히스토리 없음** | "*아직 풀이가 없어.*" + CTA "첫 풀이 받으러" |
| **사주 정보 없음** | "*먼저 사주 입력해줘.*" + CTA "/onboarding/birth" |
| **무료 quota 소진** | 카드 회색 + 잠금 + 구독 CTA |

### Error (모든 화면 공통 톤)

| 상황 | 카피 (시니컬 누님 톤) |
|------|--------------------|
| 네트워크 끊김 | "*인터넷이 끊겼어. 재연결되면 알려줄게.*" |
| LLM 실패 | "*별기운이 잠시 약하네. 환불 처리됐어.*" |
| TTS 실패 | "*목소리가 잠겼어. 글로 읽어줘.*" |
| 결제 실패 | "*결제가 안 됐네. 다시 시도해줘.*" |
| 카드 거절 | "*카드사에서 막혔어. 다른 카드로 해볼까?*" |
| 일반 500 | "*뭔가 꼬였네. 잠시 후에.*" |
| 404 | "*없는 풀이네. 처음으로 가자.*" |

---

## Form Validation Rules

### 공통 원칙
- **Validation on blur** (입력 중 X — 매운맛이지만 *공격적이지 않게*).
- **Error message**: input 하단 1px 빨강 hairline + `--state-error` 텍스트, 4.5:1 contrast 유지.
- **Required indicator**: label 옆 amber dot (`*` 사용 X).

### 생년월일
- ISO 8601 (YYYY-MM-DD).
- 1900-01-01 ~ 오늘.
- 미래 날짜 → "*아직 태어나지 않았네.*"
- 존재하지 않는 날짜 (2월 30일) → "*그 날짜는 존재하지 않아.*"

### 시각
- HH:MM, 0~23:0~59.
- "시간 모름" 체크 시 input disabled + 안내 박스.

### 성별
- 라디오 — 한 개 필수.

### 이름 (옵셔널)
- 최대 20자.
- 한글/영문/공백만 허용 (이모지 X).
- skip 가능.

### 결제 폼
- 카드 정보는 SDK 위임, 자체 validation 없음.

---

## Accessibility Interaction Notes

- **Subtitle stream**: `aria-live="polite"`, `aria-atomic="false"` — 새 문장 등장 시 스크린리더가 자연스럽게 읽음.
- **Reading player controls**: `aria-label="재생/일시정지"`, keyboard `Space`로 toggle.
- **Tarot card**: `role="button"`, `aria-pressed` 토글, keyboard `Enter`/`Space`로 뒤집기.
- **Follow-up buttons**: 화살키 ↑↓ 네비, `Enter` 선택.
- **Modal trap**: focus trap 구현, `Escape`로 닫기, 닫힌 후 trigger element로 focus 복귀.
- **Stepper**: `aria-current="step"` on active dot.

---

## Template Completeness Check

| 섹션 | Status |
|------|--------|
| Motion philosophy | ✓ |
| Shared Element Transitions | ✓ (none planned, rationale 명시) |
| Drag & Drop | ✓ (N/A — PRD에 없음) |
| High-impact motion moments | ✓ (5개) |
| Page transition map | ✓ (3 patterns) |
| Flows (A-I) | ✓ (9 flows) |
| Loading/Empty/Error patterns | ✓ |
| Form validation | ✓ |
| Accessibility | ✓ |

---

## Confidence: **High**

모든 9 flows × (states + errors + motion + edge) 명시. ux_spec.md flows와 1:1 매핑. design_system.md motion tokens와 일치.
