'use client';

/**
 * `<TarotSpread>` — v2 Screen 12 hero (ISSUE-094).
 *
 * Replaces the single `<TarotCard>` (ISSUE-051) with a 5-card fan
 * spread. Tapping any card runs the deterministic
 * discard → centre → flip → reveal cascade. The reveal card art is
 * supplied by the page (fetched once via `/tarot/today`, FR-013) and
 * is independent of which spread index the user taps — the AC tests
 * verify this end-to-end.
 *
 * Layer architecture (per Scope notes):
 *   .tarot-spread       — perspective root, transform-style preserve-3d
 *   .spread-card        — absolute translate slot (`data-pos=1..5`)
 *     .spread-card__pose      — fan rotation (-22..+22), preserve-3d
 *       .spread-card__inner   — flip rotateY when aria-pressed=true
 *         .spread-card__face .spread-card__back   — face-down side
 *         .spread-card__face .spread-card__front  — face-up side
 *   .tarot-spread__reveal     — fades in once flip completes
 *
 * Why scoped `<style>`-in-component instead of a global stylesheet:
 * - ISSUE-098 owns the canonical `.tilted` / `.reveal-*` utilities. To
 *   avoid stepping on it we inline the spread CSS as a `<style>` block
 *   scoped via `[data-tarot-spread="root"]` selectors so the class
 *   names remain stable but the rules don't leak.
 * - All v2 tokens (--vermilion-*, --hanji-*, --baekrim-*, --font-*) come
 *   from `web/src/styles/tokens.css` which is already loaded globally
 *   by `app/layout.tsx`. v1 motion tokens (--dur-*, --ease-*) live in
 *   tailwind.config.ts; we hard-code their numeric values where needed
 *   so the cascade timings stay readable.
 *
 * Accessibility:
 * - The container is a `role="group"` with a Korean aria-label so
 *   screen readers announce "오늘의 카드, 5장 펼침" semantics.
 * - Each card is a `<button>` with `aria-pressed` reflecting the flip
 *   state. The pressed card is the one driving the reveal — non-tapped
 *   buttons stay `aria-pressed="false"` and become `aria-hidden="true"`
 *   once they slide off-screen so AT users skip the dead-letter row.
 *
 * Reduced-motion:
 * - The page passes `prefersReducedMotion` from a `matchMedia` hook.
 * - On tap, the reducer dispatches `forceReveal` which jumps straight
 *   to `revealed`; the CSS adds no transitions on that path.
 *
 * No setTimeout chain:
 * - DOM events (`onAnimationEnd`, `onTransitionEnd`) advance the
 *   reducer. This means the reveal cascade never desynchronises from
 *   the actual CSS timing, AND reduced-motion users get the reveal
 *   immediately via `forceReveal` without any waiting.
 */
import {
  useCallback,
  useEffect,
  useReducer,
  type AnimationEvent,
  type TransitionEvent,
} from 'react';
import { cn } from '@/lib/utils';
import { initialSpreadState, spreadReducer, type SpreadPhase } from './tarotSpreadReducer';

export interface TarotSpreadCard {
  /** FR-013-derived art URL (relative or R2-signed). */
  artUrl: string;
  /** Card name in Korean, used as the alt text on reveal. */
  name: string;
}

export interface TarotSpreadProps {
  /** The deterministic card for today — same value regardless of tap. */
  card: TarotSpreadCard;
  /**
   * Fires once the flip-and-fade cascade completes. The page uses this
   * to kick off the FR-015 audio pipeline (NFR-003 ≤ 2s budget).
   */
  onReveal: () => void;
  /** When true, skip the choreography and jump straight to reveal. */
  prefersReducedMotion?: boolean;
  /** Overrides the default group aria-label. */
  ariaLabel?: string;
  /** Extra className on the outer container (page-level layout). */
  className?: string;
}

// Fan angles for `.__pose` per the issue Scope.
// Index 0..4 → -22°, -11°, 0°, +11°, +22°.
const POSE_ANGLES = [-22, -11, 0, 11, 22] as const;

// Slot offset in pixels — pulls each card sideways before the rotation
// is applied. The exact value is tuned for 224px-wide cards but the
// 375px-viewport AC is handled by the CSS clamp() inside the scoped
// style block, NOT here.
const SLOT_OFFSETS = [-160, -80, 0, 80, 160] as const;

