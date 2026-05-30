'use client';

/**
 * `<SajuChart>` — collapsible 명식 chart sidebar for `/reading/play`
 * (ISSUE-042).
 *
 * Renders the 4-pillar 사주 명식 table (시 / 일 / 월 / 년) with the
 * 천간 + 지지 + 오행 cells, and exposes each cell as a tappable button
 * that opens an inline tooltip showing the 오행 + 십신 label
 * (ux_spec Screen 9, AC3).
 *
 * Phase-1 scope (minimal placeholder — ISSUE-042):
 *  - The real chart engine (`voicesaju.saju.engine.compute_chart`) is
 *    M2 backend territory; the page-level shell on `/reading/play`
 *    passes a static placeholder chart object today and will swap in
 *    the live computation when ISSUE-040's `/me` envelope ships the
 *    persisted chart blob.
 *  - "시간 모름" (no birth hour) collapses the 시주 column to a "?"
 *    cell per copy_guide §7 row "명식 시간모름 표시".
 *  - On mobile (`md:` breakpoint), the chart collapses into a
 *    one-line summary + a tap-to-expand button. Desktop renders the
 *    full grid inline.
 *
 * The one-line summary copy follows ux_spec Screen 9 (`Right
 * collapsible sidebar`): `"무자년 갑오월 경신일 — [시주 or 모름]"`.
 *
 * Architecture refs:
 *   docs/ux_spec.md Screen 9 (chart sidebar contract)
 *   docs/copy_guide.md §7 (chart cell labels)
 */

import { useCallback, useMemo, useState, type ReactNode } from 'react';

/** One pillar of the 명식 — 시 / 일 / 월 / 년. */
export interface SajuPillar {
  /** Column key (used for stable React keys + aria labels). */
  key: 'hour' | 'day' | 'month' | 'year';
  /** 한국어 column label rendered in the header — "시", "일", "월", "년". */
  label: string;
  /** 천간 character (e.g. "갑"). May be `null` when 시간 모름. */
  heaven: string | null;
  /** 지지 character (e.g. "오"). May be `null` when 시간 모름. */
  earth: string | null;
  /** 오행 mapping — "목"/"화"/"토"/"금"/"수". May be `null` when 시간 모름. */
  element: '목' | '화' | '토' | '금' | '수' | null;
  /** 십신 label rendered in the tooltip. May be `null` when 시간 모름. */
  tenGod: string | null;
}

export interface SajuChartData {
  pillars: ReadonlyArray<SajuPillar>;
  /** One-line summary shown in the collapsed sidebar header. */
  summary: string;
  /** Whether the user's birth hour was unknown at onboarding. */
  hourUnknown: boolean;
}

export interface SajuChartProps {
  chart: SajuChartData;
  /**
   * When `true`, renders the mobile-style collapsible header even on
   * wider viewports. Used by the page shell to drive the layout from a
   * parent media-query if needed; defaults to `false` so the chart
   * shows inline on desktop.
   */
  forceCollapsible?: boolean;
}

const ELEMENT_COLORS: Record<NonNullable<SajuPillar['element']>, string> = {
  목: 'text-emerald-300',
  화: 'text-rose-300',
  토: 'text-amber-300',
  금: 'text-slate-200',
  수: 'text-sky-300',
};

/**
 * A static placeholder chart so the page renders something coherent
 * before the real /me envelope (ISSUE-040 ships the persisted chart).
 * Mirrors the architecture §8 example fixture
 * "무자년 갑오월 경신일 모름시".
 */
export const PLACEHOLDER_CHART: SajuChartData = {
  hourUnknown: true,
  summary: '무자년 갑오월 경신일 — 시간 모름',
  pillars: [
    { key: 'hour', label: '시', heaven: null, earth: null, element: null, tenGod: null },
    { key: 'day', label: '일', heaven: '경', earth: '신', element: '금', tenGod: '비견' },
    { key: 'month', label: '월', heaven: '갑', earth: '오', element: '화', tenGod: '정관' },
    { key: 'year', label: '년', heaven: '무', earth: '자', element: '수', tenGod: '편재' },
  ],
};

interface CellTooltipState {
  pillarKey: SajuPillar['key'];
}

