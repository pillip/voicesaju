# Design Philosophy — Ink & Amber (v2 · with 印 Vermilion)

> v1 후 자가비판: Aesop의 *형식*(좌측정렬·hairline·미니멀)만 가져와 AI slop이 됐다.
> v2는 **명리원의 밀도** + **잡지의 침범** + **uncanny ambiguity**로 다시 잡는다.

---

## Named Aesthetic
**Ink, Amber & 印** — 잉크, 호박, 그리고 도장.

세 요소가 서비스의 정체성을 떠받친다.

- **잉크(墨)**: 명리(命理)의 한국적 정체성. 검정이 아니라 *먹*. 한자를 *주연*으로 박는다.
- **호박(琥珀)**: Aesop의 절제된 따뜻함, 위스키 한 잔, 시니컬 누님의 미세한 빛.
- **도장(印)**: 명리원 우측 하단의 붉은 인주. **모든 풀이 결과의 시그니처** — 한 줄 풀이 옆에 도장이 찍히면 끝.

---

## How It Manifests — 핵심 7가지

### 1. 한자는 *장식*이 아니라 *주연*
- v1 실수: 천간/지지 한자를 8-10px로 흘려 풍수의 *흔적*. → 가짜 동양 디테일.
- v2: 한자를 **160~240px**로 박는다. 풀이 텍스트는 한자 옆을 흐른다.
- 명리원이 벽에 만세력을 *건다*. 우리는 화면이 곧 만세력이다.

### 2. 인주 도장(印) = 시그니처
- 새로운 핵심 컬러 **인주 적색** (`#9B2A1A`) — 호박 단독에서 벗어남.
- 풀이 결과·명대사 카드·로그인 후 토큰에 *반드시* 정사각 도장이 찍힌다 (24~40px).
- 도장 안에는 한자 1자 (`命`/`明`/`星`/`水`/`火` 등 — 카테고리/콘텐츠별).
- 도장은 *완벽한 정사각* 아닌 *살짝 기울어짐* (-1.5deg, uncanny).

### 3. 베이스를 *순흑* 에서 *한지 어둠* 으로
- v1: `#0F0B08` 깊은 잉크 차콜 — 디지털 검정.
- v2: `#1A1208` **한지 어둠** — 누런 갈색이 살짝 도는 어둠. 한약방 천장 같은.
- 그레인 텍스처: opacity 0.05 → **0.08** + 색조를 따뜻한 갈색으로.
- 페이지 *가장자리*는 더 검게 (vignette) — *동굴 같은 깊이*.

### 4. 잡지의 밀도 — Apartamento의 단단함
- 본문은 *덜 미니멀하게*. 풀이 한 문장만 띄우지 말고 **2-3 문장 묶음**으로.
- Aesop의 좌측 정렬만 흉내내지 말고, 잡지처럼 **헤드라인이 화면 가장자리에서 잘려나감**.
- 컬럼화: 좌측 한자 monumental + 우측 dense 본문 (잡지 펼침면).

### 5. 카피의 *술 취한 횡설수설*
- v1: "흠. 이 시간에 사주를 본다고?" — 너무 단정한 한 단어.
- v2: 누님이 *반쯤 취해 횡설수설*: *"...아니 진짜 이 시간에. 너 잠 안 와? 술도 안 마셨어? 사주 보러 왔구나. 어디 봐봐."*
- 마침표 사라짐, 줄임표 자주.

### 6. Uncanny Ambiguity — Toiletpaper의 *기억 박힘*
- 모든 카드가 *정확히 수평/수직*이면 AI slop. 카드를 -1.5deg 기울이기.
- 한자가 화면 가장자리에서 *의도적으로 잘림* (overflow hidden).
- ✦ 같은 깔끔 심볼 폐기, **인주 도장 + 흐트러진 손글씨**로 대체.

### 7. 화면별 *다른 공간 정체성*
- v1: 모든 화면이 동일 nav-top + hairline divider — *형식 반복 slop*.
- v2:
  - landing: nav 없음, 풀스크린 침묵
  - category: nav가 좌측 세로축
  - reading: nav가 아래로 내려옴 (몰입형)
  - tarot: 카드가 화면 중앙, nav 가장자리에만
- 각 화면이 *공간 자체로 메시지*.

---

## What Makes It Unforgettable

**한자가 화면을 차지하고, 그 옆에 누님의 횡설수설이 흐르고, 우측 하단에 붉은 인주 도장이 찍히는 그 순간.**

