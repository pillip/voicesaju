/**
 * ISSUE-093 — `<SajuChartTile>` v2 display primitive unit tests.
 *
 * Covers FR-039 AC2 + AC5 (and the aria-label contract from the issue
 * "년주 천간 무자, 오행 수"):
 *   AC2: pillar="hour" missing → "모름" overlay + aria-label contains
 *        "모름".
 *   AC5: tile is focusable (role=button, tabIndex=0); Enter/Space
 *        opens the 오행 + 십신 tooltip.
 *
 * The tooltip + missing overlay live alongside the existing ISSUE-042
 * `<SajuChart>` interactive chart — these are NEW v2 visual primitives
 * (not replacements). Coexistence is intentional through M2.5.
 */

import { describe, expect, it } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { axe, toHaveNoViolations } from 'jest-axe';

import {
  SajuChartTile,
  SAJU_PILLAR_LABEL,
  SAJU_ELEMENT_HANGUL,
} from '@/components/saju/SajuChartTile';

expect.extend(toHaveNoViolations);

describe('<SajuChartTile> — FR-039 AC2 (missing="모름" overlay)', () => {
  it('pillar="hour" missing renders the 모름 overlay and aria-label contains 모름', () => {
    render(<SajuChartTile pillar="hour" missing />);
    const tile = screen.getByTestId('saju-chart-tile-hour');
    expect(tile).toHaveAttribute('data-missing', 'true');
    expect(tile.getAttribute('aria-label')).toContain('모름');

    const overlay = screen.getByTestId('saju-chart-tile-hour-missing-overlay');
    expect(overlay).toHaveTextContent('모름');
    const overlayStyle = overlay.getAttribute('style') ?? '';
    expect(overlayStyle).toContain('var(--vermilion-300)');
    expect(overlayStyle).toContain('rotate(-1.5deg)');
  });

  it('non-missing tile does NOT render the 모름 overlay', () => {
    render(
      <SajuChartTile
        pillar="year"
        hanja="무자"
        heaven="무"
        earth="자"
        element="수"
        tenGod="편재"
      />,
    );
    expect(screen.queryByTestId('saju-chart-tile-year-missing-overlay')).not.toBeInTheDocument();
  });

  it('aria-label uses the FR-039 example format "년주 천간 무자, 오행 수"', () => {
    render(
      <SajuChartTile
        pillar="year"
        hanja="무자"
        heaven="무"
        earth="자"
        element="수"
        tenGod="편재"
      />,
    );
    const tile = screen.getByTestId('saju-chart-tile-year');
    expect(tile).toHaveAttribute('aria-label', '년주 천간 무자, 오행 수');
  });

  it('falls back to hanja when heaven+earth not provided', () => {
    render(<SajuChartTile pillar="day" hanja="경신" element="금" />);
    expect(screen.getByTestId('saju-chart-tile-day')).toHaveAttribute(
      'aria-label',
      '일주 천간 경신, 오행 금',
    );
  });
});

describe('<SajuChartTile> — FR-039 AC5 (focus + Enter/Space tooltip)', () => {
  it('tile is focusable with tabIndex=0 and role=button', () => {
    render(<SajuChartTile pillar="day" hanja="경신" element="금" tenGod="비견" />);
    const tile = screen.getByTestId('saju-chart-tile-day');
    expect(tile).toHaveAttribute('tabindex', '0');
    expect(tile).toHaveAttribute('role', 'button');
  });

  it('focused tile + Enter → tooltip with 오행 + 십신 appears', () => {
    render(<SajuChartTile pillar="day" hanja="경신" element="금" tenGod="비견" />);
    const tile = screen.getByTestId('saju-chart-tile-day');
    tile.focus();
    expect(tile).toHaveFocus();

    expect(screen.queryByTestId('saju-chart-tile-day-tooltip')).not.toBeInTheDocument();

    fireEvent.keyDown(tile, { key: 'Enter' });
    const tooltip = screen.getByTestId('saju-chart-tile-day-tooltip');
    expect(tooltip).toHaveAttribute('role', 'tooltip');
    expect(tooltip.textContent).toContain('오행');
    expect(tooltip.textContent).toContain('금');
    expect(tooltip.textContent).toContain('십신');
    expect(tooltip.textContent).toContain('비견');
  });

  it('Space key also toggles the tooltip', () => {
    render(<SajuChartTile pillar="day" hanja="경신" element="금" tenGod="비견" />);
    const tile = screen.getByTestId('saju-chart-tile-day');
    tile.focus();
    fireEvent.keyDown(tile, { key: ' ' });
    expect(screen.getByTestId('saju-chart-tile-day-tooltip')).toBeInTheDocument();
    fireEvent.keyDown(tile, { key: ' ' });
    expect(screen.queryByTestId('saju-chart-tile-day-tooltip')).not.toBeInTheDocument();
  });

  it('Escape closes an open tooltip', () => {
    render(<SajuChartTile pillar="day" hanja="경신" element="금" tenGod="비견" />);
    const tile = screen.getByTestId('saju-chart-tile-day');
    tile.focus();
    fireEvent.keyDown(tile, { key: 'Enter' });
    expect(screen.getByTestId('saju-chart-tile-day-tooltip')).toBeInTheDocument();
    fireEvent.keyDown(tile, { key: 'Escape' });
    expect(screen.queryByTestId('saju-chart-tile-day-tooltip')).not.toBeInTheDocument();
  });

  it('click toggles the tooltip (mouse parity)', () => {
    render(<SajuChartTile pillar="day" hanja="경신" element="금" tenGod="비견" />);
    const tile = screen.getByTestId('saju-chart-tile-day');
    fireEvent.click(tile);
    expect(screen.getByTestId('saju-chart-tile-day-tooltip')).toBeInTheDocument();
    fireEvent.click(tile);
    expect(screen.queryByTestId('saju-chart-tile-day-tooltip')).not.toBeInTheDocument();
  });

  it('missing tile does NOT render a tooltip even on Enter', () => {
    render(<SajuChartTile pillar="hour" missing />);
    const tile = screen.getByTestId('saju-chart-tile-hour');
    tile.focus();
    fireEvent.keyDown(tile, { key: 'Enter' });
    expect(screen.queryByTestId('saju-chart-tile-hour-tooltip')).not.toBeInTheDocument();
  });
});

describe('<SajuChartTile> — pillar labels + element table', () => {
  it('exports the documented pillar labels', () => {
    expect(SAJU_PILLAR_LABEL).toEqual({
      hour: '시주',
      day: '일주',
      month: '월주',
      year: '년주',
    });
  });

  it('exports all 5 오행 mappings', () => {
    expect(Object.keys(SAJU_ELEMENT_HANGUL)).toEqual(['목', '화', '토', '금', '수']);
  });
});

describe('<SajuChartTile> — a11y', () => {
  it('has zero axe violations in the populated state', async () => {
    const { container } = render(
      <SajuChartTile
        pillar="year"
        hanja="무자"
        heaven="무"
        earth="자"
        element="수"
        tenGod="편재"
      />,
    );
    const results = await axe(container, {
      rules: { 'color-contrast': { enabled: false } },
    });
    expect(results).toHaveNoViolations();
  });

  it('has zero axe violations in the missing state', async () => {
    const { container } = render(<SajuChartTile pillar="hour" missing />);
    const results = await axe(container, {
      rules: { 'color-contrast': { enabled: false } },
    });
    expect(results).toHaveNoViolations();
  });
});