export function SajuChart({ chart, forceCollapsible = false }: SajuChartProps): ReactNode {
  const [expanded, setExpanded] = useState(false);
  const [tooltip, setTooltip] = useState<CellTooltipState | null>(null);

  const handleCellTap = useCallback((pillarKey: SajuPillar['key']) => {
    setTooltip((prev) => (prev?.pillarKey === pillarKey ? null : { pillarKey }));
  }, []);

  const handleToggleExpand = useCallback(() => {
    setExpanded((prev) => !prev);
  }, []);

  const tooltipPillar = useMemo(
    () => (tooltip ? (chart.pillars.find((p) => p.key === tooltip.pillarKey) ?? null) : null),
    [tooltip, chart.pillars],
  );

  // Collapsible style: always render the summary header; the grid lives
  // inside a conditional block. On desktop we use Tailwind's responsive
  // utilities so the grid stays visible unless `forceCollapsible` is on.
  const gridVisibilityClass = forceCollapsible
    ? expanded
      ? 'block'
      : 'hidden'
    : expanded
      ? 'block'
      : 'hidden md:block';

  return (
    <aside
      aria-label="사주 명식"
      data-testid="saju-chart"
      className="flex w-full flex-col gap-s2 rounded-md border border-cream-700 bg-ink-800/60 p-s3 text-cream-100"
    >
      <div className="flex items-center justify-between gap-s2">
        <p className="font-body text-sm text-cream-200" data-testid="saju-chart-summary">
          {chart.summary}
        </p>
        <button
          type="button"
          onClick={handleToggleExpand}
          aria-expanded={expanded}
          aria-controls="saju-chart-grid"
          data-testid="saju-chart-toggle"
          className={`inline-flex items-center rounded-md border border-cream-600 px-s2 py-s1 font-body text-xs text-cream-200 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-amber-300 ${
            forceCollapsible ? '' : 'md:hidden'
          }`}
        >
          {expanded ? '접기' : '명식 보기'}
        </button>
      </div>

      <div id="saju-chart-grid" data-testid="saju-chart-grid" className={gridVisibilityClass}>
        <table className="w-full table-fixed border-collapse text-center font-body">
          <thead>
            <tr>
              {chart.pillars.map((pillar) => (
                <th
                  key={pillar.key}
                  scope="col"
                  className="border-b border-cream-700 pb-s1 text-xs text-cream-300"
                >
                  {pillar.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            <tr>
              {chart.pillars.map((pillar) => {
                const isHourUnknown = pillar.key === 'hour' && chart.hourUnknown;
                const tooltipId = `saju-tooltip-${pillar.key}`;
                const isOpen = tooltip?.pillarKey === pillar.key;
                const cellLabel = isHourUnknown
                  ? '시간 모름'
                  : `${pillar.label} 명식 — ${pillar.heaven}${pillar.earth}`;
                return (
                  <td key={pillar.key} className="relative px-s1 pt-s2">
                    <button
                      type="button"
                      onClick={() => handleCellTap(pillar.key)}
                      aria-label={cellLabel}
                      aria-describedby={isOpen ? tooltipId : undefined}
                      aria-expanded={isOpen}
                      data-testid={`saju-cell-${pillar.key}`}
                      className="flex w-full flex-col items-center gap-s1 rounded-md px-s1 py-s2 text-base text-cream-100 transition-colors hover:bg-ink-700/60 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-amber-300"
                    >
                      {isHourUnknown ? (
                        <span aria-hidden className="text-cream-400">
                          ?
                        </span>
                      ) : (
                        <>
                          <span className="text-lg">{pillar.heaven}</span>
                          <span className="text-lg">{pillar.earth}</span>
                          {pillar.element && (
                            <span
                              className={`text-[10px] ${ELEMENT_COLORS[pillar.element]}`}
                              aria-hidden
                            >
                              {pillar.element}
                            </span>
                          )}
                        </>
                      )}
                    </button>
                    {isOpen && tooltipPillar && (
                      <div
                        id={tooltipId}
                        role="tooltip"
                        data-testid={`saju-tooltip-${pillar.key}`}
                        className="absolute left-1/2 top-full z-10 mt-s1 -translate-x-1/2 whitespace-nowrap rounded-md border border-cream-700 bg-ink-900 px-s2 py-s1 text-xs text-cream-100 shadow-lg"
                      >
                        {tooltipPillar.element && tooltipPillar.tenGod ? (
                          <>
                            오행 {tooltipPillar.element} · 십신 {tooltipPillar.tenGod}
                          </>
                        ) : (
                          '시간 모름'
                        )}
                      </div>
                    )}
                  </td>
                );
              })}
            </tr>
          </tbody>
        </table>
        {chart.hourUnknown && (
          <p
            className="mt-s2 text-center font-body text-xs text-cream-400"
            data-testid="saju-chart-hour-unknown"
          >
            시간 모름
          </p>
        )}
      </div>
    </aside>
  );
}
