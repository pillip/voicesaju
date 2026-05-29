# Wireframes — VoiceSaju · Ink & Amber

> 디자인 철학 "Ink & Amber"와 design_system.md 토큰을 기반으로 한 화면 명세.
> 모든 화면은 mobile-first (375px) 기준, tablet (768px) 및 desktop (1280px) 행동 명시.

---

## Screen Inventory & UX Spec Mapping

`docs/ux_spec.md` 의 26 screens 중 v1 핵심 12개를 wireframe에 작성.
나머지 14개는 design_system 토큰 조합으로 도출 가능 (P2 deferred or composition variation).

| # | Route | Wireframe | Priority |
|---|-------|-----------|----------|
| 1 | `/` | §1 Landing | P0 |
| 2 | `/onboarding/birth` | §2 Onboarding · 생년월일 | P0 |
| 3 | `/onboarding/time` | §3 Onboarding · 시각 (모름 옵션) | P0 |
| 4 | `/onboarding/gender` | §3.5 | P0 |
| 5 | `/onboarding/name` | §3.5 | P1 |
| 6 | `/category` | §4 Category Select | P0 |
| 7 | `/reading/intro` | §5 Intro + Paywall | P0 |
| 8 | `/payment` (modal/sheet) | §6 Payment Sheet | P0 |
| 9 | `/reading/play` | §7 Reading Player | P0 |
| 10 | `/reading/followup/:id` | §8 Follow-up Answer | P0 |
| 11 | `/reading/end` | §9 Signature Quote + Share | P0 |
| 12 | `/tarot` | §10 Daily Tarot | P0 |
| 13 | `/me` | §11 My Page | P0 |
| 14 | `/auth/login` | §12 Login | P0 |
| 15-26 | `/me/history`, `/me/billing`, `/me/edit-saju`, `/share/[slug]`, `/upsell/subscription`, `/legal/*`, error screens | §13 Composition Reuse | P1-P2 |

---

## §1. Landing — `/`

**목적**: 첫 5초 안에 "시니컬 + 신비"를 각인.

```
┌────────────────────────────────────────────┐
│  ☰              VoiceSaju ⓘ              │ ← nav-top (sticky, blur)
├────────────────────────────────────────────┤
│                                            │
│                                            │
│   흠.                                      │ ← 96px display, amber-300, italic
│   이 시간에 사주를 본다고?                  │ ← 32px display-han, cream-50
│                                            │
│   ─────────────                            │ ← hairline divider, 80px wide
│                                            │
│   새벽 3시의 누님이 직접 풀어줍니다.        │ ← 18px body, cream-200
│   목소리로.                                │
│                                            │
│                                            │
│         [   사주 풀러 가기   ]             │ ← btn-primary, amber-400
│                                            │
│         오늘의 타로 한 장만 →               │ ← btn-ghost link
│                                            │
│                                            │
│  ─────────────                             │
│  甲乙丙丁  戊己庚辛  壬癸                  │ ← 8px hanja, cream-600
│  연애 · 직장 · 금전                         │ ← caption meta
└────────────────────────────────────────────┘
```

### Layout & Composition
- **Asymmetric left-aligned**: 헤드라인 좌측 끝, 우측 여백 풍부
- **Background**: `--ink-900` + `--grain-medium` overlay
- **Content max-width**: `--container-narrow` (560px), 모바일 16px 좌우 padding
- **Hero spacing**: 상단 `--space-32`, 헤드라인 후 `--space-12`, CTA 후 `--space-16`
- **Bottom**: 한자 디테일 (8-10px) + 카테고리 caption — *풍수의 흔적*

### Responsive
- **Mobile (375px)**: 헤드라인 56px, 한 줄 wrap 허용
- **Tablet (768px)**: 헤드라인 80px, asymmetric padding 좌 64px
- **Desktop (1280px)**: 헤드라인 96px, 좌측 정렬 + 우측 빈공간 의도적

### States

| State | Description |
|-------|-------------|
| **Default** | 위 레이아웃 |
| **Loading** | N/A (정적 페이지) — 첫 진입 시 폰트 로드 fallback `font-display: swap` |
| **Empty** | N/A |
| **Error** | 네트워크 끊김 시: 페이지 그대로, CTA 클릭 시 토스트 "*인터넷 연결을 확인해줘.*" |
| **Edge: returning user** | "흠. 또 왔네." + CTA 변경 "*저번 풀이 다시 듣기*" |

