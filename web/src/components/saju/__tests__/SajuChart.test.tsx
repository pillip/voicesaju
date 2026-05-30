/**
 * Unit tests for `<SajuChart>` (ISSUE-042).
 *
 * AC3 from ISSUE-042: tap a 명식 cell → tooltip showing 오행 + 십신.
 * Also covers the "시간 모름" rendering path used when the user did
 * not provide a birth hour at onboarding.
 */
import { describe, expect, it } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { PLACEHOLDER_CHART, SajuChart, type SajuChartData } from '@/components/saju/SajuChart';

const FULL_CHART: SajuChartData = {
  hourUnknown: false,
  summary: '갑자년 을축월 병인일 정묘시',
  pillars: [
    { key: 'hour', label: '시', heaven: '정', earth: '묘', element: '목', tenGod: '정인' },
    { key: 'day', label: '일', heaven: '병', earth: '인', element: '화', tenGod: '비견' },
    { key: 'month', label: '월', heaven: '을', earth: '축', element: '토', tenGod: '정관' },
    { key: 'year', label: '년', heaven: '갑', earth: '자', element: '수', tenGod: '편재' },
  ],
};

describe('<SajuChart /> (ISSUE-042)', () => {
  it('renders the one-line 명식 summary', () => {
    render(<SajuChart chart={FULL_CHART} />);
    expect(screen.getByTestId('saju-chart-summary').textContent).toContain(
      '갑자년 을축월 병인일 정묘시',
    );
  });

  it('AC3: tapping a 명식 cell opens an inline tooltip with 오행 + 십신', () => {
    render(<SajuChart chart={FULL_CHART} />);
    // The grid is visible on desktop by default; tap the year cell.
    const yearCell = screen.getByTestId('saju-cell-year');
    fireEvent.click(yearCell);
    const tooltip = screen.getByTestId('saju-tooltip-year');
    expect(tooltip).toBeInTheDocument();
    expect(tooltip.textContent).toMatch(/오행\s*수/);
    expect(tooltip.textContent).toMatch(/십신\s*편재/);
    // aria-describedby wires the cell to the tooltip for screen readers.
    expect(yearCell.getAttribute('aria-describedby')).toBe(tooltip.getAttribute('id'));
  });

  it('tapping the same cell again closes the tooltip', () => {
    render(<SajuChart chart={FULL_CHART} />);
    const cell = screen.getByTestId('saju-cell-month');
    fireEvent.click(cell);
    expect(screen.queryByTestId('saju-tooltip-month')).not.toBeNull();
    fireEvent.click(cell);
    expect(screen.queryByTestId('saju-tooltip-month')).toBeNull();
  });

  it('renders 시간 모름 footer + ? in the 시 cell when hourUnknown is true', () => {
    render(<SajuChart chart={PLACEHOLDER_CHART} />);
    expect(screen.getByTestId('saju-chart-hour-unknown').textContent).toBe('시간 모름');
    const hourCell = screen.getByTestId('saju-cell-hour');
    expect(hourCell.textContent).toMatch(/\?/);
  });

  it("tooltip on 시간 모름 cell shows '시간 모름' rather than 오행/십신", () => {
    render(<SajuChart chart={PLACEHOLDER_CHART} />);
    fireEvent.click(screen.getByTestId('saju-cell-hour'));
    const tooltip = screen.getByTestId('saju-tooltip-hour');
    expect(tooltip.textContent).toMatch(/시간 모름/);
  });

  it('forceCollapsible=true hides the grid until the toggle button is tapped', () => {
    render(<SajuChart chart={FULL_CHART} forceCollapsible />);
    const grid = screen.getByTestId('saju-chart-grid');
    expect(grid.className).toMatch(/hidden/);
    fireEvent.click(screen.getByTestId('saju-chart-toggle'));
    expect(grid.className).toMatch(/block/);
  });
});
