/**
 * Unit tests for `<TarotSpread>` (ISSUE-094, v2 Screen 12 hero).
 *
 * Component contract — the page hands the component a single
 * deterministic card (fetched on mount via `/tarot/today`, FR-013) and
 * a tap handler that gets invoked AFTER the cascade completes. The
 * five fan cards are intrinsic to the component; the page does not
 * pass them in.
 *
 *   props = {
 *     card: { artUrl, name },     // FR-013 deterministic card
 *     onReveal: () => void,       // fires once the flip cascade ends
 *     prefersReducedMotion?: bool,
 *     ariaLabel?: string,         // override "오늘의 카드"
 *   }
 *
 * AC coverage at the component level:
 * - AC1 — five face-down cards rendered with `data-pos={1..5}` and
 *   `.__pose` rotations -22°/-11°/0°/+11°/+22°.
 * - AC2 — tap drives the four-stage cascade; we exercise it via the
 *   `animationend`/`transitionend` events (the reducer test covers the
 *   state-machine logic; here we verify DOM observability — class
 *   toggles, `aria-pressed`).
 * - AC3 — the reveal card art comes from the `card` prop and is
 *   identical no matter which index the user taps (we render twice
 *   with different tap indices and assert the same alt + src).
 * - AC4 — `.spread-card__face`, `__back`, `__front` carry the absolute
 *   positioning hooks; faces never override with `position: relative`.
 * - Reduced-motion — when `prefersReducedMotion=true` the tap jumps
 *   straight to the reveal (no `is-moving`/`is-centered` interim).
 *
 * AC5 (375px no overflow) is a CSS regression covered by a Playwright
 * visual test — jsdom has no layout engine. We DO assert the class
 * naming hook (`.tarot-spread`) exists so the CSS rule can target it.
 *
 * Why we mock `window.matchMedia`:
 * - jsdom's default matchMedia stub always returns `matches: false`,
 *   which is what we want for the non-reduced-motion path. The
 *   reduced-motion test passes `prefersReducedMotion` explicitly via
 *   prop so we don't depend on the global stub.
 */
import { describe, expect, it, vi, afterEach } from 'vitest';
import { render, screen, cleanup, fireEvent, act } from '@testing-library/react';
import { axe, toHaveNoViolations } from 'jest-axe';
import { TarotSpread } from '@/components/tarot/TarotSpread';

expect.extend(toHaveNoViolations);

afterEach(() => {
  cleanup();
});

const SAMPLE_CARD = {
  artUrl: '/api/v1/tarot/cards/17/art',
  name: '달',
};

