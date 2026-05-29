# STATUS — VoiceSaju

Last updated: 2026-05-28

## Current Milestone

**M1 — Foundation** (ISSUE-001 ~ ISSUE-027)

Sprint cadence: not yet active (use `/sprint plan M1` to begin).

## Roadmap Snapshot

| Milestone | Range | Issues | Goal |
|-----------|-------|--------|------|
| **M1 Foundation** | ISSUE-001 ~ 027 | 27 | Backend/Frontend skeleton, DB schema, KMS envelope, saju engine, design system, OAuth |
| **M2 Saju Reading Flow** | ISSUE-028 ~ 046 | 19 | Onboarding → intro paywall → SSE streaming reading → follow-ups → payment |
| **M3 Daily Tarot** | ISSUE-047 ~ 055 | 9 | Deterministic seed, quota service, tarot UI, KST refresh |
| **M4 Quote Card + Sharing** | ISSUE-056 ~ 062 | 7 | Quote extraction, server OG image, share/landing |
| **M5 My Page** | ISSUE-063 ~ 073 | 11 | History, billing, saju correction |
| **M6 Polish + Launch** | ISSUE-074 ~ 090 | 17 | Legal, observability, deploys, tone regression CI gate |
| **M2.5 v2 Design Refinement (Ink, Amber & 印)** | ISSUE-091 ~ 098 | 8 | v2 design tokens, vermilion seal, hanja monument, 5-card tarot spread + 3D flip, quote card v2 (9:16 + seal), nav variants, copy tone system, tilt + reveal utilities |
| **Mock Adapter Layer (Phase 1 PoC)** | ISSUE-099 ~ 102 | 4 | Protocol/Adapter pattern for Payment / Auth / LLM / TTS — unblocks full M1+M2 vertical slice with no external API keys |

## Issue Summary

- Total: **102**
- Priority — **P0: 63 / P1: 33 / P2: 6**
- UI track: **35** (frontend screens/components, incl. 8 v2 design issues)
- Manual setup (human action required): **2** (Fly.io backend deploy ISSUE-084, Vercel frontend deploy ISSUE-085 — both **deferred** to Phase 2)
- Deferred (Phase 2): **7** — ISSUE-005 (R2 bucket), ISSUE-025 (Kakao/Apple OAuth), ISSUE-035 (Anthropic key), ISSUE-036 (Supertone), ISSUE-043 (Toss merchant), ISSUE-084 (Fly.io), ISSUE-085 (Vercel)

## Mock Adapter Strategy (Phase 1 PoC)

Added 2026-05-28 — ISSUE-099..102 introduce a Protocol/Adapter pattern so the entire app runs end-to-end against local fixtures, no external API keys required.

- **ISSUE-099 — MockPaymentAdapter** (replaces Toss while ISSUE-043 deferred): fake checkout session + auto-fire success webhook after 3s. Also ships a `MockStorageAdapter` for local-fs asset storage (replaces R2 while ISSUE-005 deferred).
- **ISSUE-100 — MockAuthAdapter** (replaces Kakao/Apple while ISSUE-025 deferred): pre-seeded `test_user_001` + signed dev JWT, middleware-compatible.
- **ISSUE-101 — MockLLMAdapter** (replaces Anthropic while ISSUE-035 deferred): fixture-based saju (3 per love/work/money) + tarot (7 daily) responses streamed sentence-by-sentence at 100ms pacing.
- **ISSUE-102 — MockTTSAdapter** (replaces Supertone while ISSUE-036 deferred): 10 pre-baked 200ms silent MP3 chunks streamed at 200ms pacing (~2s total per request).

**Deferred items (Phase 2 only, NOT blocking Phase 1):**
- ISSUE-005 — Cloudflare R2 bucket → MockStorageAdapter (local-fs) covers Phase 1
- ISSUE-025 — Kakao OAuth + Apple Sign-In → MockAuthAdapter covers Phase 1
- ISSUE-035 — Anthropic API key → MockLLMAdapter covers Phase 1
- ISSUE-036 — Supertone TTS API → MockTTSAdapter covers Phase 1
- ISSUE-043 — Toss Payments merchant → MockPaymentAdapter covers Phase 1
- ISSUE-084 — Fly.io backend deploy → local docker compose covers Phase 1
- ISSUE-085 — Vercel frontend deploy → local `pnpm dev` covers Phase 1

ISSUE-004 (Postgres + Redis) was reclassified from manual to non-manual: ISSUE-001's docker-compose.yml deliverable now provides both containers locally; cloud provisioning is part of Phase 2 deploy work.

Dependency redirects applied:
- ISSUE-026 (Kakao+Apple OAuth backend routes) now depends on ISSUE-100 instead of ISSUE-025.
- ISSUE-032 (intro player) now depends on ISSUE-101 instead of ISSUE-035.
- ISSUE-044 (Toss checkout endpoint) now depends on ISSUE-099 instead of ISSUE-043.

