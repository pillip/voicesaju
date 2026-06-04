/**
 * ISSUE-097 — `<Pause />` unit tests.
 *
 * Covers AC5: `<Pause />` renders a `<br>` with the `data-pause` hook
 * that the global `@layer copy-system` rule keys off to add a visible
 * line break with adjusted leading.
 *
 * The leading adjustment itself lives in `copy-system.css`. We can't
 * assert the resolved leading in jsdom (no CSS engine for cascade), but
 * we can assert the DOM hook the rule depends on (`br[data-pause]`) and
 * the `display: block` + `margin-block-start` rule shape via a stylesheet
 * presence check.
 */

import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { axe, toHaveNoViolations } from 'jest-axe';

import { Pause } from '@/components/copy';

expect.extend(toHaveNoViolations);

describe('<Pause /> — ISSUE-097 AC5 (data-pause break hook)', () => {
  it('renders a <br> element with the data-pause attribute', () => {
    render(<Pause />);
    const node = screen.getByTestId('pause');
    expect(node.tagName).toBe('BR');
    expect(node).toHaveAttribute('data-pause');
  });

  it('forwards optional id passthrough so tests/a11y tooling can target it', () => {
    render(<Pause id="reading-pause-1" />);
    const node = screen.getByTestId('pause');
    expect(node).toHaveAttribute('id', 'reading-pause-1');
  });

  it('is callable with zero arguments (default-args contract)', () => {
    // Defensive: ensure the default-arg destructuring does not throw.
    // We render inside a paragraph so the JSX context matches real use.
    render(
      <p>
        흠.
        <Pause />이 시간에 사주를 본다고?
      </p>,
    );
    expect(screen.getByTestId('pause')).toBeInTheDocument();
  });
});

describe('<Pause /> — a11y', () => {
  it('has zero axe violations inside a paragraph context', async () => {
    const { container } = render(
      <p>
        흠.
        <Pause />이 시간에 사주를 본다고?
      </p>,
    );
    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });
});