describe('<TarotSpread> (ISSUE-094)', () => {
  it('AC1 — renders exactly 5 face-down cards with data-pos 1..5', () => {
    render(<TarotSpread card={SAMPLE_CARD} onReveal={() => {}} />);
    const cards = screen.getAllByTestId(/^spread-card-\d$/);
    expect(cards).toHaveLength(5);
    const positions = cards.map((el) => el.getAttribute('data-pos'));
    expect(positions).toEqual(['1', '2', '3', '4', '5']);
  });

  it('AC1 — the `.tarot-spread` container is rendered as the perspective root', () => {
    const { container } = render(<TarotSpread card={SAMPLE_CARD} onReveal={() => {}} />);
    const root = container.querySelector('.tarot-spread');
    expect(root).not.toBeNull();
  });

  it('AC1 — each card carries a `.__pose` layer with the documented rotation token', () => {
    // We assert the data-rot attribute (the angle expressed in degrees);
    // it's what the component uses to drive `--pose-rot` so tests can read
    // the source of truth without touching computed CSS.
    render(<TarotSpread card={SAMPLE_CARD} onReveal={() => {}} />);
    const expected = ['-22', '-11', '0', '11', '22'];
    for (let i = 0; i < 5; i++) {
      const pose = screen.getByTestId(`spread-card-${i + 1}`).querySelector('.spread-card__pose');
      expect(pose).not.toBeNull();
      expect(pose!.getAttribute('data-rot')).toBe(expected[i]);
    }
  });

  it('AC2 — tap drives is-moving on all cards then is-centered on the tapped card', () => {
    render(<TarotSpread card={SAMPLE_CARD} onReveal={() => {}} />);
    const card3 = screen.getByTestId('spread-card-3');
    const card1 = screen.getByTestId('spread-card-1');

    // Initial — all cards are inert (no animation classes).
    expect(card3.className).not.toContain('is-moving');
    expect(card3.className).not.toContain('is-centered');

    // Click the middle card (index 2 → data-pos=3).
    fireEvent.click(card3);

    // After tap → every card gets `is-moving` so non-tapped cards
    // translate off-screen while the tapped one prepares to centre.
    expect(card1.className).toContain('is-moving');
    expect(card3.className).toContain('is-moving');

    // Fire animationend on the tapped card → it enters `is-centered`.
    // The reducer routes to the tapped index; non-tapped cards stay
    // in `is-moving` until they finish leaving.
    act(() => {
      fireEvent.animationEnd(card3);
    });
    expect(card3.className).toContain('is-centered');
  });

  it('AC2 — after centering, `aria-pressed=true` toggles on the tapped card', () => {
    render(<TarotSpread card={SAMPLE_CARD} onReveal={() => {}} />);
    const card2 = screen.getByTestId('spread-card-2');

    fireEvent.click(card2);
    // Before centre completes the card is NOT pressed.
    expect(card2.getAttribute('aria-pressed')).toBe('false');

    // Two animationEnds: moving→centered, centered→pressed.
    act(() => {
      fireEvent.animationEnd(card2);
    });
    act(() => {
      fireEvent.animationEnd(card2);
    });

    // Centre + flip kickoff → reducer in `pressed` → DOM reflects it.
    expect(card2.getAttribute('aria-pressed')).toBe('true');
  });

  it('AC2 — reveal section receives `.reveal-visible` and fires onReveal after flip transitionend', () => {
    const onReveal = vi.fn();
    const { container } = render(<TarotSpread card={SAMPLE_CARD} onReveal={onReveal} />);
    const card3 = screen.getByTestId('spread-card-3');
    const reveal = container.querySelector('.tarot-spread__reveal');
    expect(reveal).not.toBeNull();
    expect(reveal!.className).not.toContain('reveal-visible');

    // Drive the full cascade: moving → centered → pressed → revealed.
    fireEvent.click(card3);
    act(() => {
      fireEvent.animationEnd(card3); // moveDone
    });
    act(() => {
      fireEvent.animationEnd(card3); // centerDone → enters `pressed`
    });
    // Flip transition ends → reveal fades in and onReveal fires.
    const inner = card3.querySelector('.spread-card__inner');
    expect(inner).not.toBeNull();
    act(() => {
      fireEvent.transitionEnd(inner!, { propertyName: 'transform' });
    });

    expect(reveal!.className).toContain('reveal-visible');
    expect(onReveal).toHaveBeenCalledOnce();
  });

  it('AC3 — reveal card art is identical regardless of which index is tapped', () => {
    // Render twice, tapping different indices each time. The card art
    // must match the prop, NOT the tap target — this is the FR-013
    // determinism guarantee surfaced at the component level.
    function tapThrough(index: number) {
      cleanup();
      const { container } = render(<TarotSpread card={SAMPLE_CARD} onReveal={() => {}} />);
      const target = screen.getByTestId(`spread-card-${index + 1}`);
      fireEvent.click(target);
      // Two animationEnds: moving → centered → pressed.
      act(() => {
        fireEvent.animationEnd(target);
      });
      act(() => {
        fireEvent.animationEnd(target);
      });
      const inner = target.querySelector('.spread-card__inner');
      act(() => {
        fireEvent.transitionEnd(inner!, { propertyName: 'transform' });
      });
      const img = container.querySelector('.tarot-spread__reveal img') as HTMLImageElement | null;
      return img;
    }

    const imgFromIndex0 = tapThrough(0);
    const imgFromIndex4 = tapThrough(4);
    expect(imgFromIndex0).not.toBeNull();
    expect(imgFromIndex4).not.toBeNull();
    expect(imgFromIndex0!.getAttribute('src')).toBe(SAMPLE_CARD.artUrl);
    expect(imgFromIndex4!.getAttribute('src')).toBe(SAMPLE_CARD.artUrl);
    expect(imgFromIndex0!.getAttribute('alt')).toBe(SAMPLE_CARD.name);
    expect(imgFromIndex4!.getAttribute('alt')).toBe(SAMPLE_CARD.name);
  });

  it('AC4 — face/back/front DOM hooks expose the absolute positioning hierarchy', () => {
    const { container } = render(<TarotSpread card={SAMPLE_CARD} onReveal={() => {}} />);
    // `.spread-card__face` is the absolute-positioned parent; `__back`
    // and `__front` inherit. The regression guard is that NONE of them
    // carry an inline `position: relative` override.
    const faces = container.querySelectorAll('.spread-card__face');
    expect(faces.length).toBeGreaterThan(0);
    const backs = container.querySelectorAll('.spread-card__back');
    expect(backs.length).toBe(5);
    const fronts = container.querySelectorAll('.spread-card__front');
    expect(fronts.length).toBe(5);

    // Guard: no inline `position: relative` on backs or fronts.
    [...backs, ...fronts].forEach((el) => {
      const inline = (el as HTMLElement).style.position;
      expect(inline === 'relative').toBe(false);
    });
  });

  it('reduced-motion — tap skips the choreography and reveals immediately', () => {
    const onReveal = vi.fn();
    const { container } = render(
      <TarotSpread card={SAMPLE_CARD} onReveal={onReveal} prefersReducedMotion />,
    );
    const card1 = screen.getByTestId('spread-card-1');
    fireEvent.click(card1);

    // No `is-moving`/`is-centered` should appear — the reducer jumps
    // straight to `revealed`, so the reveal panel is visible right away.
    const reveal = container.querySelector('.tarot-spread__reveal');
    expect(reveal!.className).toContain('reveal-visible');
    expect(card1.className).not.toContain('is-moving');
    expect(onReveal).toHaveBeenCalledOnce();
  });

  it('accessibility — the spread region has an aria-label and each card is a button', () => {
    render(<TarotSpread card={SAMPLE_CARD} onReveal={() => {}} />);
    // Default aria-label per copy_guide.md §10.
    expect(screen.getByRole('group', { name: /오늘의 카드/ })).toBeInTheDocument();
    const buttons = screen.getAllByRole('button');
    // 5 spread cards (the page header is owned by `/tarot/page.tsx`).
    expect(buttons.length).toBeGreaterThanOrEqual(5);
  });

  it('ignores duplicate taps once the cascade has started', () => {
    // FR-013 determinism is preserved at the component level too:
    // a second tap on a different card mid-cascade must not switch
    // which card centres.
    render(<TarotSpread card={SAMPLE_CARD} onReveal={() => {}} />);
    const card1 = screen.getByTestId('spread-card-1');
    const card5 = screen.getByTestId('spread-card-5');
    fireEvent.click(card1);
    fireEvent.click(card5);

    // Two animationEnds reach `pressed`; only the latched index (1) flips.
    act(() => {
      fireEvent.animationEnd(card1);
    });
    act(() => {
      fireEvent.animationEnd(card1);
    });
    expect(card1.getAttribute('aria-pressed')).toBe('true');
    expect(card5.getAttribute('aria-pressed')).toBe('false');
  });

  it('axe-core — no a11y violations in the initial face-down spread', async () => {
    const { container } = render(<TarotSpread card={SAMPLE_CARD} onReveal={() => {}} />);
    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });
});
