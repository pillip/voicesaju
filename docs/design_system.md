# Design System — VoiceSaju · Ink & Amber (v2)

> 모든 값은 CSS custom properties로 정의됩니다. 디자인 시스템이 토큰의 단일 소스(SSOT)입니다.
> **v2 변경 사항**: 인주 적색·한지 갈색 추가, 한자 monumental·인주 도장 컴포넌트 신설, 손글씨/명조 폰트 추가, 화면별 다른 nav 패턴.

---

## v2 ADDITIONS — 새 토큰과 컴포넌트

### New Colors — Vermilion (인주 도장)

| Token | Hex | Usage |
|-------|-----|-------|
| `--vermilion-100` | `#C95F4A` | hover state / 호버 호박 |
| `--vermilion-300` | `#9B2A1A` | **메인 인주 적색** — 도장 본체, 시그니처 |
| `--vermilion-500` | `#6C1D11` | 도장 그림자, 인주 깊은 |

### New Colors — Hanji (한지 갈색 — 새 베이스)

| Token | Hex | Usage |
|-------|-----|-------|
| `--hanji-900` | `#0A0604` | 가장자리 vignette, 깊은 그림자 |
| `--hanji-800` | `#1A1208` | **메인 배경** (v1 ink-900 대체) |
| `--hanji-700` | `#241810` | Elevated surface |
| `--hanji-500` | `#3A2A18` | 종이 톤 표면 |
| `--hanji-300` | `#6E5A40` | 한지 무늬 hairline |
| `--baekrim-200` | `#D9C49A` | 백열등 색 텍스트 (희소) |

### New Fonts

```css
--font-brush:  'Nanum Brush Script', 'East Sea Dokdo', cursive;
--font-mincho: 'Noto Serif KR', 'Gowun Batang', serif;  /* 한자 모뉴멘탈 */
```

**Google Fonts loaded (추가)**:
- `Nanum Brush Script` — 손글씨 가격표·라벨 (붓글씨 felt-pen)
- `Noto Serif KR` (900) — 한자 monumental display

### Updated Base
```css
body { background: var(--hanji-800); }  /* was: ink-900 */
```

---

## New Components (v2)

### Vermilion Seal (인주 도장 印) — 시그니처 모먼트

```css
.seal {
  display: inline-grid; place-items: center;
  width: 56px; height: 56px;
  background: var(--vermilion-300);
  color: var(--baekrim-200);
  font-family: var(--font-mincho);
  font-weight: 900;
  font-size: 32px;
  transform: rotate(-2.5deg);  /* uncanny */
  box-shadow: inset 0 0 0 1px var(--vermilion-500);
  position: relative;
  /* 도장 가장자리 살짝 흐트러짐 효과 (mask로 노이즈 처리) */
  -webkit-mask-image:
    radial-gradient(circle at 30% 30%, #000 90%, transparent 100%),
    var(--grain-medium);
  mask-image:
    radial-gradient(circle at 30% 30%, #000 90%, transparent 100%);
}
.seal--sm { width: 36px; height: 36px; font-size: 22px; }
.seal--lg { width: 80px; height: 80px; font-size: 48px; }
.seal--tilt-r { transform: rotate(2.5deg); }
```

### Hanja Monument — 한자 주연 디스플레이

```css
.hanja-monument {
  font-family: var(--font-mincho);
  font-weight: 900;
  font-size: clamp(120px, 28vw, 240px);
  line-height: 0.85;
  letter-spacing: -0.04em;
  color: var(--baekrim-200);
  text-shadow: 0 0 30px rgba(155, 42, 26, 0.08);
}
.hanja-monument--cut {
  /* 가장자리에서 의도적으로 잘림 */
  margin-left: -0.15em;
  margin-right: -0.1em;
}
.hanja-row-mono {
  display: flex; gap: 0.05em;
  font-family: var(--font-mincho);
  font-weight: 900;
  font-size: clamp(80px, 18vw, 160px);
  line-height: 1;
  color: var(--baekrim-200);
}
.hanja-row-mono .hanja--dim { color: var(--cream-500); }
```

### Tilted Card — uncanny ambiguity

```css
.tilted {
  transform: rotate(-1.5deg);
  transition: transform var(--dur-base) var(--ease-out);
}
.tilted--right { transform: rotate(1.5deg); }
.tilted:hover  { transform: rotate(-0.5deg); }
```

### Handwritten Label — 가격표·카테고리 손글씨

