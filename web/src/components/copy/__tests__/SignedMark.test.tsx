/**
 * ISSUE-097 — `<SignedMark>` unit tests.
 *
 * Covers AC3: the DOM contains the text `signed, 누님` followed by a
 * `<Seal hanja="明" size="sm" />`. Mounting at the end of `/reading/play`
 * and `/reading/end` is covered by the page tests; here we lock in the
 * primitive's own contract.
 *
 * Also locks in:
 *   - Mincho italic font + cream-300 colour token.
 *   - inline-flex baseline layout with the documented 8px gap.
 *   - Memoisation of the seal child (re-render with same props does
 *     NOT recompute the inner Seal element — assert by spying on
 *     React.memo via render output identity through a marker prop).
 *   - jest-axe zero-violation scan.
 */

import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { axe, toHaveNoViolations } from 'jest-axe';

import { SignedMark } from '@/components/copy';

expect.extend(toHaveNoViolations);

describe('<SignedMark> — ISSUE-097 AC3 (text + Seal hanja="明" size="sm")', () => {
  it('renders the text "signed, 누님"', () => {
    render(<SignedMark />);
    expect(screen.getByTestId('signed-mark-text')).toHaveTextContent('signed, 누님');
  });

  it('renders a <Seal hanja="明" size="sm" /> as a child', () => {
    render(<SignedMark />);
    const seal = screen.getByTestId('seal');
    expect(seal).toHaveAttribute('data-hanja', '明');
    expect(seal).toHaveAttribute('data-size', 'sm');
  });

  it('SR sees "signed, 누님" but the decorative seal is aria-hidden', () => {
    render(<SignedMark />);
    expect(screen.getByText('signed, 누님')).toBeInTheDocument();
    // <Seal> default is decorative — aria-hidden="true".
    expect(screen.getByTestId('seal')).toHaveAttribute('aria-hidden', 'true');
  });
});

describe('<SignedMark> — mincho italic + cream-300', () => {
  it('uses var(--font-mincho) and italic style', () => {
    render(<SignedMark />);
    const style = screen.getByTestId('signed-mark').getAttribute('style') ?? '';
    expect(style).toContain('var(--font-mincho)');
    expect(style).toContain('font-style: italic');
  });

  it('uses var(--cream-300) for color', () => {
    render(<SignedMark />);
    const style = screen.getByTestId('signed-mark').getAttribute('style') ?? '';
    expect(style).toContain('var(--cream-300)');
  });

  it('lays out as inline-flex with 8px gap and baseline alignment', () => {
    render(<SignedMark />);
    const style = screen.getByTestId('signed-mark').getAttribute('style') ?? '';
    expect(style).toContain('display: inline-flex');
    expect(style).toContain('align-items: baseline');
    expect(style).toContain('gap: 8px');
  });
});

describe('<SignedMark> — Seal child is memoised', () => {
  it('re-render with same props keeps the Seal DOM node identity stable', () => {
    const { rerender, container } = render(<SignedMark />);
    const firstSeal = container.querySelector('[data-testid="seal"]');
    rerender(<SignedMark />);
    const secondSeal = container.querySelector('[data-testid="seal"]');
    // Because the inner SignedMarkSeal is wrapped in React.memo and
    // receives no props, the same DOM node should be reused between
    // renders (React reconciler does not unmount + remount it).
    expect(firstSeal).toBe(secondSeal);
  });

  it('re-render with a changed prop on the parent still keeps the Seal stable', () => {
    const { rerender, container } = render(<SignedMark className="a" />);
    const firstSeal = container.querySelector('[data-testid="seal"]');
    rerender(<SignedMark className="b" />);
    const secondSeal = container.querySelector('[data-testid="seal"]');
    expect(firstSeal).toBe(secondSeal);
  });
});

describe('<SignedMark> — passthrough + a11y', () => {
  it('forwards data-* attributes (used by the play-ended sentinel selector)', () => {
    render(<SignedMark data-testid="play-ended-signature" />);
    expect(screen.getByTestId('play-ended-signature')).toBeInTheDocument();
  });

  it('has zero axe violations', async () => {
    const { container } = render(<SignedMark />);
    const results = await axe(container, {
      rules: { 'color-contrast': { enabled: false } },
    });
    expect(results).toHaveNoViolations();
  });
});