---

## §2. Onboarding — 생년월일 (`/onboarding/birth`)

**목적**: 입력 부담 최소화 + 진행률 안내.

```
┌────────────────────────────────────────────┐
│  ← 뒤로                          STEP 1/4 │ ← nav-top
├────────────────────────────────────────────┤
│                                            │
│  생년월일                                  │ ← 32px display-han, cream-50
│                                            │
│  먼저, 너 언제 태어났어?                    │ ← 18px body, cream-300
│                                            │
│  ─────────────                             │
│                                            │
│  YYYY-MM-DD                                 │ ← input-label uppercase caption
│  [ 1997-03-15           ]                  │ ← input with bottom border
│                                            │
│  ○ 양력      ● 음력      ○ 음력 윤달        │ ← radio (custom)
│                                            │
│                                            │
│                                            │
│                                            │
│  ●●○○                                      │ ← stepper dots
│                                            │
│  [        다음        ]                    │ ← btn-primary full-width
└────────────────────────────────────────────┘
```

### Spatial Notes
- **Single field per screen** — Aesop 절제, 인지 부하 최소
- **Stepper dots**: 진행 4개 dots, 활성=amber, 완료=cream-300
- **Solar/Lunar toggle**: radio with hairline indicator (not pill)

### States

| State | Description |
|-------|-------------|
| **Default** | 입력 대기, placeholder "YYYY-MM-DD" `--cream-400` |
| **Loading** | 다음 클릭 후 spinner inside btn (`aria-busy=true`) |
| **Empty** | 첫 진입 시 default 동일 |
| **Error (invalid date)** | input 하단 빨강 hairline + "*그 날짜는 존재하지 않아.*" `--state-error` |
| **Error (future date)** | "*아직 태어나지 않았네.*" |
| **Edge (음력 윤달 선택)** | 추가 안내: "*윤달이면 정확한 명식을 위해 한 번 더 확인해줘.*" |

---

## §3. Onboarding — 시각 + 모름 옵션 (`/onboarding/time`)

**목적**: 시각 모름을 자연스럽게 처리 (한국 사용자 친화).

```
┌────────────────────────────────────────────┐
│  ← 뒤로                          STEP 2/4 │
├────────────────────────────────────────────┤
│                                            │
│  태어난 시각                                │
│                                            │
│  몇 시쯤이었어?                             │ ← cream-300
│                                            │
│  ─────────────                             │
│                                            │
│  HH : MM                                    │ ← caption
│  [ 14 ] : [ 30 ]                           │ ← two inputs, mono font
│                                            │
│  □ 시간 모름                                │ ← checkbox
│                                            │
│  ┌──────────────────────────────────────┐  │ ← collapsed help, hidden until check
│  │ ⓘ 시간을 모르면 큰 줄기는 봐도         │  │
│  │   디테일은 조금 흐릿해. 괜찮아.        │  │
│  └──────────────────────────────────────┘  │
│                                            │
│  ●●●○                                      │
│                                            │
│  [        다음        ]                    │
└────────────────────────────────────────────┘
```

### Behavior
- 체크박스 활성화 시 input 비활성화 + 안내 박스 fade-in (200ms)
- input은 24h 형식, 캐릭터별로 separate (mono font, 큰 글자 36px)

### States

| State | Description |
|-------|-------------|
| **Default** | 시간 입력 대기 |
| **Loading** | 다음 버튼 spinner |
| **Empty** | "시간 모름" 미체크 + input 비어있음 → 다음 disabled |
| **Error** | 24h 범위 초과 (e.g., "25:30") → "*그건 시간이 아니야.*" |
| **Edge: 시간 모름 체크** | input disabled, 회색 처리, 안내 박스 노출 |

---

## §3.5. Onboarding — 성별 / 이름 (composition)

같은 레이아웃, 다른 컨텐츠:

- **성별**: 두 개의 큰 텍스트 옵션 ("여자 / 남자"), 선택 시 amber 좌측 라인.
- **이름 (옵셔널)**: 텍스트 input + "건너뛰기" ghost 버튼.

---

## §4. Category Select — `/category`

