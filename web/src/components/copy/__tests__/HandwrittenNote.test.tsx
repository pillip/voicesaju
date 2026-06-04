/**
 * ISSUE-097 — `<HandwrittenNote>` unit tests.
 *
 * Covers AC2: `<HandwrittenNote tilt={-3}>흠… 진심이긴 해</HandwrittenNote>`
 * produces a computed `transform` that includes `rotate(-3deg)`.
 *
 * Also locks in:
 *   - The default tilt (-1.5deg) when the prop is omitted.
 *   - The brush font + cream-300 color tokens (aside, not stamp).
 *   - aria-label passthrough so callers can supply a spoken form.
 *   - jest-axe zero-violation scan.
 */

import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { axe, toHaveNoViolations } from 'jest-axe';

import { HandwrittenNote } from '@/components/copy';

expect.extend(toHaveNoViolations);

describe('<HandwrittenNote> — ISSUE-097 AC2 (tilt prop drives rotate(deg))', () => {
  it('default tilt = -1.5 → transform contains rotate(-1.5deg)', () => {
    render(<HandwrittenNote>흠… 진심이긴 해</HandwrittenNote>);
    const style = screen.getByTestId('handwritten-note').getAttribute('style') ?? '';
    expect(style).toContain('rotate(-1.5deg)');
  });

  it('tilt={-3} → computed transform contains rotate(-3deg)', () => {
    render(<HandwrittenNote tilt={-3}>흠… 진심이긴 해</HandwrittenNote>);
    const style = screen.getByTestId('handwritten-note').getAttribute('style') ?? '';
    expect(style).toContain('rotate(-3deg)');
    expect(style).not.toContain('rotate(-1.5deg)');
  });

  it('data-tilt attribute mirrors the prop for downstream selectors', () => {
    render(<HandwrittenNote tilt={-3}>흠… 진심이긴 해</HandwrittenNote>);
    expect(screen.getByTestId('handwritten-note')).toHaveAttribute('data-tilt', '-3');
  });
});

describe('<HandwrittenNote> — brush font + cream-300 (aside)', () => {
  it('uses var(--font-brush) for font-family', () => {
    render(<HandwrittenNote>곁가지</HandwrittenNote>);
    const style = screen.getByTestId('handwritten-note').getAttribute('style') ?? '';
    expect(style).toContain('var(--font-brush)');
  });

  it('uses var(--cream-300) for color (aside, not stamp)', () => {
    render(<HandwrittenNote>곁가지</HandwrittenNote>);
    const style = screen.getByTestId('handwritten-note').getAttribute('style') ?? '';
    expect(style).toContain('var(--cream-300)');
  });
});

describe('<HandwrittenNote> — passthrough + a11y', () => {
  it('forwards aria-label to the rendered span', () => {
    render(<HandwrittenNote aria-label="누님의 곁말">곁말</HandwrittenNote>);
    expect(screen.getByTestId('handwritten-note')).toHaveAttribute('aria-label', '누님의 곁말');
  });

  it('has zero axe violations in default render', async () => {
    const { container } = render(<HandwrittenNote>곁가지</HandwrittenNote>);
    const results = await axe(container, {
      rules: { 'color-contrast': { enabled: false } },
    });
    expect(results).toHaveNoViolations();
  });
});