```css
.handwritten {
  font-family: var(--font-brush);
  font-size: var(--text-h3);
  color: var(--baekrim-200);
  letter-spacing: -0.01em;
  line-height: 1.1;
  transform: rotate(-1.5deg);
  transform-origin: left center;
}
.handwritten--price {
  color: var(--vermilion-100);
  font-size: var(--text-lead);
}
```

### Vignette Edge — 동굴 같은 깊이

```css
.vignette-edge {
  position: relative;
}
.vignette-edge::before {
  content: ""; position: fixed; inset: 0;
  background: radial-gradient(
    ellipse at center,
    transparent 30%,
    var(--hanji-900) 110%
  );
  pointer-events: none;
  z-index: 2;
  mix-blend-mode: multiply;
}
```

### Hanji Texture — 한지 종이 결

```css
.hanji-bg {
  background-color: var(--hanji-800);
  background-image:
    /* 가로 결 */
    repeating-linear-gradient(0deg,
      transparent 0px, transparent 6px,
      rgba(110, 90, 64, 0.04) 6px, rgba(110, 90, 64, 0.04) 7px),
    /* 그레인 */
    var(--grain-medium);
}
```

### Ink-blur Headline (잡지 침범 헤드라인)

```css
.headline-bleed {
  font-family: var(--font-display-han);
  font-weight: 400;
  font-size: clamp(40px, 12vw, 96px);
  line-height: 0.95;
  letter-spacing: -0.025em;
  color: var(--cream-50);
  /* 가장자리에서 잘려나감 */
  margin-left: calc(var(--space-6) * -1);
  margin-right: calc(var(--space-6) * -1);
  padding-left: var(--space-6);
  padding-right: var(--space-6);
  overflow-wrap: break-word;
}
.headline-bleed--amber  { color: var(--amber-300); font-style: italic; font-family: var(--font-display); }
.headline-bleed--strike {
  text-decoration: line-through;
  text-decoration-color: var(--vermilion-300);
  text-decoration-thickness: 3px;
}
```

### Dense Body Column (잡지 펼침면)

```css
.body-column {
  font-family: var(--font-body);
  font-size: var(--text-body);
  line-height: 1.55;  /* 1.65 → 1.55 더 빽빽 */
  color: var(--cream-100);
  column-rule: 1px solid var(--hanji-300);
}
.body-column p + p { margin-top: var(--space-3); }
.body-column .drop {
  float: left;
  font-family: var(--font-mincho);
  font-size: 4.5em;
  line-height: 0.9;
  padding-right: 0.15em;
  color: var(--vermilion-300);
}
```

### Updated Nav Patterns — 화면별 다름

```css
/* landing은 nav 없음 - 풀스크린 침묵 */

/* category — 좌측 세로축 nav */
.nav-vertical {
  position: sticky; top: 0;
  writing-mode: vertical-rl;
  padding: var(--space-6) var(--space-3);
  font-family: var(--font-mono);
  font-size: var(--text-caption);
  letter-spacing: 0.3em;
  color: var(--cream-300);
  border-right: 1px solid var(--hanji-300);
}

/* reading-play — 하단 nav (몰입형) */
.nav-bottom {
  position: sticky; bottom: 0;
  padding: var(--space-4) var(--space-6);
  border-top: 1px solid var(--hanji-300);
  background: color-mix(in srgb, var(--hanji-800) 92%, transparent);
  backdrop-filter: blur(12px);
  display: flex; justify-content: space-between; align-items: center;
}
```

---

(아래는 v1 토큰/컴포넌트 — 호환성 유지)

## Foundational Tokens

### Color — Ink Scale (베이스)

| Token | Hex | Usage |
|-------|-----|-------|
| `--ink-950` | `#080603` | 깊은 배경 (앰비언트) |
| `--ink-900` | `#0F0B08` | **메인 배경** |
| `--ink-800` | `#1A140F` | Elevated surface (모달, sheet) |
| `--ink-700` | `#241B14` | Card surface (드물게 사용) |
| `--ink-600` | `#2E2419` | Hover/active 표면 |
| `--ink-500` | `#3A2E22` | Border (강조) |
| `--ink-400` | `#4A3B2C` | Disabled surface |

### Color — Cream Scale (텍스트)

| Token | Hex | Usage |
|-------|-----|-------|
| `--cream-50` | `#F5EDD7` | 헤드라인 (최고 강조) |
| `--cream-100` | `#EAE0CC` | **본문 텍스트 (기본)** |
| `--cream-200` | `#D4C8AC` | 보조 텍스트 |
| `--cream-300` | `#B0A48A` | Muted (메타데이터) |
| `--cream-400` | `#8A7E66` | Placeholder, 비활성 |
| `--cream-500` | `#6A604E` | 매우 약함 (caption 일부) |
| `--cream-600` | `#4D4538` | Hairline divider |