### v2 Design Refinement Batch (M2.5) — added 2026-05-28
- ISSUE-091..098 (8 issues) decompose the v2 "Ink, Amber & 印" visual system across reading / tarot / quote card surfaces.
- Foundation: ISSUE-091 (tokens). ISSUE-092 (seal), ISSUE-093 (hanja monument + saju tile), and ISSUE-098 (tilt/reveal utilities) depend on 091.
- ISSUE-094 (5-card spread) depends on 091 + the M3 tarot UI (051). ISSUE-095 (quote card v2) depends on 058/060 + 092. ISSUE-096 (nav variants) depends on 091 + 022. ISSUE-097 (copy tone) depends on 091 + 092.
- All 8 issues are sized 0.5d–1.5d. New FRs FR-037..FR-044 in `docs/requirements.md`; new test flow `J` in `docs/test_plan.md` (TC-J-001..TC-J-052) including a determinism guard for FR-013 across FR-040.

## Next 3 Issues to Implement

1. **ISSUE-001** — Bootstrap backend service skeleton (FastAPI + uv, includes docker-compose for Postgres 16 + Redis 7) · P0 · 1d
2. **ISSUE-002** — Bootstrap Next.js 15 frontend skeleton · P0 · 1d
3. **ISSUE-003** — Configure GitHub Actions CI (lint + test + typecheck) · P0 · 0.5d

After ISSUE-001~003, land the four Mock adapters in parallel (ISSUE-099 Payment, ISSUE-100 Auth, ISSUE-101 LLM, ISSUE-102 TTS — all 0.5d, all P0, all depend only on ISSUE-001) to unblock the full M1/M2 vertical slice without external API keys. Then proceed with schema migrations (ISSUE-006..010) and the saju engine (ISSUE-011..012).

## Key Risks (from requirements.md §9)

1. **Tone guardrail regression** — LLM 매운맛 톤이 욕설/혐오로 빠지면 앱스토어 정책 위반. M1 ISSUE-024 (톤 evalset) + M6 ISSUE-090 (CI gate)로 완화.
2. **Supertone pricing unknown (DEP-01)** — 단건가 20% 비용 상한 검증 불가. 비즈니스 컨택 필요 (Open Question OQ-01).
3. **Toss WebView policy (A-04)** — 결제/인증/콘텐츠 정책 미확인. M2 ISSUE-046 시점에 정책 확인 완료 필수.
4. **Saju calculation determinism** — manseryeok 라이브러리 정확도 미검증. M1 ISSUE-019에서 50+ fixture 회귀 테스트.
5. **Streaming latency 3s/1.5s 예산 초과** — Claude+Supertone 청크 합성. M2 ISSUE-040 부하 테스트 필수.

## Pre-MVP Validation (Blocking Launch)

- [ ] 톤 검증 인터뷰 (20-30대 여성 5명, 30분) — `PRD.md §10`, `business_analysis.md §5.3`
  - 매운맛 > 정통 톤 선호 3/5 이상
  - 캡쳐 공유 의향 3/5 이상
  - 단건 4,900원 결제 의향 3/5 이상

## Open Questions (출시 전 확정 — PRD §11)

- [ ] Supertone 비즈니스 컨택 (가격 / 티어 / API 한도)
- [ ] 토스 인앱 결제·인증·콘텐츠 정책 공식 확인
- [ ] 만세력 라이브러리 정확도 검증 (manseryeok 50 case)
- [ ] LLM 톤 샘플 5개로 Sonnet 4.6 / Haiku 4.5 비교 테스트
- [ ] 사주 단건 / 구독 가격 최종 결정 (A/B)
- [ ] 캐릭터 일러스트 IP 발주 (시니컬 누님 + 노인 도사)
- [ ] 22장 메이저 아르카나 일러스트 발주
- [ ] 카테고리별 인트로 멘트 5~10개 사전 녹음

## Sprint Activation

When ready to start: run `/sprint plan M1` to begin foundation milestone.

## Document Index

- `PRD.md` — 제품 요구사항 명세
- `docs/prd_digest.md` — 1페이지 요약
- `docs/requirements.md` — 분석된 요구사항 (US/FR/NFR)
- `docs/ux_spec.md` — UX 명세 (26 screens, 9 flows)
- `docs/architecture.md` — 아키텍처 (Next.js + FastAPI 모듈러 모놀리스)
- `docs/data_model.md` — 데이터 모델 (21 tables, 54 access patterns)
- `docs/test_plan.md` — 테스트 계획 (~120 cases, 9 flows)
- `docs/brainstorm_notes.md` — 초기 의사결정 히스토리
- `docs/business_analysis.md` — 시장/경쟁/페르소나/리스크
- `issues.md` — 구현 이슈 (102개; 95 active + 7 deferred to Phase 2)