**목적**: 카테고리를 *물건*이 아닌 *질문*으로 제시.

```
┌────────────────────────────────────────────┐
│  ← 뒤로                                ⓘ  │
├────────────────────────────────────────────┤
│                                            │
│  뭐가 제일 궁금해?                          │ ← 48px display-han
│                                            │
│  ─────────────                             │
│                                            │
│  │ 연애                                    │ ← chip border-left cat-love
│  │ 결혼? 헤어짐? 짝사랑?                    │ ← 18px body cream-200
│                                            │
│  │ 직장                                    │ ← chip border-left cat-work
│  │ 이직? 상사? 사업?                       │
│                                            │
│  │ 금전                                    │ ← chip border-left cat-money
│  │ 빚? 투자? 가난할까?                      │
│                                            │
│  ─────────────                             │
│                                            │
│  오늘의 타로 한 장 →                        │ ← ghost link, 우측 하단
└────────────────────────────────────────────┘
```

### Spatial Notes
- **Vertical stack of 3 large tappable areas** — 카드 아님, hairline 라벨 + 본문만
- **Tap target**: 카테고리 영역 전체 (84px min height)
- **Left border**: 카테고리 시그니처 컬러 2px

### States

| State | Description |
|-------|-------------|
| **Default** | 3개 카테고리 노출 |
| **Loading** | N/A |
| **Empty** | N/A |
| **Error** | 선택 후 다음 페이지 fetch 실패 → 토스트 "*잠시 별기운이 약하네.*" |
| **Edge: 두 번째 사주 (signup 필요)** | 클릭 시 로그인 modal "*이번엔 가입하고 가야 해.*" |

---

## §5. Reading Intro + Paywall — `/reading/intro`

**목적**: 캐릭터 보이스로 후킹 → 결제 결정.

```
┌────────────────────────────────────────────┐
│  ← 뒤로                  연애 · 1997-03-15 │
├────────────────────────────────────────────┤
│                                            │
│            ✦                               │ ← amber dot 12px, centered top
│                                            │
│                                            │
│       [silhouette of woman]                │ ← 200×200 character, 50% opacity
│       (시니컬 누님 손/실루엣)               │   mix-blend-mode: screen
│                                            │
│                                            │
│   ────────────────────                     │ ← hairline
│                                            │
│   어디 보자… 1997년생 무자년…              │ ← 22px display-han, cream-50
│   음, 재미있네.                            │   subtitle stream
│                                            │
│   ────────────────────                     │
│                                            │
│                                            │
│   [ ▷ 본격 풀이 받기 · ₩4,900 ]            │ ← btn-primary
│                                            │
│   구독하면 다 포함 · ₩9,900/월              │ ← btn-ghost
│                                            │
└────────────────────────────────────────────┘
```

### Audio Behavior
- **자동 재생**: 페이지 로드 200ms 후 인트로 15초 시작
- **자막 stream**: 한 문장씩 fade-up (200ms stagger)
- **인트로 끝나면 5초 정지** → CTA가 부드럽게 amber 강조

### States

| State | Description |
|-------|-------------|
| **Default** | 인트로 재생 중, 자막 흐름 |
| **Loading** | TTS 첫 청크 대기 시 spinner 작게 (≤1.5s) |
| **Empty** | N/A |
| **Error (TTS 실패)** | 자막만 표시, 캐릭터 상단 작은 안내 "*목소리가 잠겼네. 글로만 봐줘.*" |
| **Edge (재시청)** | 우측 상단 "이미 인트로 들었다 →" ghost link, 즉시 CTA 활성 |

---

## §6. Payment Sheet (Modal / Bottom Sheet)

**목적**: 최소 진입 장벽 + 토스/카카오 결제 분기.

```
┌────────────────────────────────────────────┐
│ ─────                                      │ ← bottom sheet drag handle
│                                            │
│  결제                                      │ ← 32px display-han
│                                            │
│  연애 · 사주 풀이 + 꼬리질문 3개            │ ← cream-300 caption
│                                            │
│  ─────────────                             │
│                                            │
│  ₩4,900                                    │ ← 48px display, cream-50
│                                            │
│  ─────────────                             │
│                                            │
│  [    토스페이로 결제    ]                 │ ← btn-primary
│                                            │
│  [   카카오페이로 결제   ]                 │ ← btn-secondary (웹 only)
│                                            │
│                                            │
│  먼저 가입하면 1회 무료 →                   │ ← btn-ghost link
│                                            │
└────────────────────────────────────────────┘
```