export function TarotSpread({
  card,
  onReveal,
  prefersReducedMotion,
  ariaLabel = '오늘의 카드, 5장 펼침',
  className,
}: TarotSpreadProps) {
  const [state, dispatch] = useReducer(spreadReducer, initialSpreadState);

  // Reduced-motion: the tap handler dispatches `forceReveal` instead of
  // `tap` so the reducer skips the moving/centered/pressed cascade and
  // lands on `revealed` immediately. We still need to fire `onReveal`
  // so the page can wire audio — driven from an effect on `phase`.
  const handleTap = useCallback(
    (index: number) => {
      if (state.phase !== 'idle') return;
      if (prefersReducedMotion) {
        dispatch({ type: 'forceReveal', index });
        return;
      }
      dispatch({ type: 'tap', index });
    },
    [state.phase, prefersReducedMotion],
  );

  // Fire `onReveal` exactly once when the cascade reaches `revealed`.
  useEffect(() => {
    if (state.phase === 'revealed') {
      onReveal();
    }
    // We intentionally do NOT depend on `onReveal` here — if the page
    // re-creates the callback on every render we'd over-fire.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state.phase]);

  const handleAnimationEnd = useCallback(
    (event: AnimationEvent<HTMLButtonElement>, index: number) => {
      // We only react to the tapped card's own animation completions to
      // avoid racing on the non-tapped cards' off-screen slide.
      if (state.tappedIndex !== index) return;
      if (state.phase === 'moving') {
        dispatch({ type: 'moveDone' });
      } else if (state.phase === 'centered') {
        // The centre animation ends → reducer moves to `pressed`, the
        // CSS picks up `aria-pressed=true` and runs the flip.
        dispatch({ type: 'centerDone' });
      }
      void event;
    },
    [state.phase, state.tappedIndex],
  );

  const handleTransitionEnd = useCallback(
    (event: TransitionEvent<HTMLDivElement>, index: number) => {
      if (state.tappedIndex !== index) return;
      if (state.phase !== 'pressed') return;
      // The flip is a transform transition; we filter so unrelated
      // properties (opacity fades on the face) don't trigger early.
      // jsdom may report an empty `propertyName` — when missing we
      // accept the event, since the only transition declared on
      // `.spread-card__inner` is transform anyway.
      const prop = event.propertyName ?? '';
      if (prop && prop !== 'transform') return;
      dispatch({ type: 'flipDone' });
    },
    [state.phase, state.tappedIndex],
  );

  return (
    <div
      data-tarot-spread="root"
      className={cn('tarot-spread', className)}
      role="group"
      aria-label={ariaLabel}
      data-phase={state.phase}
    >
      <style>{SPREAD_CSS}</style>
      <div className="tarot-spread__stage">
        {POSE_ANGLES.map((angle, index) => {
          const isTapped = state.tappedIndex === index;
          const slotOffset = SLOT_OFFSETS[index];
          const phaseClass = cardPhaseClass(state.phase, isTapped);
          // Non-tapped cards become inert once the cascade starts.
          const hideFromAt = state.phase !== 'idle' && !isTapped ? true : undefined;
          return (
            <button
              key={index}
              type="button"
              data-testid={`spread-card-${index + 1}`}
              data-pos={index + 1}
              data-rot={String(angle)}
              data-tapped={isTapped ? 'true' : 'false'}
              // Each fan card gets a positional Korean label so screen
              // readers announce "카드 1", "카드 2" etc. — the FR-013
              // reveal card name is announced via the reveal panel's
              // aria-live region, NOT here, so determinism (tap target
              // does NOT influence the card) is preserved at the AT
              // layer too.
              aria-label={`카드 ${index + 1}`}
              aria-pressed={
                state.phase === 'pressed' || state.phase === 'revealed' ? isTapped : false
              }
              aria-hidden={hideFromAt}
              onClick={() => handleTap(index)}
              onAnimationEnd={(e) => handleAnimationEnd(e, index)}
              className={cn('spread-card', phaseClass)}
              style={
                {
                  '--slot-offset': `${slotOffset}px`,
                } as React.CSSProperties
              }
            >
              <div
                className="spread-card__pose"
                data-rot={String(angle)}
                style={
                  {
                    '--pose-rot': `${angle}deg`,
                  } as React.CSSProperties
                }
              >
                <div
                  className="spread-card__inner"
                  onTransitionEnd={(e) => handleTransitionEnd(e, index)}
                >
                  <div className="spread-card__face spread-card__back" aria-hidden="true">
                    <span className="spread-card__mark">✦</span>
                  </div>
                  <div className="spread-card__face spread-card__front" aria-hidden={!isTapped}>
                    {/* Only render the art img once the user has tapped
                        this card — keeps the network request lazy and
                        keeps the "no img in face_down state" expectation
                        consistent with the v1 single-card behaviour. */}
                    {isTapped && (
                      <img src={card.artUrl} alt={card.name} className="spread-card__art" />
                    )}
                  </div>
                </div>
              </div>
            </button>
          );
        })}
      </div>

      <div
        className={cn('tarot-spread__reveal', state.phase === 'revealed' && 'reveal-visible')}
        aria-live="polite"
      >
        {state.phase === 'revealed' && (
          <>
            <img src={card.artUrl} alt={card.name} className="tarot-spread__reveal-art" />
            <p className="tarot-spread__reveal-name">{card.name}</p>
          </>
        )}
      </div>
    </div>
  );
}

function cardPhaseClass(phase: SpreadPhase, isTapped: boolean): string {
  switch (phase) {
    case 'idle':
      return '';
    case 'moving':
      // All five cards animate in the moving phase: non-tapped slide
      // off-screen, the tapped one starts its translate-to-centre.
      return 'is-moving';
    case 'centered':
      // Only the tapped card centres; non-tapped stay in `is-moving`
      // (their slide can still be running, and they stay hidden).
      return isTapped ? 'is-centered' : 'is-moving is-gone';
    case 'pressed':
      // The tapped card has finished centring and is now flipping; CSS
      // keys off `aria-pressed=true` for the flip transform itself.
      return isTapped ? 'is-centered is-flipping' : 'is-moving is-gone';
    case 'revealed':
      // Cascade complete — the reveal panel handles the surfacing; the
      // tapped card stays centred + flipped (front face visible).
      return isTapped ? 'is-centered is-flipping is-revealed' : 'is-moving is-gone';
  }
}

// Scoped CSS for the spread. We embed it in a `<style>` block inside
// the component so ISSUE-098 retains ownership of the global utility
// surface (`.tilted`, `.reveal-*`). All selectors are scoped to
// `[data-tarot-spread="root"]` to keep the cascade contained.
const SPREAD_CSS = `
[data-tarot-spread="root"].tarot-spread {
  position: relative;
  width: 100%;
  max-width: 720px;
  /* The stage is at least one card tall + space for the reveal panel. */
  min-height: 420px;
  perspective: 1800px;
  -webkit-perspective: 1800px;
  transform-style: preserve-3d;
  -webkit-transform-style: preserve-3d;
}
@media (min-width: 768px) {
  [data-tarot-spread="root"].tarot-spread {
    perspective: 2400px;
    -webkit-perspective: 2400px;
    min-height: 520px;
  }
}
[data-tarot-spread="root"] .tarot-spread__stage {
  position: relative;
  width: 100%;
  height: 360px;
  transform-style: preserve-3d;
  -webkit-transform-style: preserve-3d;
}
/* Each card is anchored to centre and offset via --slot-offset. The
   transform-origin sits at the bottom of the card so the fan reads as
   "held in a hand" rather than rotating around the centre. */
[data-tarot-spread="root"] .spread-card {
  position: absolute;
  top: 50%;
  left: 50%;
  /* Card geometry — clamp the width so it shrinks at 375px (AC5). */
  width: clamp(96px, 18vw, 160px);
  aspect-ratio: 3 / 5;
  margin: 0;
  padding: 0;
  border: 0;
  background: transparent;
  cursor: pointer;
  /* Slot translate: re-centre + offset to the card's fan slot. We use
     a function-style transform so .__pose can layer its rotation
     without us having to recompose everything in one matrix. */
  transform:
    translate(-50%, -50%)
    translateX(var(--slot-offset, 0px));
  transform-style: preserve-3d;
  -webkit-transform-style: preserve-3d;
  transition: transform 650ms cubic-bezier(0.16, 1, 0.3, 1),
              opacity 650ms ease-out;
  will-change: transform, opacity;
}
[data-tarot-spread="root"] .spread-card:focus-visible {
  outline: 2px solid var(--amber-300, #facc15);
  outline-offset: 6px;
  border-radius: 6px;
}
/* Moving — non-tapped cards translate up + fade out. */
[data-tarot-spread="root"] .spread-card.is-moving:not(.is-centered) {
  animation: spread-discard 650ms cubic-bezier(0.4, 0, 0.2, 1) forwards;
}
[data-tarot-spread="root"] .spread-card.is-moving.is-gone {
  opacity: 0;
  pointer-events: none;
}
/* Centered — the tapped card slides to dead centre over 450ms. */
[data-tarot-spread="root"] .spread-card.is-centered {
  animation: spread-centre 450ms cubic-bezier(0.16, 1, 0.3, 1) forwards;
  z-index: 10;
}
@keyframes spread-discard {
  to {
    transform:
      translate(-50%, -50%)
      translateX(var(--slot-offset, 0px))
      translateY(-140%);
    opacity: 0;
  }
}
@keyframes spread-centre {
  to {
    transform: translate(-50%, -50%) translateX(0);
  }
}

/* Pose layer — rotates the card around the bottom-centre origin for the
   "held fan" effect. Hovers/active states are intentionally NOT defined
   here so the cascade animation owns transform. */
[data-tarot-spread="root"] .spread-card__pose {
  position: relative;
  width: 100%;
  height: 100%;
  transform-origin: 50% 100%;
  transform: rotate(var(--pose-rot, 0deg));
  transform-style: preserve-3d;
  -webkit-transform-style: preserve-3d;
  transition: transform 450ms cubic-bezier(0.16, 1, 0.3, 1);
}
/* When the card is centred / flipping the pose rotation is unwound so
   the flip happens around the natural Y axis, not a tilted one. */
[data-tarot-spread="root"] .spread-card.is-centered .spread-card__pose,
[data-tarot-spread="root"] .spread-card.is-flipping .spread-card__pose {
  transform: rotate(0deg);
}

/* Inner — the flip pivot. Driven by aria-pressed=true. */
[data-tarot-spread="root"] .spread-card__inner {
  position: relative;
  width: 100%;
  height: 100%;
  transform-style: preserve-3d;
  -webkit-transform-style: preserve-3d;
  transform: rotateY(0deg);
  transition: transform 500ms cubic-bezier(0.4, 0, 0.2, 1);
}
[data-tarot-spread="root"] .spread-card[aria-pressed="true"] .spread-card__inner {
  transform: rotateY(180deg);
}

/* Faces — absolutely positioned. The regression guard says BACK and
   FRONT must inherit; neither sets position: relative anywhere. */
[data-tarot-spread="root"] .spread-card__face {
  position: absolute;
  inset: 0;
  backface-visibility: hidden;
  -webkit-backface-visibility: hidden;
  border: 1px solid var(--amber-400, #f59e0b);
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
}
[data-tarot-spread="root"] .spread-card__back {
  background: var(--hanji-800, #1a1208);
  background-image:
    radial-gradient(circle at 50% 20%, rgba(217, 196, 154, 0.06), transparent 60%),
    var(--grain-strong, none);
  color: var(--amber-300, #facc15);
}
[data-tarot-spread="root"] .spread-card__front {
  background: var(--hanji-900, #0a0604);
  transform: rotateY(180deg);
  -webkit-transform: rotateY(180deg);
}
[data-tarot-spread="root"] .spread-card__mark {
  font-family: var(--font-mincho, serif);
  font-size: clamp(20px, 4vw, 36px);
}
[data-tarot-spread="root"] .spread-card__art {
  width: 100%;
  height: 100%;
  object-fit: contain;
}

/* Reveal panel — fades in over 400ms after the flip transition lands. */
[data-tarot-spread="root"] .tarot-spread__reveal {
  margin-top: 24px;
  opacity: 0;
  transition: opacity 400ms ease-out;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
}
[data-tarot-spread="root"] .tarot-spread__reveal.reveal-visible {
  opacity: 1;
}
[data-tarot-spread="root"] .tarot-spread__reveal-art {
  width: clamp(120px, 30vw, 200px);
  aspect-ratio: 3 / 5;
  object-fit: contain;
}
[data-tarot-spread="root"] .tarot-spread__reveal-name {
  font-family: var(--font-display-han, "Noto Serif KR", serif);
  font-size: 1.5rem;
  color: var(--baekrim-200, #d9c49a);
  margin: 0;
}

/* AC5 — at 375px viewport, dial the fan in: smaller offsets + tighter
   angles so the leftmost / rightmost cards stay inside the viewport.
   We override --slot-offset on each data-pos slot. */
@media (max-width: 480px) {
  [data-tarot-spread="root"] .spread-card[data-pos="1"] { --slot-offset: -84px; }
  [data-tarot-spread="root"] .spread-card[data-pos="2"] { --slot-offset: -44px; }
  [data-tarot-spread="root"] .spread-card[data-pos="3"] { --slot-offset:   0px; }
  [data-tarot-spread="root"] .spread-card[data-pos="4"] { --slot-offset:  44px; }
  [data-tarot-spread="root"] .spread-card[data-pos="5"] { --slot-offset:  84px; }
}

/* Reduced motion — kill choreography, keep the reveal visible. The
   reducer also short-circuits to revealed, but we belt-and-braces
   the CSS so a user who flips the OS toggle mid-session is safe too. */
@media (prefers-reduced-motion: reduce) {
  [data-tarot-spread="root"] .spread-card,
  [data-tarot-spread="root"] .spread-card__pose,
  [data-tarot-spread="root"] .spread-card__inner,
  [data-tarot-spread="root"] .tarot-spread__reveal {
    transition: none !important;
    animation: none !important;
  }
}
`;
