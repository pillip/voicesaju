'use client';

/**
 * `<SajuChartGrid>` — 4-column responsive wrapper for the v2 명식
 * tiles (FR-039 / ISSUE-093).
 *
 * Renders `<SajuChartTile>` children in a 4-column grid that holds its
 * column count even at the 375 px mobile breakpoint (FR-039 AC3). This
 * is the v2 monumental display used on landing, onboarding 1-3,
 * category, reading-play, and `/me/saju` — distinct from the
 * interactive ISSUE-042 `<SajuChart>`.
 *
 * The grid uses `grid-template-columns: repeat(4, 1fr)` per
 * docs/design_system.md §SajuChart; `--space-4` gap (≈16px) and
 * `--hairline` top/bottom borders are inherited from the tiles
 * themselves so the wrapper stays a pure layout primitive.
 *
 * The grid is rendered as a `<div role="group">` (not `<table>`) — the
 * tiles are individually focusable buttons and act like a toolbar, not
 * tabular data. aria-label on the group identifies it as "사주 명식".
 */

import type { CSSProperties, HTMLAttributes, ReactNode } from 'react';

export interface SajuChartGridProps extends HTMLAttributes<HTMLDivElement> {
  children: ReactNode;
}

export function SajuChartGrid({
  children,
  style,
  'aria-label': ariaLabel = '사주 명식',
  ...rest
}: SajuChartGridProps): ReactNode {
  const gridStyle: CSSProperties = {
    display: 'grid',
    // 4 fixed columns at every viewport — FR-039 AC3 requires all four
    // tiles fit one row even at 375 px (~93 px / tile).
    gridTemplateColumns: 'repeat(4, 1fr)',
    gap: '16px',
    width: '100%',
    ...style,
  };

  return (
    <div
      role="group"
      aria-label={ariaLabel}
      data-testid="saju-chart-grid"
      style={gridStyle}
      {...rest}
    >
      {children}
    </div>
  );
}