### Channel Variants
- **Web**: 토스페이 + 카카오페이 2개 노출
- **Toss WebView**: 토스페이 단일 (카카오페이 hidden)

### States

| State | Description |
|-------|-------------|
| **Default** | 위 |
| **Loading** | "결제 진행 중…" spinner + buttons disabled |
| **Empty** | N/A |
| **Error (결제 실패)** | 토스트 + 시트 유지 "*결제가 안 됐네. 다시 시도해줘.*" |
| **Error (카드 거절)** | "*카드사에서 막혔어. 다른 카드로 해볼까?*" |
| **Edge (구독자)** | 시트 안 열림 — 바로 reading/play로 |

---

## §7. Reading Player — `/reading/play`

**목적**: 1~2분 음성 + 자막 + 캐릭터 + 명식 시각화의 *침묵의 무게*.

```
┌────────────────────────────────────────────┐
│  ← 뒤로                  연애 · 1/4 진행   │ ← progress meta
├────────────────────────────────────────────┤
│                                            │
│    [silhouette·시니컬 누님 손]              │
│                                            │
│    ────────────────────                    │
│                                            │
│    "직장 상사가 너 좀 미워하지?            │ ← 32px display-han, amber-300
│    그건 네 잘못 아니야.                    │   (current line)
│    근데 너도 좀 받아쳐야겠다."             │
│                                            │
│    ────────────────────                    │
│                                            │
│  ┌──── 명식 (sticky bottom collapse) ────┐ │
│  │  甲  辛  丁  ?                       │ │ ← saju-chart, "시 모름"의 ?
│  │  子  亥  卯  ?                       │ │
│  │  목 토 화 ─                          │ │
│  └────────────────────────────────────┘ │
│                                            │
│  [ ▷ ]  ━━━━━━━━━━━━━━ 0:42 / 1:38      │ ← voice-player controls
│                                            │
└────────────────────────────────────────────┘
```

### Behavior
- **자막 stream**: 현재 문장 `--amber-300`, 이전 문장 `--cream-300` (위로 fade out)
- **명식 collapse**: 기본 펼침, 탭 시 접힘 (mobile 화면 절약)
- **컨트롤**: play/pause + 다시 듣기. 구간 이동 X.

### States

| State | Description |
|-------|-------------|
| **Default** | 재생 중, 자막 흐름, 명식 펼침 |
| **Loading** | 첫 청크 대기 spinner 좌측 상단 |
| **Empty** | N/A (paywall 통과 후 진입) |
| **Error (LLM 실패)** | 캐릭터 silhouette 사라짐 + "*별기운이 약하네… 잠시 후 다시 들려줄게.*" + 자동 환불 안내 modal |
| **Error (TTS 실패)** | 자막만 노출, "*목소리가 잠겼어. 글로 읽어줘.*" 토스트 |
| **Edge (재생 완료)** | 자동 transition to §8 follow-up |
| **Edge (네트워크 끊김)** | 일시정지, "*재연결되면 이어서 들려줄게.*" 토스트 |

---

## §8. Follow-up Buttons + Answer — `/reading/followup`

**목적**: 매운맛 꼬리질문 3개 → 30~40초 답변.

### 8a. Question Selection

```
┌────────────────────────────────────────────┐
│  ← 뒤로                  꼬리질문 (3 남음) │
├────────────────────────────────────────────┤
│                                            │
│  더 알고 싶은 거 골라.                      │ ← 32px display-han
│                                            │
│  ─────────────                             │
│                                            │
│  — 이 사람이랑 결혼해도 돼?                 │ ← followup-btn
│                                            │
│  — 올해 이직이 좋아?                        │
│                                            │
│  — 빚 갚을 수 있어?                         │
│                                            │
│  ─────────────                             │
│                                            │
│  이만 마칠게요 →                            │ ← btn-ghost
└────────────────────────────────────────────┘
```

### 8b. Answer (single question selected)

