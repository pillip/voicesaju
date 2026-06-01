'use client';

/**
 * `<SajuChartTile>` — v2 display primitive for one 4-pillar 명식 cell
 * (FR-039 / ISSUE-093).
 *
 * This is the v2 visual identity tile — hanja-first, monumental, with a
 * dedicated "모름" overlay for unknown pillars (per FR-002). It is a
 * pure presentational primitive: no tap-to-tooltip behaviour, no
 * 사주 engine integration. The existing interactive `<SajuChart>`
 * (ISSUE-042) stays the production chart for `/reading/play` until
 * ISSUE-097 wires the v2 tile into it; the two coexist during M2.5.
 *
 * Token + spec source: docs/design_system.md §SajuChart + FR-039.
 *
 * AC2: `<SajuChartTile pillar="hour" missing>` renders the "모름"
 * overlay (vermilion-300 stroke, rotate(-1.5deg)) AND sets aria-label
 * to include "모름" so AT users hear it.
 *
 * AC5: tile is focusable; pressing Enter/Space reveals an inline
 * tooltip showing 오행 + 십신 (the same payload as v1 SajuChart, but in
 * a presentational, controlled-via-internal-state form).
 */

import {
  useCallback,
  useId,
  useState,
  type CSSProperties,
  type KeyboardEvent,
  type ReactNode,
} from 'react';

export type SajuPillarKey = 'hour' | 'day' | 'month' | 'year';
export type SajuElement = '목' | '화' | '토' | '금' | '수';

export const SAJU_PILLAR_LABEL: Record<SajuPillarKey, string> = {
  hour: '시주',
  day: '일주',
  month: '월주',
  year: '년주',
};

export const SAJU_ELEMENT_HANGUL: Record<SajuElement, string> = {
  목: '목',
  화: '화',
  토: '토',
  금: '금',
  수: '수',
};

export interface SajuChartTileProps {
  /** Which of the 4 pillars this tile renders. */
  pillar: SajuPillarKey;
  /** Hanja string — typically 천간 + 지지 (e.g. "무자"). */
  hanja?: string;
  /** 오행 mapping for the pillar. Omitted when `missing` is true. */
  element?: SajuElement;
  /** 십신 label shown in the tooltip. Omitted when `missing` is true. */
  tenGod?: string;
  /**
   * Heaven stem alone, for aria-label assembly. Optional — when both
   * `heaven` and `earth` are passed, the aria-label uses them; otherwise
   * it falls back to `hanja`.
   */
  heaven?: string;
  /** Earth branch alone. See `heaven`. */
  earth?: string;
  /** `true` → unknown pillar (e.g. 시간 모름) — shows "모름" overlay. */
  missing?: boolean;
}

const ELEMENT_COLORS: Record<SajuElement, string> = {
  목: 'var(--baekrim-200)',
  화: 'var(--vermilion-300)',
  토: 'var(--baekrim-200)',
  금: 'var(--baekrim-200)',
  수: 'var(--baekrim-200)',
};

const ELEMENT_READING: Record<SajuElement, string> = {
  목: '목 (나무)',
  화: '화 (불)',
  토: '토 (흙)',
  금: '금 (쇠)',
  수: '수 (물)',
};

/**
 * Builds the SR aria-label per the FR-039 example:
 *   "년주 천간 무자, 오행 수"
 * Missing pillars yield "시주 모름".
 */
function buildAriaLabel(args: {
  pillar: SajuPillarKey;
  hanja?: string;
  heaven?: string;
  earth?: string;
  element?: SajuElement;
  missing?: boolean;
}): string {
  const pillarName = SAJU_PILLAR_LABEL[args.pillar];
  if (args.missing) {
    return `${pillarName} 모름`;
  }
  const stem = args.heaven && args.earth ? `${args.heaven}${args.earth}` : (args.hanja ?? '');
  const element = args.element ? `, 오행 ${SAJU_ELEMENT_HANGUL[args.element]}` : '';
  return `${pillarName} 천간 ${stem}${element}`;
}