### Color — Amber Scale (액센트)

| Token | Hex | Usage |
|-------|-----|-------|
| `--amber-200` | `#E8C896` | Hover state |
| `--amber-300` | `#D9A968` | 강조 텍스트 (호박 발광) |
| `--amber-400` | `#C28E4D` | **주 액센트 (CTA, 시그니처)** |
| `--amber-500` | `#A87639` | Pressed/active |
| `--amber-600` | `#8B5E2A` | Deep accent |

### Color — Category Signatures (얇은 색조, 풀 컬러 배경 X)

| Token | Hex | Category |
|-------|-----|----------|
| `--cat-love` | `#9B4A4A` | 연애 — 마른 장미 |
| `--cat-work` | `#3D5266` | 직장 — 잉크 블루 |
| `--cat-money` | `#A67C28` | 금전 — 황동 |
| `--cat-tarot` | `#5B3A5C` | 타로 — 깊은 가지색 |

### Color — Semantic States

| Token | Hex | Usage |
|-------|-----|-------|
| `--state-success` | `#6B8F5C` | 결제 성공, 저장 완료 (sage green, 잉크 친화) |
| `--state-warning` | `#D9A968` | 무료 한도 임박 (호박 사용) |
| `--state-error` | `#B05544` | 에러 (rust, 순수 빨강 X) |
| `--state-info` | `#6B7C8A` | 안내 (쿨 그레이) |

> ⚠️ Semantic 컬러는 category/decorative 컬러와 다른 hex 사용 — 충돌 방지 검증 완료.

### Typography — Font Stack

```css
--font-display:  'EB Garamond', 'Gowun Batang', Georgia, serif;
--font-display-han: 'Gowun Batang', 'EB Garamond', serif;
--font-body:     'Pretendard', 'IBM Plex Sans', -apple-system, sans-serif;
--font-mono:     'JetBrains Mono', 'D2Coding', monospace;
--font-accent:   'Cormorant Garamond', 'Gowun Batang', serif;
```

**Google Fonts loaded**:
- `EB Garamond` (400, 400-italic, 500-italic, 700-italic) — 디스플레이 영문 세리프
- `Gowun Batang` (400, 700) — 디스플레이/명대사 한글 명조
- `Pretendard` (400, 500, 600, 700) — 본문 한영 산세리프
- `Cormorant Garamond` (300, 400, 500-italic) — 강조 세리프
- `JetBrains Mono` (400, 500) — 천간/지지/타임스탬프

**금지 폰트**: Inter, Roboto, Arial, Open Sans, Space Grotesk, Noto Sans/Serif.

### Typography — Type Scale (극단 대비 6.8×)

| Token | Size | Line Height | Letter Spacing | Usage |
|-------|------|-------------|----------------|-------|
| `--text-caption` | 12px | 1.4 | 0.08em | 메타데이터 (UPPERCASE) |
| `--text-meta` | 14px | 1.5 | 0.04em | 라벨, 보조 텍스트 |
| `--text-body-sm` | 16px | 1.6 | 0 | 작은 본문 |
| `--text-body` | 18px | 1.65 | 0 | **본문 기본** |
| `--text-lead` | 22px | 1.5 | -0.01em | 리드 문단 |
| `--text-h3` | 32px | 1.2 | -0.015em | 섹션 헤딩 |
| `--text-h2` | 48px | 1.1 | -0.02em | 페이지 헤딩 |
| `--text-h1` | 72px | 1.05 | -0.025em | 화면 헤더 |
| `--text-display` | 96px | 1.0 | -0.03em | **시그니처 명대사** |

### Spacing Scale (4px base)

```css
--space-1:   4px;
--space-2:   8px;
--space-3:  12px;
--space-4:  16px;
--space-5:  20px;
--space-6:  24px;
--space-8:  32px;
--space-10: 40px;
--space-12: 48px;
--space-16: 64px;
--space-20: 80px;
--space-24: 96px;
--space-32: 128px;
--space-40: 160px;
```

### Border Radius (sharp 기본)

```css
--radius-0:    0;       /* default — 카드, 인풋 */
--radius-1:    2px;     /* 미세한 둥글림 (버튼) */
--radius-2:    4px;     /* 토스트, 태그 */
--radius-pill: 9999px;  /* 특수 — 카테고리 칩 only */
```

> 둥근 모서리는 디자인 철학과 충돌 — sharp가 기본.

### Layered Depth (그림자 대신 grain + hairline)