```
┌────────────────────────────────────────────┐
│  ← 뒤로                  꼬리질문 (2 남음) │
├────────────────────────────────────────────┤
│                                            │
│  Q. 이 사람이랑 결혼해도 돼?                │ ← cream-300, caption
│                                            │
│  ─────────────                             │
│                                            │
│    "결혼? 음...                            │ ← 32px display-han, amber-300
│     그 사람은 너랑 코드가 안 맞아.          │   subtitle stream
│     1년 안에 끝나."                        │
│                                            │
│  ─────────────                             │
│                                            │
│  [ ▷ ]  ━━━━━━━━━━ 0:18 / 0:36           │
│                                            │
│  ─────────────                             │
│                                            │
│  다른 질문 ↓                                │ ← collapsed remaining buttons
└────────────────────────────────────────────┘
```

### States

| State | Description |
|-------|-------------|
| **Default** | 3개 버튼 노출 (8a) |
| **Loading** | 클릭 후 답변 fetch 중 spinner |
| **Empty** | N/A |
| **Error** | LLM 실패 시 해당 버튼 다시 활성, 토스트 "*그 답은 못 들었어. 다시 골라.*" (꼬리질문 차감 X) |
| **Edge (3개 모두 사용)** | "이만 마칠게요" 자동 강조 + auto-progress 5초 후 §9 |

---

## §9. Signature Quote Card + Share — `/reading/end`

**목적**: 잊을 수 없는 한 줄 + 자연 바이럴.

```
┌────────────────────────────────────────────┐
│                                       닫기 │
├────────────────────────────────────────────┤
│                                            │
│  ┌──────────────────────────────────┐     │
│  │                                  │     │ ← quote-card-preview 9:16
│  │   LOVE                           │     │   border-left cat-love
│  │                                  │     │
│  │                                  │     │
│  │   "그 사람은 너랑                 │     │ ← 36px display-han
│  │    코드가 안 맞아."              │     │   amber-300
│  │                                  │     │   appears at 5s
│  │                                  │     │
│  │                                  │     │
│  │   VoiceSaju ⓘ                   │     │ ← watermark, italic
│  │                                  │     │
│  └──────────────────────────────────┘     │
│                                            │
│  ─────────────                             │
│                                            │
│  [ 인스타 스토리 ] [ 카톡 ] [ 저장 ]        │ ← share-row
│                                            │
│  히스토리에 저장됨 ✓                        │ ← cream-300 caption
│                                            │
│  [   처음으로   ]                          │ ← btn-secondary
└────────────────────────────────────────────┘
```

### Behavior
- **5초 정지** 후 한 줄 fade-up — *기다림의 무게*
- **저장 버튼**: 클라이언트 캔버스 → 1080×1920 PNG 다운로드
- **공유**: 서버 OG 이미지 URL 복사 (인스타 스토리는 외부 앱 호출)

### States

| State | Description |
|-------|-------------|
| **Default** | 카드 빈 상태 → 5초 후 quote fade-up |
| **Loading** | 카드 백그라운드 generation 중 skeleton 0.5초 |
| **Empty** | N/A |
| **Error (OG 실패)** | 클라이언트 캔버스 fallback + 안내 "*저장은 되지만 공유 미리보기가 안 보일 수 있어.*" |
| **Edge (비회원)** | 카드 노출 + "*가입하면 영구 저장. 1초.*" CTA |

---

## §10. Daily Tarot — `/tarot`

**목적**: 매일 1장 가벼운 후킹.

```
┌────────────────────────────────────────────┐
│  ← 뒤로            이번 주 무료 1회 남음   │ ← quota-banner, amber border
├────────────────────────────────────────────┤
│                                            │
│  오늘의 카드                                │ ← 48px display-han
│                                            │
│  ─────────────                             │
│                                            │
│                                            │
│                ┌──────┐                    │ ← tarot-card 200×333
│                │ ✦    │                    │   back face, ink-700 + pattern
│                │      │                    │
│                │  ✦   │                    │
│                │      │                    │
│                │    ✦ │                    │
│                └──────┘                    │
│                                            │
│         탭해서 뽑기                         │ ← cream-300 caption pulse
│                                            │
│                                            │
│  ─────────────                             │
│                                            │
│  甲乙丙丁 · 메이저 아르카나 22장             │ ← caption meta
└────────────────────────────────────────────┘
```

### After Flip

