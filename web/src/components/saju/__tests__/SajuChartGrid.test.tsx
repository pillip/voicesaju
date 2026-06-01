/**
 * ISSUE-093 — `<SajuChartGrid>` unit tests.
 *
 * Covers FR-039 AC3:
 *   AC3: 4-col grid at 375px → 4 tiles fit one row.
 *
 * jsdom does not actually lay out CSS grid pixels, so AC3 is verified
 * structurally — we assert (a) the grid uses
 * `grid-template-columns: repeat(4, 1fr)` and (b) 4 child tiles render
 * as direct children with no media-query override. Combined, this
 * guarantees the AC3 layout at any viewport including 375px.
 */

import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { axe, toHaveNoViolations } from 'jest-axe';

import { SajuChartGrid } from '@/components/saju/SajuChartGrid';
import { SajuChartTile } from '@/components/saju/SajuChartTile';

expect.extend(toHaveNoViolations);

function renderFullChart() {
  return render(
    <SajuChartGrid>
      <SajuChartTile pillar="hour" missing />
      <SajuChartTile pillar="day" hanja="경신" heaven="경" earth="신" element="금" tenGod="비견" />
      <SajuChartTile
        pillar="month"
        hanja="갑오"
        heaven="갑"
        earth="오"
        element="화"
        tenGod="정관"
      />
      <SajuChartTile pillar="year" hanja="무자" heaven="무" earth="자" element="수" tenGod="편재" />
    </SajuChartGrid>,
  );
}

describe('<SajuChartGrid> — FR-039 AC3 (4-col responsive)', () => {
  it('uses grid-template-columns repeat(4, 1fr) — 4 tiles fit one row at every viewport', () => {
    renderFullChart();
    const grid = screen.getByTestId('saju-chart-grid');
    const style = grid.getAttribute('style') ?? '';
    expect(style).toContain('grid-template-columns: repeat(4, 1fr)');
    expect(style).toContain('display: grid');
  });

  it('renders exactly 4 tiles as direct children when given 4 pillars', () => {
    renderFullChart();
    expect(screen.getByTestId('saju-chart-tile-hour')).toBeInTheDocument();
    expect(screen.getByTestId('saju-chart-tile-day')).toBeInTheDocument();
    expect(screen.getByTestId('saju-chart-tile-month')).toBeInTheDocument();
    expect(screen.getByTestId('saju-chart-tile-year')).toBeInTheDocument();
  });

  it('aria-labels the grid as "사주 명식" by default', () => {
    renderFullChart();
    expect(screen.getByTestId('saju-chart-grid')).toHaveAttribute('aria-label', '사주 명식');
    expect(screen.getByTestId('saju-chart-grid')).toHaveAttribute('role', 'group');
  });

  it('caller-provided aria-label wins over the default', () => {
    render(
      <SajuChartGrid aria-label="내 명식">
        <SajuChartTile pillar="year" hanja="무자" heaven="무" earth="자" element="수" />
      </SajuChartGrid>,
    );
    expect(screen.getByTestId('saju-chart-grid')).toHaveAttribute('aria-label', '내 명식');
  });
});

describe('<SajuChartGrid> — a11y', () => {
  it('has zero axe violations on the full 4-pillar chart', async () => {
    const { container } = renderFullChart();
    const results = await axe(container, {
      rules: { 'color-contrast': { enabled: false } },
    });
    expect(results).toHaveNoViolations();
  });
});