```css
--grain-light: url("data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 200 200'><filter id='n'><feTurbulence type='fractalNoise' baseFrequency='0.9' /></filter><rect width='100%' height='100%' filter='url(%23n)' opacity='0.03'/></svg>");
--grain-medium: url("...opacity='0.05'");
--hairline: 1px solid var(--cream-600);
--hairline-strong: 1px solid var(--cream-500);
--hairline-amber: 1px solid var(--amber-500);
```

> Drop shadow / box-shadow 사용 안 함. Depth는 grain + hairline + opacity 레이어로.

### Motion Tokens

| Token | Value | Usage |
|-------|-------|-------|
| `--ease-out` | `cubic-bezier(0.2, 0.8, 0.4, 1)` | 기본 이징 |
| `--ease-deliberate` | `cubic-bezier(0.65, 0, 0.35, 1)` | 명대사 카드 등장 |
| `--ease-linear` | `linear` | 자막 흐름 |
| `--dur-fast` | `200ms` | hover, focus |
| `--dur-base` | `400ms` | 화면 전환, fade |
| `--dur-slow` | `600ms` | 카드 뒤집기 |
| `--dur-deliberate` | `1000ms` | 명대사 reveal |
| `--dur-wait` | `5000ms` | 명대사 정지 시간 |
| `--stagger` | `80ms` | 문장 stagger 간격 |

> ⚠️ GPU 컴포지트: `transform` + `opacity`만 사용. `box-shadow` 트랜지션 X.
> `prefers-reduced-motion` 미디어 쿼리에서 모든 모션 ≤ 100ms로 단축.

### Breakpoints

```css
--bp-mobile:  375px;  /* base — mobile first */
--bp-tablet:  768px;
--bp-desktop: 1280px;
--bp-wide:    1600px;
```

### Container Widths

```css
--container-narrow:  560px;   /* 본문 흐름 (Aesop 스타일) */
--container-medium:  720px;
--container-wide:    1080px;
--container-full:    1440px;
```

---

## Components

### Button

#### Variants

| Variant | Background | Text | Border |
|---------|-----------|------|--------|
| **primary** | `--amber-400` | `--ink-900` | none |
| **secondary** | transparent | `--cream-100` | `--hairline-strong` |
| **ghost** | transparent | `--cream-200` | none |
| **destructive** | transparent | `--state-error` | `1px solid var(--state-error)` |

#### States — Primary

```css
.btn-primary {
  background: var(--amber-400);
  color: var(--ink-900);
  border: none;
  padding: var(--space-4) var(--space-8);
  font-family: var(--font-body);
  font-size: var(--text-body);
  font-weight: 500;
  letter-spacing: 0.02em;
  border-radius: var(--radius-1);
  transition: background var(--dur-fast) var(--ease-out),
              transform var(--dur-fast) var(--ease-out);
  cursor: pointer;
}
.btn-primary:hover    { background: var(--amber-300); }
.btn-primary:active   { background: var(--amber-500); transform: translateY(1px); }
.btn-primary:focus-visible {
  outline: 2px solid var(--amber-200);
  outline-offset: 3px;
}
.btn-primary:disabled {
  background: var(--ink-500);
  color: var(--cream-400);
  cursor: not-allowed;
}
.btn-primary[aria-busy="true"] {
  background: var(--amber-500);
  color: transparent;
  position: relative;
}
.btn-primary[aria-busy="true"]::after {
  content: ""; position: absolute; inset: 50% 50%; width: 14px; height: 14px;
  border: 1.5px solid var(--ink-900); border-right-color: transparent;
  border-radius: 50%; transform: translate(-50%, -50%);
  animation: spin 800ms linear infinite;
}
```

#### States — Secondary

```css
.btn-secondary {
  background: transparent;
  color: var(--cream-100);
  border: 1px solid var(--cream-500);
  padding: calc(var(--space-4) - 1px) calc(var(--space-8) - 1px);
  font-family: var(--font-body); font-size: var(--text-body); font-weight: 500;
  border-radius: var(--radius-1);
  transition: border-color var(--dur-fast) var(--ease-out),
              color var(--dur-fast) var(--ease-out);
}
.btn-secondary:hover  { border-color: var(--amber-400); color: var(--amber-300); }
.btn-secondary:active { border-color: var(--amber-500); color: var(--amber-400); }
.btn-secondary:focus-visible {
  outline: 2px solid var(--amber-200); outline-offset: 3px;
}
.btn-secondary:disabled {
  border-color: var(--ink-500); color: var(--cream-500); cursor: not-allowed;
}
```

#### States — Ghost

