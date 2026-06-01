/**
 * ISSUE-093 — /preview/hanja-saju
 *
 * Visual verification surface for `<HanjaMonument>`, `<SajuChartTile>`,
 * and `<SajuChartGrid>`. Mounts outside production routes so designers
 * can verify the v2 monumental display + 4-pillar chart without
 * traversing onboarding.
 */
import { HanjaMonument } from '@/components/hanja';
import { SajuChartGrid, SajuChartTile } from '@/components/saju';

// Inline copy of HANJA_MONUMENT_CHAR_SET — Next.js prerender doesn't
// tolerate the `as const` readonly tuple being iterated at module-eval
// time during the server build. Source-of-truth lives in HanjaMonument.tsx;
// the unit test asserts byte-equality.
const PREVIEW_CHAR_SET: readonly string[] = [
  '命',
  '生',
  '時',
  '性',
  '戀',
  '業',
  '財',
  '月',
  '我',
  '門',
];

import '@/styles/tokens.css';
import '@/styles/utilities.css';

export default function HanjaSajuPreviewPage() {
  return (
    <main
      style={{
        minHeight: '100vh',
        backgroundColor: 'var(--hanji-800)',
        backgroundImage: 'var(--grain-strong)',
        color: 'var(--baekrim-200)',
        fontFamily: 'var(--font-mincho)',
        padding: '48px 24px',
      }}
    >
      <header style={{ marginBottom: '48px' }}>
        <h1
          style={{
            fontFamily: 'var(--font-brush)',
            fontSize: '48px',
            marginBottom: '8px',
          }}
        >
          命 · Hanja + Saju preview
        </h1>
        <p style={{ opacity: 0.7, maxWidth: '60ch' }}>
          ISSUE-093 / FR-039. Monumental hanja display + 4-pillar 명식 tile grid.
        </p>
      </header>

      <section aria-labelledby="hanja-mono" style={{ marginBottom: '64px' }}>
        <h2 id="hanja-mono" style={{ marginBottom: '16px', fontSize: '20px' }}>
          HanjaMonument · single hero character (clamp 120-240px)
        </h2>
        <div style={{ marginBottom: '24px' }}>
          <HanjaMonument char="命" aria-label="당신의 명운" />
        </div>
        <h3 style={{ marginBottom: '12px', fontSize: '16px', opacity: 0.7 }}>
          Documented character set (FR-039 AC4)
        </h3>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '32px', alignItems: 'flex-end' }}>
          {PREVIEW_CHAR_SET.map((char) => (
            <div key={char} style={{ textAlign: 'center', fontSize: '12px', opacity: 0.6 }}>
              <span
                style={{
                  display: 'inline-block',
                  fontFamily: 'var(--font-mincho)',
                  fontWeight: 900,
                  fontSize: '60px',
                  lineHeight: 1,
                  color: 'var(--baekrim-200)',
                }}
                aria-hidden
              >
                {char}
              </span>
              <div style={{ marginTop: '6px' }}>{char}</div>
            </div>
          ))}
        </div>
      </section>

      <section aria-labelledby="saju-grid" style={{ marginBottom: '48px' }}>
        <h2 id="saju-grid" style={{ marginBottom: '16px', fontSize: '20px' }}>
          SajuChartGrid + Tiles · 4-pillar 명식 (시 / 일 / 월 / 년)
        </h2>
        <p style={{ marginBottom: '16px', opacity: 0.6, fontSize: '14px' }}>
          시주 is missing (모름 overlay). Tab into a tile and press Enter to see the 오행 + 십신
          tooltip.
        </p>
        <SajuChartGrid>
          <SajuChartTile pillar="hour" missing />
          <SajuChartTile
            pillar="day"
            hanja="경신"
            heaven="경"
            earth="신"
            element="금"
            tenGod="비견"
          />
          <SajuChartTile
            pillar="month"
            hanja="갑오"
            heaven="갑"
            earth="오"
            element="화"
            tenGod="정관"
          />
          <SajuChartTile
            pillar="year"
            hanja="무자"
            heaven="무"
            earth="자"
            element="수"
            tenGod="편재"
          />
        </SajuChartGrid>
      </section>
    </main>
  );
}
