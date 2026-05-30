/**
 * Unit tests for `<TarotCard>` (ISSUE-050, Screen 12 hero affordance).
 *
 * Component contract — the page passes a flat prop bag, the component
 * stays presentational:
 *   props = { state, cardArtUrl, cardName, onTap, disableAnimation? }
 *
 * AC coverage:
 * - AC1 — `state='face_down'` renders a tap-able face-down card; the
 *   card art is NOT yet revealed (no `<img>` for the art surface).
 * - AC2 — Tapping invokes `onTap`. The animation timing (300–600ms) is
 *   a CSS property — we assert the `transition-duration` falls inside
 *   the spec window so a regression to 0ms or 2000ms is caught.
 * - AC4 — When `disableAnimation` is true the component sets
 *   `transition-duration: 0ms` so users with `prefers-reduced-motion`
 *   get an instant flip. The page wires that prop from a media query.
 * - AC5 — `state='face_up'` renders the card art + card name.
 *
 * The face-up/face-down toggle is a pure prop. We do NOT test internal
 * timer state — the page owns the flip transition. This keeps the test
 * light and avoids the OOM risk from ISSUE-042 (no fake timers, no
 * repeated rerender storms).
 */
import { describe, expect, it, vi, afterEach } from "vitest";
import { render, screen, cleanup, fireEvent } from "@testing-library/react";
import { TarotCard } from "@/components/tarot/TarotCard";

afterEach(() => {
  cleanup();
});

describe("<TarotCard>", () => {
  it("AC1 — renders a face-down card with the tap affordance", () => {
    render(
      <TarotCard
        state="face_down"
        cardArtUrl="/api/v1/tarot/cards/17/art"
        cardName="달"
        onTap={() => {}}
      />,
    );
    const card = screen.getByRole("button", { name: /오늘의 카드/ });
    expect(card).toBeInTheDocument();
    expect(card).toHaveAttribute("data-state", "face_down");
    // Face-down state should NOT expose the card name to assistive tech
    // — the reveal happens after the flip, not before.
    expect(screen.queryByAltText("달")).toBeNull();
  });

  it("AC2 — clicking the card calls onTap", () => {
    const onTap = vi.fn();
    render(
      <TarotCard
        state="face_down"
        cardArtUrl="/api/v1/tarot/cards/17/art"
        cardName="달"
        onTap={onTap}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: /오늘의 카드/ }));
    expect(onTap).toHaveBeenCalledTimes(1);
  });

  it("AC2 — flip animation duration is within the 300–600ms spec window", () => {
    render(
      <TarotCard
        state="face_down"
        cardArtUrl="/api/v1/tarot/cards/17/art"
        cardName="달"
        onTap={() => {}}
      />,
    );
    const inner = screen.getByTestId("tarot-card-inner");
    // The flip happens on a child element with `transition` on transform.
    // jsdom does not run real CSS, so we read the inline style we set
    // (which mirrors the Tailwind class) for the assertion.
    const duration = inner.style.transitionDuration;
    expect(duration).toMatch(/^\d+ms$/);
    const ms = Number.parseInt(duration, 10);
    expect(ms).toBeGreaterThanOrEqual(300);
    expect(ms).toBeLessThanOrEqual(600);
  });

  it("AC4 — disableAnimation prop forces transition-duration to 0ms", () => {
    render(
      <TarotCard
        state="face_down"
        cardArtUrl="/api/v1/tarot/cards/17/art"
        cardName="달"
        onTap={() => {}}
        disableAnimation
      />,
    );
    const inner = screen.getByTestId("tarot-card-inner");
    expect(inner.style.transitionDuration).toBe("0ms");
  });

  it("AC5 — face_up state renders the card art image with cardName as alt", () => {
    render(
      <TarotCard
        state="face_up"
        cardArtUrl="/api/v1/tarot/cards/17/art"
        cardName="달"
        onTap={() => {}}
      />,
    );
    const img = screen.getByAltText("달");
    expect(img).toBeInTheDocument();
    expect(img).toHaveAttribute("src", "/api/v1/tarot/cards/17/art");
    // data-state mirrors the prop so the page + tests both see the same
    // surface even before the CSS transform completes.
    expect(screen.getByRole("button", { name: /달/ })).toHaveAttribute(
      "data-state",
      "face_up",
    );
  });
});