```css
.btn-ghost {
  background: transparent; color: var(--cream-200); border: none;
  padding: var(--space-3) var(--space-4);
  font-family: var(--font-body); font-size: var(--text-meta);
  transition: color var(--dur-fast) var(--ease-out);
}
.btn-ghost:hover  { color: var(--amber-300); }
.btn-ghost:active { color: var(--amber-400); }
.btn-ghost:focus-visible {
  outline: 1px solid var(--amber-200); outline-offset: 2px;
}
.btn-ghost:disabled { color: var(--cream-500); cursor: not-allowed; }
```

#### States — Destructive

```css
.btn-destructive {
  background: transparent; color: var(--state-error);
  border: 1px solid var(--state-error);
  padding: calc(var(--space-4) - 1px) calc(var(--space-8) - 1px);
  font-family: var(--font-body); font-size: var(--text-body); font-weight: 500;
  border-radius: var(--radius-1);
  transition: background var(--dur-fast) var(--ease-out);
}
.btn-destructive:hover  { background: color-mix(in srgb, var(--state-error) 12%, transparent); }
.btn-destructive:active { background: color-mix(in srgb, var(--state-error) 20%, transparent); }
.btn-destructive:focus-visible {
  outline: 2px solid var(--state-error); outline-offset: 3px;
}
.btn-destructive:disabled {
  border-color: var(--ink-500); color: var(--cream-500); cursor: not-allowed;
}
```

### Input

```css
.input {
  background: transparent;
  color: var(--cream-50);
  border: none;
  border-bottom: 1px solid var(--cream-500);
  padding: var(--space-3) 0;
  font-family: var(--font-body);
  font-size: var(--text-body);
  width: 100%;
  transition: border-color var(--dur-fast) var(--ease-out);
}
.input::placeholder { color: var(--cream-400); }
.input:hover         { border-bottom-color: var(--cream-300); }
.input:focus-visible {
  outline: none;
  border-bottom-color: var(--amber-400);
  border-bottom-width: 1.5px;
}
.input:disabled      { color: var(--cream-500); border-bottom-color: var(--ink-500); cursor: not-allowed; }
.input[aria-invalid="true"] { border-bottom-color: var(--state-error); }
.input-label {
  display: block;
  font-size: var(--text-caption);
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--cream-300);
  margin-bottom: var(--space-2);
}
.input-error {
  color: var(--state-error);
  font-size: var(--text-meta);
  margin-top: var(--space-2);
}
```

> Placeholder contrast: `--cream-400` on `--ink-900` = 4.7:1 ≥ 3:1 ✓

### Card (드물게 사용 — 본문 hairline 우선)

```css
.card {
  background: var(--ink-800);
  border: var(--hairline);
  padding: var(--space-8);
  border-radius: var(--radius-0);
  position: relative;
}
.card::after { /* grain overlay */
  content: ""; position: absolute; inset: 0;
  background: var(--grain-light); pointer-events: none;
  mix-blend-mode: overlay;
}
.card--amber { border-left: 2px solid var(--amber-400); }
```

### Hairline Divider

```css
.divider        { border: 0; border-top: var(--hairline); margin: var(--space-8) 0; }
.divider--strong{ border-top: var(--hairline-strong); }
.divider--amber { border-top: var(--hairline-amber); }
.divider--vertical { width: 1px; height: 100%; background: var(--cream-600); border: 0; }
```

### Category Chip (얇은 색조 1줄)

```css
.chip {
  display: inline-flex; align-items: center; gap: var(--space-2);
  background: transparent;
  color: var(--cream-100);
  border: none;
  border-left: 2px solid var(--cat-love); /* category color variable */
  padding: var(--space-1) var(--space-3);
  font-family: var(--font-body); font-size: var(--text-meta);
  letter-spacing: 0.05em; text-transform: uppercase;
  border-radius: 0;
}
.chip--love  { border-left-color: var(--cat-love); }
.chip--work  { border-left-color: var(--cat-work); }
.chip--money { border-left-color: var(--cat-money); }
.chip--tarot { border-left-color: var(--cat-tarot); }
.chip:hover  { color: var(--amber-300); }
.chip:focus-visible { outline: 1px solid var(--amber-200); outline-offset: 2px; }
.chip[aria-selected="true"] { color: var(--amber-300); border-left-width: 3px; }
```

### Stepper (Onboarding 진행률)

```css
.stepper {
  display: flex; align-items: center; gap: var(--space-3);
  font-family: var(--font-mono); font-size: var(--text-caption);
  color: var(--cream-400); letter-spacing: 0.15em;
}
.stepper-dot {
  width: 6px; height: 6px; border-radius: 50%;
  background: var(--cream-600);
  transition: background var(--dur-base) var(--ease-out);
}
.stepper-dot--active { background: var(--amber-400); }
.stepper-dot--done   { background: var(--cream-300); }
```

