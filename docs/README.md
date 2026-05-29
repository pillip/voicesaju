# VoiceSaju

> 20-30대를 위한 대화형 음성 사주·타로 풀이 서비스. 매운맛 톤 + Supertone 캐릭터 보이스.

## Prerequisites

| 항목 | 버전 |
|------|------|
| Python | 3.11+ |
| Node.js | 20 LTS |
| `uv` | latest (https://docs.astral.sh/uv/) |
| PostgreSQL | 16 |
| Redis | 7 |

### 외부 계정 (사전 발급 필요)

- **Anthropic API key** — Claude Haiku 4.5 + Sonnet 4.6
- **Supertone API key** — TTS (business@supertone.ai 컨택 후 발급)
- **Cloudflare R2** — 오디오 청크 객체 저장
- **토스페이먼츠** — 결제 (단건 + 구독)
- **Kakao / Apple Developer** — 소셜 로그인
- **Vercel / Fly.io** — 호스팅

## Setup

### 1. Clone & Install

```bash
git clone <repo>
cd voicesaju

# Backend (FastAPI)
cd api
uv sync

# Frontend (Next.js)
cd ../web
pnpm install
```

### 2. Environment

```bash
# api/.env.local
DATABASE_URL=postgresql://...
REDIS_URL=redis://localhost:6379
ANTHROPIC_API_KEY=sk-ant-...
SUPERTONE_API_KEY=...
R2_ACCESS_KEY_ID=...
R2_SECRET_ACCESS_KEY=...
KMS_KEY_ID=...
TOSS_SECRET_KEY=...

# web/.env.local
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
NEXT_PUBLIC_TOSS_CLIENT_KEY=...
KAKAO_CLIENT_SECRET=...
APPLE_PRIVATE_KEY=...
```

> **보안**: `.env.local` 파일은 절대 커밋 금지. CI/배포 환경에서는 시크릿 매니저 사용.

### 3. Database Migration

```bash
cd api
uv run alembic upgrade head
uv run python -m voicesaju.seeds  # 22 major arcana + character voices + tone evalset
```

## Run

### Backend (FastAPI on :8000)

```bash
cd api
uv run uvicorn voicesaju.main:app --reload
```

### Frontend (Next.js on :3000)

```bash
cd web
pnpm dev
```

브라우저: http://localhost:3000

### Toss WebView 미리보기

```bash
cd web
pnpm dev:toss  # User-Agent 시뮬레이션 모드
```

## Test

### Backend

```bash
cd api
uv run pytest -q                              # 전체
uv run pytest tests/unit -q                   # 유닛만
uv run pytest tests/integration -q -m "not external"  # 외부 API mock
uv run pytest --cov=voicesaju --cov-report=term-missing
```

### Frontend

```bash
cd web
pnpm test          # Vitest 유닛
pnpm test:e2e      # Playwright E2E (Chromium + Mobile Safari)
pnpm test:visual   # Visual regression
```

### 사주 결정성 회귀 (반드시 PR 전 통과)

```bash
cd api
uv run pytest tests/regression/test_saju_determinism.py -q
```

### 톤 가드레일 평가셋

```bash
cd api
uv run pytest tests/regression/test_tone_eval.py -q
```

## Project Structure

```
voicesaju/
├── PRD.md                    # 제품 요구사항
├── STATUS.md                 # 현재 진행 상황 + 다음 액션
├── issues.md                 # 90개 구현 이슈
├── docs/
│   ├── prd_digest.md         # 1페이지 PRD 요약
│   ├── requirements.md       # US / FR / NFR
│   ├── ux_spec.md            # 26 screens, 9 flows
│   ├── architecture.md       # Next.js + FastAPI
│   ├── data_model.md         # 21 tables
│   ├── test_plan.md          # ~120 cases
│   ├── brainstorm_notes.md   # 의사결정 히스토리
│   └── business_analysis.md  # 시장/페르소나/리스크
├── api/                      # FastAPI 백엔드 (uv)
│   ├── voicesaju/
│   └── tests/
└── web/                      # Next.js 15 (App Router, TS)
    ├── app/
    ├── components/
    └── lib/
```

## Workflow

1. **이슈 확인** — `STATUS.md` 의 "Next 3 Issues to Implement"
2. **구현 시작** — `/implement ISSUE-001` (Claude Code 스킬)
3. **테스트 통과** — `uv run pytest` + `pnpm test`
4. **리뷰** — `/review` 후 머지
5. **상태 업데이트** — `STATUS.md` + `issues.md` 자동 갱신

## Key Constraints

- 풀이 1회 응답 3초 이내, TTS 첫 청크 1.5초 이내 (NFR-001/002)
- 풀이 1회당 LLM+TTS 비용 ≤ 단건가의 20%
- 생년월일/시각은 AES-256-GCM 봉투 암호화
- 모든 LLM 응답은 톤 평가셋 (≥50 case) 회귀 통과 필수
- 사주 명식 계산은 결정적 (50+ fixture × 3회 반복 = byte-identical)

## License

TBD
