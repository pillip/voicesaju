/**
 * ISSUE-092 — `<Seal>` (印) component unit tests.
 *
 * Covers FR-038 AC1–AC6:
 *   AC1: hanja prop renders the character with vermilion bg + mincho font + -2.5deg.
 *   AC2: category="work" → hanja resolves to 業 (and so on for all categories).
 *   AC3: tilt="right" → transform contains rotate(2.5deg).
 *   AC4: size="lg" → width = height = 112px.
 *   AC5: default decorative → aria-hidden="true"; explicit aria-label → no aria-hidden.
 *
 * Plus a jest-axe scan covering both states (aria-hidden default + labelled).
 *
 * jsdom limitation: computed CSS resolution is unreliable for `var(--*)`
 * tokens, so we assert against the inline style strings rather than
 * `getComputedStyle()` (same approach as the v2-tokens preview test).
 */

import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { axe, toHaveNoViolations } from 'jest-axe';

import { Seal, SEAL_CATEGORY_HANJA } from '@/components/seal';

expect.extend(toHaveNoViolations);

describe('<Seal> — FR-038 AC1 (explicit hanja + vermilion + mincho + default tilt)', () => {
  it('renders the supplied hanja inside a vermilion-300 stamp with mincho font and -2.5deg tilt', () => {
    render(<Seal hanja="戀" />);
    const seal = screen.getByTestId('seal');

    expect(seal).toHaveTextContent('戀');
    expect(seal).toHaveAttribute('data-hanja', '戀');

    // Inline style assertions — jsdom keeps the raw `var(--*)` strings.
    const style = seal.getAttribute('style') ?? '';
    expect(style).toContain('var(--vermilion-300)');
    expect(style).toContain('var(--vermilion-500)'); // inset border / shadow
    expect(style).toContain('var(--font-mincho)');
    // Default tilt is "left" → -2.5deg.
    expect(style).toContain('rotate(-2.5deg)');
  });
});

describe('<Seal> — FR-038 AC2 (category → hanja lookup)', () => {
  it('resolves category="work" to 業', () => {
    render(<Seal category="work" />);
    const seal = screen.getByTestId('seal');
    expect(seal).toHaveTextContent('業');
    expect(seal).toHaveAttribute('data-hanja', '業');
  });

  it.each([
    ['love', '戀'],
    ['work', '業'],
    ['money', '財'],
    ['tarot', '月'],
    ['reading-end', '明'],
  ] as const)('resolves category="%s" to %s', (category, expected) => {
    render(<Seal category={category} />);
    expect(screen.getByTestId('seal')).toHaveTextContent(expected);
  });

  it('prefers explicit hanja over category lookup', () => {
    render(<Seal hanja="心" category="work" />);
    expect(screen.getByTestId('seal')).toHaveTextContent('心');
  });

  it('exports SEAL_CATEGORY_HANJA matching FR-038 AC4 spec', () => {
    expect(SEAL_CATEGORY_HANJA).toEqual({
      love: '戀',
      work: '業',
      money: '財',
      tarot: '月',
      'reading-end': '明',
    });
  });
});

describe('<Seal> — FR-038 AC3 (tilt direction)', () => {
  it('tilt="right" → transform contains rotate(2.5deg) (positive, no minus sign)', () => {
    render(<Seal hanja="月" tilt="right" />);
    const style = screen.getByTestId('seal').getAttribute('style') ?? '';
    expect(style).toContain('rotate(2.5deg)');
    expect(style).not.toContain('rotate(-2.5deg)');
  });

  it('tilt="left" (default) → transform contains rotate(-2.5deg)', () => {
    render(<Seal hanja="月" tilt="left" />);
    const style = screen.getByTestId('seal').getAttribute('style') ?? '';
    expect(style).toContain('rotate(-2.5deg)');
  });
});

describe('<Seal> — FR-038 AC4 (size grid sm/md/lg)', () => {
  it('size="lg" → width and height are 112px (per design_system.md)', () => {
    render(<Seal hanja="命" size="lg" />);
    const seal = screen.getByTestId('seal');
    expect(seal).toHaveAttribute('data-size', 'lg');
    const style = seal.getAttribute('style') ?? '';
    expect(style).toContain('width: 112px');
    expect(style).toContain('height: 112px');
  });

  it('size="md" (default) → 72px', () => {
    render(<Seal hanja="命" />);
    const style = screen.getByTestId('seal').getAttribute('style') ?? '';
    expect(style).toContain('width: 72px');
    expect(style).toContain('height: 72px');
  });

  it('size="sm" → 48px', () => {
    render(<Seal hanja="命" size="sm" />);
    const style = screen.getByTestId('seal').getAttribute('style') ?? '';
    expect(style).toContain('width: 48px');
    expect(style).toContain('height: 48px');
  });
});

describe('<Seal> — FR-038 AC5 (aria-hidden default + aria-label override)', () => {
  it('default render is aria-hidden="true" (decorative)', () => {
    render(<Seal hanja="戀" />);
    const seal = screen.getByTestId('seal');
    expect(seal).toHaveAttribute('aria-hidden', 'true');
    expect(seal).not.toHaveAttribute('aria-label');
  });

  it('explicit aria-label removes aria-hidden and surfaces the label', () => {
    render(<Seal hanja="戀" aria-label="누님이 서명함" />);
    const seal = screen.getByTestId('seal');
    expect(seal).not.toHaveAttribute('aria-hidden');
    expect(seal).toHaveAttribute('aria-label', '누님이 서명함');
  });

  it('empty-string aria-label does NOT escape decorative mode', () => {
    // Defensive: an accidentally-empty label should keep the seal decorative.
    render(<Seal hanja="戀" aria-label="" />);
    expect(screen.getByTestId('seal')).toHaveAttribute('aria-hidden', 'true');
  });
});

describe('<Seal> — passthrough + composition', () => {
  it('preserves caller className and merges inline style overrides', () => {
    render(<Seal hanja="命" className="custom-cls" style={{ marginTop: '8px' }} />);
    const seal = screen.getByTestId('seal');
    expect(seal).toHaveClass('custom-cls');
    expect(seal.getAttribute('style') ?? '').toContain('margin-top: 8px');
  });
});

describe('<Seal> — a11y (jest-axe)', () => {
  it('has zero axe violations in default decorative mode', async () => {
    const { container } = render(<Seal hanja="戀" />);
    const results = await axe(container, {
      rules: { 'color-contrast': { enabled: false } },
    });
    expect(results).toHaveNoViolations();
  });

  it('has zero axe violations when used as labelled signature', async () => {
    const { container } = render(<Seal hanja="戀" aria-label="누님이 서명함" />);
    const results = await axe(container, {
      rules: { 'color-contrast': { enabled: false } },
    });
    expect(results).toHaveNoViolations();
  });
});