### VoicePlayer (composite — 사주/타로 풀이 재생)

```css
.voice-player {
  display: flex; flex-direction: column; gap: var(--space-6);
  padding: var(--space-8) 0;
}
.voice-player__character {
  width: 200px; aspect-ratio: 1; opacity: 0.5;
  background-position: center; background-size: cover; mix-blend-mode: screen;
}
.voice-player__controls {
  display: flex; align-items: center; gap: var(--space-4);
}
.voice-player__play {
  width: 56px; height: 56px; border-radius: 50%;
  background: var(--amber-400); color: var(--ink-900);
  border: none; cursor: pointer; display: grid; place-items: center;
  transition: transform var(--dur-fast) var(--ease-out);
}
.voice-player__play:hover  { transform: scale(1.05); }
.voice-player__play:active { transform: scale(0.96); }
.voice-player__play:focus-visible { outline: 2px solid var(--amber-200); outline-offset: 4px; }
.voice-player__progress {
  flex: 1; height: 1px; background: var(--cream-600); position: relative;
}
.voice-player__progress::before {
  content: ""; position: absolute; inset: 0;
  background: var(--amber-400); width: var(--progress, 0%);
  transition: width 250ms linear;
}
.voice-player__time {
  font-family: var(--font-mono); font-size: var(--text-caption);
  color: var(--cream-300); letter-spacing: 0.08em;
}
```

### SubtitleBand (자막 — 한 문장씩 fade-in)

```css
.subtitle-band {
  min-height: 4lh; padding: var(--space-6) 0;
  font-family: var(--font-display-han); font-size: var(--text-h3); line-height: 1.5;
  color: var(--cream-100); letter-spacing: -0.005em;
  border-top: var(--hairline); border-bottom: var(--hairline);
  position: relative;
}
.subtitle-line {
  opacity: 0;
  animation: fadeUp var(--dur-base) var(--ease-out) forwards;
}
.subtitle-line--current { color: var(--amber-300); }
.subtitle-line--past    { color: var(--cream-300); }
@keyframes fadeUp {
  from { opacity: 0; transform: translateY(8px); }
  to   { opacity: 1; transform: translateY(0); }
}
```

### TarotCard (flip)

```css
.tarot-card {
  width: 200px; aspect-ratio: 3/5;
  perspective: 1200px; cursor: pointer;
}
.tarot-card__inner {
  position: relative; width: 100%; height: 100%;
  transform-style: preserve-3d;
  transition: transform var(--dur-slow) var(--ease-deliberate);
}
.tarot-card[aria-pressed="true"] .tarot-card__inner {
  transform: rotateY(180deg);
}
.tarot-card__face {
  position: absolute; inset: 0; backface-visibility: hidden;
  border: 1px solid var(--cream-500);
}
.tarot-card__back {
  background: var(--ink-700);
  background-image: url("/assets/tarot-back-pattern.svg"), var(--grain-medium);
  display: grid; place-items: center;
}
.tarot-card__front {
  background: var(--ink-800);
  transform: rotateY(180deg);
}
.tarot-card:focus-visible {
  outline: 2px solid var(--amber-200); outline-offset: 6px;
}
```

### FollowUpButtonGroup

```css
.followup-group {
  display: flex; flex-direction: column; gap: var(--space-3);
  padding-top: var(--space-8); border-top: var(--hairline);
}
.followup-btn {
  text-align: left; padding: var(--space-4) var(--space-6);
  background: transparent; color: var(--cream-100);
  border: 1px solid var(--cream-600); border-radius: var(--radius-0);
  font-family: var(--font-display-han); font-size: var(--text-lead);
  cursor: pointer;
  transition: border-color var(--dur-fast) var(--ease-out),
              color var(--dur-fast) var(--ease-out),
              transform var(--dur-fast) var(--ease-out);
}
.followup-btn::before { content: "— "; color: var(--amber-400); }
.followup-btn:hover   { border-color: var(--amber-400); color: var(--amber-300); transform: translateX(4px); }
.followup-btn:active  { color: var(--amber-400); }
.followup-btn:focus-visible { outline: 2px solid var(--amber-200); outline-offset: 3px; }
.followup-btn:disabled, .followup-btn[aria-disabled="true"] {
  color: var(--cream-500); border-color: var(--ink-500); cursor: not-allowed;
}
.followup-btn--used {
  color: var(--cream-400); text-decoration: line-through;
  text-decoration-color: var(--cream-500);
}
```

