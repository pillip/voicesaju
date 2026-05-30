"use client";

/**
 * `<TarotCard>` — Screen 12 hero affordance (ISSUE-050).
 *
 * Renders the daily card in one of two states:
 *   - `face_down` — visible back of the card with the amber-dots
 *     decoration (`✦` pattern from copy_guide.md §10). Tap-able.
 *   - `face_up`   — the card art image + name label revealed.
 *
 * The flip is a CSS 3D rotation on the inner div. We pick `400ms` for
 * the transition duration to sit at the midpoint of the FR-012 window
 * (300–600ms) so any future timing tweak still satisfies the spec.
 *
 * `disableAnimation` is wired from `prefers-reduced-motion` by the
 * page. When true the inner element drops to `0ms` and the flip is
 * effectively instant (AC4).
 *
 * Why inline style for the duration:
 * - Tailwind's `duration-300` class would also work, but jsdom can't
 *   inspect the resolved CSS rule — tests need a property they can
 *   read directly. The inline style is the source of truth here; we
 *   pair it with a Tailwind `transition-transform` class so the
 *   property is animated in production browsers too.
 *
 * Accessibility:
 * - The whole card is a single `<button>`. The accessible name is
 *   "오늘의 카드" in face_down state and the card name (e.g. "달") in
 *   face_up state — matching how an actual user would describe the
 *   surface they're looking at.
 * - We surface the visual state via `data-state` so tests and Playwright
 *   specs can branch without relying on transient CSS values.
 */

import { cn } from "@/lib/utils";

export type TarotCardState = "face_down" | "face_up";

export interface TarotCardProps {
  state: TarotCardState;
  cardArtUrl: string;
  cardName: string;
  onTap: () => void;
  /** Disables the flip transition (used for prefers-reduced-motion). */
  disableAnimation?: boolean;
  /** Optional className for the outer button (page-level layout). */
  className?: string;
}

// FR-012 window mid-point: 300 ≤ duration ≤ 600.
const FLIP_DURATION_MS = 400;

export function TarotCard({
  state,
  cardArtUrl,
  cardName,
  onTap,
  disableAnimation,
  className,
}: TarotCardProps) {
  const isFaceUp = state === "face_up";
  const durationMs = disableAnimation ? 0 : FLIP_DURATION_MS;
  // The accessible name depends on state — face_down reveals nothing
  // about the card, face_up names the specific arcana.
  const accessibleName = isFaceUp ? cardName : "오늘의 카드";

  return (
    <button
      type="button"
      onClick={onTap}
      data-state={state}
      data-testid="tarot-card"
      aria-label={accessibleName}
      className={cn(
        // Outer button establishes the 3D perspective so the inner div
        // can rotate visibly. The whole thing is a relatively small
        // square — Screen 12 places it centered with significant margin
        // above + below for the banner and the subtitle.
        "relative block aspect-[2/3] w-56 max-w-full",
        "[perspective:1000px]",
        "focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-amber-300",
        "rounded-md",
        className,
      )}
    >
      <div
        data-testid="tarot-card-inner"
        className={cn(
          "absolute inset-0 transition-transform [transform-style:preserve-3d]",
          isFaceUp
            ? "[transform:rotateY(180deg)]"
            : "[transform:rotateY(0deg)]",
        )}
        style={{
          transitionDuration: `${durationMs}ms`,
        }}
      >
        {/* Face-down side: amber dots + card back. */}
        <div
          aria-hidden={isFaceUp}
          className={cn(
            "absolute inset-0 flex items-center justify-center rounded-md border border-amber-400/40",
            "bg-ink-800 text-amber-300",
            "[backface-visibility:hidden]",
          )}
        >
          <span className="font-display-han text-3xl" aria-hidden="true">
            ✦
          </span>
        </div>

        {/* Face-up side: card art. The img source is whatever the
            backend handed us — relative placeholder today, R2-signed
            URL after ISSUE-055. */}
        <div
          aria-hidden={!isFaceUp}
          className={cn(
            "absolute inset-0 flex flex-col items-center justify-end gap-s2 overflow-hidden rounded-md border border-amber-400/40 bg-ink-900 p-s2",
            "[backface-visibility:hidden] [transform:rotateY(180deg)]",
          )}
        >
          {isFaceUp && (
            // We only render the <img> when the card is actually
            // face_up so we don't issue a network request for the art
            // until the user has tapped (or the page detected the
            // already-flipped state). This also makes the AC1
            // assertion ("queryByAltText is null in face_down") exact.
            <img
              src={cardArtUrl}
              alt={cardName}
              className="h-full w-full object-contain"
            />
          )}
        </div>
      </div>
    </button>
  );
}