```
│                                            │
│                ┌──────┐                    │ ← front face
│                │      │                    │   custom illustration
│                │ The  │                    │
│                │ Moon │                    │
│                │  ☾   │                    │
│                │ XVIII│                    │
│                └──────┘                    │
│                                            │
│  ─────────────                             │
│                                            │
│  "오늘은…                                  │ ← 노인 도사 voice
│   숨겨진 진실이 보이는 날.                  │
│   섣불리 결정하지 말게나."                  │
│                                            │
│  [ ▷ ]  ━━━━━━ 0:12 / 0:38                │
│                                            │
│  [ 공유하기 ]   [ 명대사 저장 ]             │
└────────────────────────────────────────────┘
```

### States

| State | Description |
|-------|-------------|
| **Default (미사용)** | 카드 뒷면, "탭해서 뽑기" pulse |
| **Default (사용 완료)** | 카드 앞면 + 오늘 풀이 + 공유 — *재방문해도 같은 카드* (결정적 시드) |
| **Loading** | 뒤집기 애니메이션 후 음성 첫 청크 대기 spinner |
| **Empty (quota 소진)** | 카드 회색 잠금 + "*이번 주는 다 봤어. 구독하면 매일 볼 수 있어.*" + CTA |
| **Error** | TTS 실패 시 자막 fallback |
| **Edge (자정 KST 직후)** | 새 카드 자동 노출 + 작은 안내 "*새 날, 새 카드.*" |

---

## §11. My Page — `/me`

**목적**: 내 사주 시각화 + 히스토리 + 결제 관리.

```
┌────────────────────────────────────────────┐
│  ☰        My Page                       ⓘ │
├────────────────────────────────────────────┤
│                                            │
│  내 명식                                   │ ← 32px display-han
│                                            │
│  ┌──────────────────────────────────────┐  │
│  │  시   일   월   년                   │  │ ← saju-chart
│  │  ?   甲   辛   丁                    │  │
│  │  ?   子   亥   卯                    │  │
│  │  ─   목   토   화                    │  │
│  │  시간 모름                            │  │
│  └──────────────────────────────────────┘  │
│                                            │
│  생일 수정 (2회 무료 남음) →                │ ← btn-ghost
│                                            │
│  ─────────────                             │
│                                            │
│  히스토리                                  │
│                                            │
│  │ 연애 · 2026-05-22                       │ ← list item
│  │ "그 사람은 너랑 코드가…"  ▷             │   amber preview line
│                                            │
│  │ 직장 · 2026-05-15                       │
│  │ "이직? 가도 돼. 근데…"   ▷              │
│                                            │
│  더보기 →                                  │
│                                            │
│  ─────────────                             │
│                                            │
│  결제 / 구독                                │
│                                            │
│  무료 회원 · 이번 주 타로 0/1 남음          │ ← cream-300 caption
│                                            │
│  [   구독하고 매일 받기   ]                 │ ← btn-primary
│                                            │
│  ─────────────                             │
│                                            │
│  [ 홈 ] [ 사주 ] [ 타로 ] [ 마이 ]          │ ← tab-bar
└────────────────────────────────────────────┘
```

### States

| State | Description |
|-------|-------------|
| **Default** | 위 |
| **Loading** | skeleton 카드 (chart + history list) |
| **Empty (히스토리 없음)** | 히스토리 섹션 "*아직 풀이가 없어. 첫 풀이 받으러 갈래?*" + CTA |
| **Empty (사주 정보 없음)** | "내 명식" 자리 "*먼저 사주 정보 입력해줘.*" + CTA |
| **Error** | 섹션별 inline error + 재시도 ghost 버튼 |
| **Edge (구독자)** | "결제 / 구독" 섹션 "이번 달 사주 0/1, 타로 매일 무제한" + 구독 해지 ghost |

---

## §12. Login — `/auth/login`

**목적**: 1초 가입 — 진입 장벽 최소.