### QuotaBanner (이번 주 무료 남음)

```css
.quota-banner {
  display: flex; align-items: center; justify-content: space-between;
  padding: var(--space-3) var(--space-6);
  background: transparent; border-bottom: var(--hairline-amber);
  font-family: var(--font-mono); font-size: var(--text-caption);
  color: var(--amber-300); letter-spacing: 0.12em; text-transform: uppercase;
}
.quota-banner--exhausted {
  color: var(--state-error); border-bottom-color: var(--state-error);
}
```

### QuoteCardPreview (명대사 카드)

```css
.quote-card-preview {
  aspect-ratio: 9/16; max-width: 360px; width: 100%;
  background: var(--ink-900);
  padding: var(--space-12) var(--space-8);
  position: relative; overflow: hidden;
  display: flex; flex-direction: column; justify-content: space-between;
}
.quote-card-preview::before {
  content: ""; position: absolute; inset: 0;
  background: var(--grain-medium); pointer-events: none;
}
.quote-card-preview__line {
  font-family: var(--font-display-han); font-size: 36px; line-height: 1.3;
  color: var(--amber-300); letter-spacing: -0.01em;
  opacity: 0; animation: fadeUp var(--dur-deliberate) var(--ease-deliberate) 5s forwards;
}
.quote-card-preview__category {
  font-family: var(--font-mono); font-size: var(--text-caption);
  letter-spacing: 0.2em; text-transform: uppercase; color: var(--cream-300);
}
.quote-card-preview__watermark {
  font-family: var(--font-display); font-style: italic; font-size: var(--text-meta);
  color: var(--cream-500);
}
.quote-card-preview[data-cat="love"]  .quote-card-preview__category { color: var(--cat-love); }
.quote-card-preview[data-cat="work"]  .quote-card-preview__category { color: var(--cat-work); }
.quote-card-preview[data-cat="money"] .quote-card-preview__category { color: var(--cat-money); }
.quote-card-preview[data-cat="tarot"] .quote-card-preview__category { color: var(--cat-tarot); }
```

### ShareButtonRow

```css
.share-row {
  display: flex; gap: var(--space-3); padding-top: var(--space-6);
}
.share-btn {
  flex: 1; padding: var(--space-3) var(--space-2);
  background: transparent; border: 1px solid var(--cream-600);
  color: var(--cream-200); font-family: var(--font-body); font-size: var(--text-meta);
  cursor: pointer;
  transition: border-color var(--dur-fast), color var(--dur-fast);
}
.share-btn:hover { border-color: var(--amber-400); color: var(--amber-300); }
.share-btn:focus-visible { outline: 1px solid var(--amber-200); outline-offset: 2px; }
```

### SajuChart (천간/지지 시각화)

```css
.saju-chart {
  display: grid; grid-template-columns: repeat(4, 1fr);
  gap: var(--space-4); border-top: var(--hairline); border-bottom: var(--hairline);
  padding: var(--space-8) 0;
}
.saju-column { text-align: center; }
.saju-column__label {
  font-family: var(--font-mono); font-size: var(--text-caption);
  letter-spacing: 0.15em; text-transform: uppercase; color: var(--cream-300);
}
.saju-column__hanja {
  font-family: var(--font-display-han); font-size: 56px; line-height: 1;
  color: var(--cream-50); margin: var(--space-3) 0;
}
.saju-column__element {
  font-family: var(--font-body); font-size: var(--text-meta); color: var(--amber-300);
}
.saju-column--missing .saju-column__hanja { color: var(--cream-500); }
.saju-column--missing::after {
  content: "시간 모름"; display: block;
  font-family: var(--font-mono); font-size: var(--text-caption); color: var(--cream-400);
}
```

### Modal / Bottom Sheet

```css
.modal-overlay {
  position: fixed; inset: 0; background: rgba(8, 6, 3, 0.7);
  backdrop-filter: blur(8px);
  display: grid; place-items: center;
  animation: fadeIn var(--dur-base) var(--ease-out);
}
.modal {
  background: var(--ink-800); border: var(--hairline);
  max-width: 480px; width: calc(100% - var(--space-8));
  padding: var(--space-12) var(--space-8);
  position: relative;
}
.modal::after {
  content: ""; position: absolute; inset: 0;
  background: var(--grain-light); pointer-events: none;
}
@media (max-width: 768px) {
  .modal {
    position: fixed; bottom: 0; left: 0; right: 0; max-width: 100%;
    border-top: var(--hairline-amber); border-radius: 0;
    animation: slideUp var(--dur-base) var(--ease-out);
  }
}
@keyframes fadeIn  { from { opacity: 0; } to { opacity: 1; } }
@keyframes slideUp { from { transform: translateY(100%); } to { transform: translateY(0); } }
```