다른 사주 앱이 *결과를 빨리, 균일하게* 보여주는 동안, 우리는 **한자 한 글자**로 화면을 채우고, 도장 하나로 끝낸다. *마치 명리원에서 풀이 받고 종이를 받아드는 느낌* — 화면을 닫고 나서도 잊을 수 없는 것: **붉은 도장의 무게**.

---

## Reference Anchors (v2)

### Adopt
1. **Apartamento의 시스템 단단함** — 폰트 시스템을 *흔들지 않는 18년의 일관성*.
2. **Apartamento의 잡지 밀도** — 좌측 사진/한자 + 우측 dense 본문 인터뷰 구성.
3. **Toiletpaper의 uncanny ambiguity** — 살짝 기울임, 가장자리 잘림, *예쁨을 거부*.
4. **명리원의 한자 monumental + 인주 도장** — *주연이 한자*.
5. **노포의 따뜻한 백열 + 동굴 같은 깊이** — vignette + 그레인 강화.
6. **Aesop의 절제된 톤** — *분위기*만 차용, *형식*은 버림.

### Avoid (v1 잘못 학습한 것)
1. **모든 화면 동일 nav-top + hairline divider** — *형식 반복 slop*.
2. **한 단어 헤드라인 + 깔끔 ✦** — LLM의 "절제" 오해.
3. **8px 한자 흘리기** — 가짜 동양 디테일.
4. **amber 단일 액센트** — 시스템이 서비스 정체성을 모름.
5. **균일 수평/수직** — uncanny 없음.
6. **카드 박스 + drop shadow X 라며 hairline만 반복** — 단조로움.

---

## Decision Matrix (v2)

| 결정 | 선택 | 거부된 대안 | 이유 |
|------|------|------------|------|
| **컬러 시그니처** | 한지 어둠 + 호박 + **인주 적색 + 한지 갈색** 4축 | amber 단일 / 사이버 고스 / 파스텔 | 인주 도장이 *시그니처 모먼트* |
| **한자 처리** | 160~240px monumental | 8-10px 장식 / 한자 미사용 | 명리원처럼 *주연* |
| **레이아웃 일관성** | 화면별 *다른 nav/공간 구성* | 모든 화면 동일 nav-top | 형식 반복 slop 회피 |
| **카피 톤** | 횡설수설 2-3 문장 | 단정한 한 단어 | 술 취한 누님의 진짜 톤 |
| **카드 정렬** | **-1.5deg 기울어짐** | 수평/수직 균일 | Toiletpaper의 uncanny |
| **시그니처 모티프** | 인주 도장 (印 SVG) | ✦ amber dot | 한국적 + uncanny |
| **베이스 컬러** | 한지 어둠 `#1A1208` | 순흑 / OLED 검정 | 따뜻한 갈색 어둠 |
| **그레인** | 0.08 opacity, 갈색 톤 | 0.03 회색 | 종이 질감 강화 |
| **본문 밀도** | 잡지 펼침면 (좌측 한자 + 우측 dense 본문) | 미니멀 한 문장 | Apartamento 밀도 |
| **추가 폰트** | 손글씨 (Nanum Brush Script) + 명조 (Noto Serif KR) | EB Garamond + Pretendard만 | 가격표·라벨에 인간미 |

---

## Sources (Re-reference)

- [Apartamento Magazine — Fonts In Use](https://fontsinuse.com/uses/6839/apartamento-magazine-2008) — 18년 시스템 단단함, 잡지 밀도
- [Toiletpaper Magazine — Wikipedia](https://en.wikipedia.org/wiki/Toiletpaper_(magazine)) — uncanny ambiguity, *Toiletpaper enough?*
- [Aesop Logo & Typography — Fonts In Use](https://fontsinuse.com/uses/20234/aesop-logo-website-and-packaging) — 톤은 차용, 형식은 버림

## Confidence: **High** — but with check needed
v2가 진짜 Ink & Amber인지 검증할 한 가지: 톤 검증 인터뷰(`PRD §10`)에 *시각 prototype 1-2장*도 같이 보여주고 "이게 사주 앱처럼 느껴지나? 너무 무거운가?" 확인 필요. *어두운 한지 + 한자 monumental*이 20-30대 여성에게 *무거움/위압감*으로 느껴지지 않는지가 핵심 검증 포인트.