export function SajuChartTile(props: SajuChartTileProps): ReactNode {
  const { pillar, hanja, element, tenGod, heaven, earth, missing = false } = props;
  const [tooltipOpen, setTooltipOpen] = useState(false);
  const tooltipId = useId();

  const ariaLabel = buildAriaLabel({ pillar, hanja, heaven, earth, element, missing });

  const handleKeyDown = useCallback((e: KeyboardEvent<HTMLDivElement>) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      setTooltipOpen((prev) => !prev);
    } else if (e.key === 'Escape') {
      setTooltipOpen(false);
    }
  }, []);

  const handleClick = useCallback(() => {
    setTooltipOpen((prev) => !prev);
  }, []);

  const tileStyle: CSSProperties = {
    position: 'relative',
    textAlign: 'center',
    padding: '24px 8px',
    borderTop: '1px solid var(--hanji-300)',
    borderBottom: '1px solid var(--hanji-300)',
    color: 'var(--baekrim-200)',
    fontFamily: 'var(--font-mincho)',
    cursor: missing ? 'default' : 'pointer',
    outline: 'none',
    minHeight: '160px',
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    gap: '8px',
  };

  const labelStyle: CSSProperties = {
    fontFamily: 'monospace',
    fontSize: '11px',
    letterSpacing: '0.15em',
    textTransform: 'uppercase',
    color: 'var(--baekrim-200)',
    opacity: 0.6,
  };

  const hanjaStyle: CSSProperties = {
    fontFamily: 'var(--font-mincho)',
    fontSize: '56px',
    lineHeight: 1,
    color: missing ? 'var(--hanji-300)' : 'var(--baekrim-200)',
    fontWeight: 900,
  };

  const elementStyle: CSSProperties = {
    fontFamily: 'var(--font-mincho)',
    fontSize: '14px',
    color: element ? ELEMENT_COLORS[element] : 'var(--baekrim-200)',
  };

  return (
    <div
      role="button"
      tabIndex={0}
      aria-label={ariaLabel}
      aria-describedby={tooltipOpen ? tooltipId : undefined}
      aria-expanded={tooltipOpen}
      data-testid={`saju-chart-tile-${pillar}`}
      data-pillar={pillar}
      data-missing={missing ? 'true' : 'false'}
      onClick={handleClick}
      onKeyDown={handleKeyDown}
      style={tileStyle}
    >
      <span style={labelStyle} aria-hidden="true">
        {SAJU_PILLAR_LABEL[pillar]}
      </span>

      {missing ? (
        <>
          <span style={hanjaStyle} aria-hidden="true">
            ?
          </span>
          <span
            data-testid={`saju-chart-tile-${pillar}-missing-overlay`}
            style={{
              position: 'absolute',
              top: '50%',
              left: '50%',
              transform: 'translate(-50%, -50%) rotate(-1.5deg)',
              padding: '6px 14px',
              fontFamily: 'var(--font-brush)',
              fontSize: '24px',
              color: 'var(--vermilion-300)',
              border: '2px solid var(--vermilion-300)',
              borderRadius: '4px',
              backgroundColor: 'rgba(26, 18, 8, 0.85)',
              pointerEvents: 'none',
            }}
            aria-hidden="true"
          >
            모름
          </span>
        </>
      ) : (
        <>
          <span style={hanjaStyle} aria-hidden="true">
            {hanja ?? ''}
          </span>
          {element && (
            <span style={elementStyle} aria-hidden="true">
              {SAJU_ELEMENT_HANGUL[element]}
            </span>
          )}
        </>
      )}

      {tooltipOpen && !missing && element && tenGod && (
        <div
          id={tooltipId}
          role="tooltip"
          data-testid={`saju-chart-tile-${pillar}-tooltip`}
          style={{
            position: 'absolute',
            top: 'calc(100% + 8px)',
            left: '50%',
            transform: 'translateX(-50%)',
            whiteSpace: 'nowrap',
            backgroundColor: 'var(--hanji-900)',
            color: 'var(--baekrim-200)',
            padding: '8px 12px',
            border: '1px solid var(--hanji-300)',
            borderRadius: '4px',
            fontFamily: 'var(--font-mincho)',
            fontSize: '13px',
            zIndex: 10,
            pointerEvents: 'none',
          }}
        >
          오행 {ELEMENT_READING[element]} · 십신 {tenGod}
        </div>
      )}
    </div>
  );
}