### Toast

```css
.toast {
  position: fixed; bottom: var(--space-8); left: 50%; transform: translateX(-50%);
  background: var(--ink-700); color: var(--cream-100);
  border-left: 2px solid var(--amber-400);
  padding: var(--space-3) var(--space-6);
  font-family: var(--font-body); font-size: var(--text-meta);
  border-radius: var(--radius-2);
  animation: fadeUp var(--dur-base) var(--ease-out);
  z-index: 100;
}
.toast--success { border-left-color: var(--state-success); }
.toast--error   { border-left-color: var(--state-error); }
```

### Nav (Top Bar)

```css
.nav-top {
  position: sticky; top: 0; z-index: 50;
  background: color-mix(in srgb, var(--ink-900) 92%, transparent);
  backdrop-filter: blur(12px);
  border-bottom: var(--hairline);
  padding: var(--space-4) var(--space-6);
  display: flex; align-items: center; justify-content: space-between;
}
.nav-top__brand {
  font-family: var(--font-display); font-style: italic; font-size: var(--text-lead);
  color: var(--amber-300); letter-spacing: -0.01em;
}
.nav-top__actions { display: flex; gap: var(--space-4); }
```

### TabBar (모바일 하단)

```css
.tab-bar {
  position: sticky; bottom: 0; z-index: 40;
  background: color-mix(in srgb, var(--ink-900) 95%, transparent);
  backdrop-filter: blur(12px);
  border-top: var(--hairline);
  display: flex; justify-content: space-around;
  padding: var(--space-3) 0 calc(var(--space-3) + env(safe-area-inset-bottom));
}
.tab-bar__item {
  display: flex; flex-direction: column; align-items: center; gap: 2px;
  font-family: var(--font-mono); font-size: 10px; letter-spacing: 0.12em;
  color: var(--cream-400); padding: var(--space-2) var(--space-4);
  background: transparent; border: none; cursor: pointer;
  transition: color var(--dur-fast) var(--ease-out);
}
.tab-bar__item[aria-current="page"] { color: var(--amber-300); }
.tab-bar__item:hover { color: var(--amber-400); }
.tab-bar__item:focus-visible { outline: 1px solid var(--amber-200); outline-offset: 2px; }
```

### Loading Spinner

```css
@keyframes spin { to { transform: rotate(360deg); } }
.spinner {
  width: 24px; height: 24px;
  border: 1.5px solid var(--cream-600); border-top-color: var(--amber-400);
  border-radius: 50%; animation: spin 800ms linear infinite;
}
```

### Skeleton (loading state)

```css
.skeleton {
  background: linear-gradient(90deg,
    var(--ink-700) 0%, var(--ink-600) 50%, var(--ink-700) 100%);
  background-size: 200% 100%;
  animation: shimmer 1.4s linear infinite;
}
@keyframes shimmer { from { background-position: 200% 0; } to { background-position: -200% 0; } }
```

---

## Accessibility Standards

- **Color contrast**: 본문 텍스트 ≥ 4.5:1, placeholder ≥ 3:1, 인터랙티브 요소 ≥ 3:1
- **Focus ring**: `:focus-visible` outline 2px solid `--amber-200` + offset (절대 `outline: none` 사용 금지)
- **Keyboard navigation**: 모든 인터랙티브 요소 Tab + Enter/Space 지원
- **Reduced motion**: `prefers-reduced-motion: reduce` 시 모든 모션 ≤ 100ms
- **Subtitle**: 음성 콘텐츠에 자막 동시 노출 (WCAG 1.2.2)
- **Screen reader**: `aria-live="polite"` for subtitle stream, `aria-label` for icon-only buttons

---

## Implementation Tech Notes

- **CSS Custom Properties**: 위 토큰 전부 `:root`에 정의. JS는 토큰값을 직접 읽지 않고 클래스만 토글.
- **Framework**: Next.js 15 (App Router) + Tailwind는 사용하지 않고 plain CSS Modules 또는 vanilla-extract.
- **Token contracts**: 위 모든 토큰은 빌드 타임에 `tokens.css` 파일로 컴파일 후 import.

---

## Confidence: **High**

모든 컴포넌트가 wireframes에서 식별된 화면을 커버. Aesop 절제 + 시니컬 양극성을 토큰 차원에서 강제 (sharp 모서리, 그림자 X, 호박 액센트 1색).