```
┌────────────────────────────────────────────┐
│  ← 뒤로                                    │
├────────────────────────────────────────────┤
│                                            │
│                                            │
│  결과 저장하려면                            │ ← 48px display-han
│  1초 가입.                                  │
│                                            │
│  ─────────────                             │
│                                            │
│  [    카카오로 시작    ]                   │ ← btn-primary (yellow→amber)
│                                            │
│  [     Apple로 시작     ]                  │ ← btn-secondary
│                                            │
│  ─────────────                             │
│                                            │
│  이미 가입한 적 있어 →                      │ ← btn-ghost (auto-detect)
│                                            │
│                                            │
│  ─────────────                             │
│                                            │
│  가입하면 약관과 개인정보 처리방침에        │ ← 12px caption cream-400
│  동의한 것으로 봐.                          │
└────────────────────────────────────────────┘
```

### States

| State | Description |
|-------|-------------|
| **Default** | 위 |
| **Loading** | OAuth redirect 중 spinner full-screen |
| **Empty** | N/A |
| **Error (OAuth 실패)** | "*카카오/애플 로그인이 안 됐네. 다시 해볼까?*" |
| **Edge (Toss WebView)** | "카카오/애플" 버튼 hidden, "토스 아이디로 시작" 단일 노출 |

---

## §13. Composition Reuse (P1-P2 화면)

다음 화면들은 위 12개 화면의 **컴포지션 재사용**:

- `/me/history` — §11의 히스토리 리스트만 풀스크린
- `/me/billing` — §11 결제 섹션 + 구독 해지 destructive 버튼
- `/me/edit-saju` — §2-§3 onboarding 재사용 + "2회 남음" caption
- `/share/[slug]` — §9 quote card preview 풀스크린 + OG meta
- `/upsell/subscription` — §1 landing 구조 + 구독 CTA
- `/legal/*` — long-form serif 본문 (Aesop 약관 페이지 스타일)

### Error Screens (P0)

- **404**: "*없는 풀이네. 처음으로 가자.*" + ghost link
- **500**: "*별기운이 잠시 약해. 잠시 후 다시.*" + retry button
- **Offline**: "*인터넷이 끊겼어. 재연결되면 알려줄게.*"

모두 §1 Landing의 어조와 일관, 사용자 책임 표현 회피.

---

## PRD Feature Cross-check

| PRD Section | Feature | Wireframe Coverage |
|-------------|---------|-------------------|
| §5.1 | 단계별 온보딩 | §2, §3, §3.5 ✓ |
| §5.2 | 사주 풀이 흐름 (인트로/페이월/본풀이/꼬리질문) | §5, §6, §7, §8 ✓ |
| §5.3 | 데일리 타로 | §10 ✓ |
| §5.4 | 명대사 카드 + 공유 | §9 ✓ |
| §5.5 | 결제·구독 | §6, §11 ✓ |
| §5.6 | 회원/비회원 분기 | §12 + 비회원 흐름은 §5/§9/§11 edge case |
| §5.7 | 마이페이지 | §11 ✓ |
| §6.4 | 오류 처리 | 각 화면 States 표 ✓ |
| §6.3 | 접근성 (자막 동시 노출) | §5, §7, §8, §10 자막 stream 명시 ✓ |

**P2 deferred (note만 표시)**: 캐릭터 선택, 추가 카테고리, 다중 카드 스프레드, 궁합/연간운세, 알림 — wireframe 없음, 노출 위치만 §11 my page에 "(준비 중)" placeholder.

---

## Responsive Breakpoint Behavior

| Screen | Mobile (375) | Tablet (768) | Desktop (1280) |
|--------|-------------|-------------|----------------|
| **Landing** | 56px h1, vstack | 80px h1, asymmetric | 96px h1 + 우측 빈공간 |
| **Onboarding** | full-width input, btn fixed bottom | container-narrow centered | container-narrow + left-aligned |
| **Category** | vstack 3 items 84px each | wider tap area | container-narrow centered |
| **Intro/Reading** | 200×200 character | 280×280 | 360×360, 자막 옆 |
| **Payment Sheet** | bottom sheet 풀너비 | bottom sheet 480px max | center modal 480px |
| **Tarot** | 200×333 card center | 240×400 | 280×467 |
| **My Page** | single column, tab-bar 하단 | single column, side nav 옵션 | two-column (chart 좌 / history 우) |

---

## Confidence: **High**

모든 P0 화면의 5 states 명시 완료. design_system.md 컴포넌트와 1:1 매핑. ux_spec.md 26 screens 중 14개는 위 12개의 compositional reuse로 도출 가능.
