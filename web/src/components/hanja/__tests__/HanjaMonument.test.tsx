/**
 * ISSUE-093 — `<HanjaMonument>` unit tests.
 *
 * Covers FR-039 AC1 + AC4:
 *   AC1: font-size uses `clamp(120px, 28vw, 240px)` in `--font-mincho`.
 *   AC4: the documented character set 命 生 時 性 戀 業 財 月 我 門
 *        renders without throwing and surfaces via data-char.
 *
 * Plus jest-axe scan (decorative default + labelled mode).
 *
 * jsdom limitation: `clamp()` and CSS custom properties are kept as
 * literal strings in `getComputedStyle()` — assertions read the inline
 * style attribute directly so the test is deterministic across viewports.
 */

import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { axe, toHaveNoViolations } from 'jest-axe';

import { HanjaMonument, HANJA_MONUMENT_CHAR_SET } from '@/components/hanja';

expect.extend(toHaveNoViolations);

describe('<HanjaMonument> — FR-039 AC1 (clamp + mincho)', () => {
  it('renders the supplied character at clamp(120px, 28vw, 240px) in mincho', () => {
    render(<HanjaMonument char="命" />);
    const monument = screen.getByTestId('hanja-monument');
    expect(monument).toHaveTextContent('命');
    expect(monument).toHaveAttribute('data-char', '命');

    const style = monument.getAttribute('style') ?? '';
    // AC1: font-size clamp bounds. Assert both endpoints + the vw
    // interpolant land in the inline style.
    expect(style).toContain('font-size: clamp(120px, 28vw, 240px)');
    expect(style).toContain('var(--font-mincho)');
    expect(style).toContain('var(--baekrim-200)');
  });

  it('font-size endpoints satisfy the AC1 clamp bounds (120 ≤ x ≤ 240)', () => {
    render(<HanjaMonument char="生" />);
    const style = screen.getByTestId('hanja-monument').getAttribute('style') ?? '';
    const match = style.match(/clamp\((\d+)px,\s*([\d.]+)vw,\s*(\d+)px\)/);
    expect(match).not.toBeNull();
    const [, min, , max] = match!;
    expect(Number(min)).toBe(120);
    expect(Number(max)).toBe(240);
  });
});

describe('<HanjaMonument> — FR-039 AC4 (documented character set)', () => {
  it.each(HANJA_MONUMENT_CHAR_SET.map((c) => [c]))('renders %s', (char) => {
    render(<HanjaMonument char={char} />);
    expect(screen.getByTestId('hanja-monument')).toHaveTextContent(char);
  });

  it('exports the full FR-039 character set', () => {
    expect(HANJA_MONUMENT_CHAR_SET).toEqual([
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
    ]);
  });
});

describe('<HanjaMonument> — a11y', () => {
  it('default render is aria-hidden (decorative)', () => {
    render(<HanjaMonument char="命" />);
    const monument = screen.getByTestId('hanja-monument');
    expect(monument).toHaveAttribute('aria-hidden', 'true');
    expect(monument).not.toHaveAttribute('aria-label');
  });

  it('explicit aria-label removes aria-hidden and surfaces the label', () => {
    render(<HanjaMonument char="命" aria-label="당신의 명운" />);
    const monument = screen.getByTestId('hanja-monument');
    expect(monument).not.toHaveAttribute('aria-hidden');
    expect(monument).toHaveAttribute('aria-label', '당신의 명운');
  });

  it('has zero axe violations in decorative default mode', async () => {
    const { container } = render(<HanjaMonument char="命" />);
    const results = await axe(container, {
      rules: { 'color-contrast': { enabled: false } },
    });
    expect(results).toHaveNoViolations();
  });

  it('has zero axe violations in labelled mode', async () => {
    const { container } = render(<HanjaMonument char="命" aria-label="당신의 명운" />);
    const results = await axe(container, {
      rules: { 'color-contrast': { enabled: false } },
    });
    expect(results).toHaveNoViolations();
  });
});

describe('<HanjaMonument> — cut bleed', () => {
  it('cut=true (default) sets negative margins for the edge-bleed', () => {
    render(<HanjaMonument char="命" />);
    const style = screen.getByTestId('hanja-monument').getAttribute('style') ?? '';
    expect(style).toContain('margin-left: -0.15em');
    expect(style).toContain('margin-right: -0.1em');
  });

  it('cut=false drops the negative margins', () => {
    render(<HanjaMonument char="命" cut={false} />);
    const style = screen.getByTestId('hanja-monument').getAttribute('style') ?? '';
    expect(style).not.toContain('margin-left: -0.15em');
    expect(style).not.toContain('margin-right: -0.1em');
  });
});
