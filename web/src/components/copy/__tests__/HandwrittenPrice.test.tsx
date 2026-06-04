/**
 * ISSUE-097 — `<HandwrittenPrice>` unit tests.
 *
 * Covers AC1: `<HandwrittenPrice value="4,900원" />` renders with
 * `var(--font-brush)`, `transform: rotate(-1.5deg)`, and the
 * vermilion-500 colour token.
 *
 * jsdom keeps the raw `var(--*)` token strings in the inline style
 * attribute (it never resolves CSS custom properties), so we assert
 * against the serialised style string — same approach used by the
 * ISSUE-091 v2-tokens and ISSUE-092 `<Seal>` test suites.
 */

import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { axe, toHaveNoViolations } from 'jest-axe';

import { HandwrittenPrice } from '@/components/copy';

expect.extend(toHaveNoViolations);

describe('<HandwrittenPrice> — ISSUE-097 AC1 (brush + vermilion + -1.5deg)', () => {
  it('renders the supplied value as text content', () => {
    render(<HandwrittenPrice value="4,900원" />);
    const node = screen.getByTestId('handwritten-price');
    expect(node).toHaveTextContent('4,900원');
  });

  it('uses var(--font-brush) for font-family', () => {
    render(<HandwrittenPrice value="4,900원" />);
    const style = screen.getByTestId('handwritten-price').getAttribute('style') ?? '';
    expect(style).toContain('var(--font-brush)');
  });

  it('uses var(--vermilion-500) for color', () => {
    render(<HandwrittenPrice value="4,900원" />);
    const style = screen.getByTestId('handwritten-price').getAttribute('style') ?? '';
    expect(style).toContain('var(--vermilion-500)');
  });

  it('applies transform: rotate(-1.5deg)', () => {
    render(<HandwrittenPrice value="4,900원" />);
    const style = screen.getByTestId('handwritten-price').getAttribute('style') ?? '';
    expect(style).toContain('rotate(-1.5deg)');
  });
});

describe('<HandwrittenPrice> — passthrough + composition', () => {
  it('forwards className and merges style overrides', () => {
    render(
      <HandwrittenPrice value="1,000원" className="custom-cls" style={{ marginTop: '4px' }} />,
    );
    const node = screen.getByTestId('handwritten-price');
    expect(node).toHaveClass('custom-cls');
    expect(node.getAttribute('style') ?? '').toContain('margin-top: 4px');
    // Inline rotate must still survive a merge.
    expect(node.getAttribute('style') ?? '').toContain('rotate(-1.5deg)');
  });

  it('preserves a caller-supplied aria-label so the price is read explicitly', () => {
    render(<HandwrittenPrice value="4,900원" aria-label="4900 원" />);
    expect(screen.getByTestId('handwritten-price')).toHaveAttribute('aria-label', '4900 원');
  });
});

describe('<HandwrittenPrice> — a11y (jest-axe)', () => {
  it('has zero axe violations', async () => {
    const { container } = render(<HandwrittenPrice value="4,900원" />);
    const results = await axe(container, {
      rules: { 'color-contrast': { enabled: false } },
    });
    expect(results).toHaveNoViolations();
  });
});
