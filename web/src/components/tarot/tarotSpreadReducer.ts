/**
 * State machine for the v2 `<TarotSpread>` cascade (ISSUE-094).
 *
 * Single source of truth for the visual sequence documented in
 * interactions.md §Flow C (Tarot Reveal v2):
 *
 *   idle ──tap(i)──▶ moving ──animationend──▶ centered
 *        ──animationend──▶ pressed ──transitionend──▶ revealed
 *
 * Why a reducer:
 * - The AC explicitly forbids relying on `setTimeout` chains because
 *   they break for `prefers-reduced-motion: reduce` users (transitions
 *   never fire → the chain stalls). A reducer driven by DOM events
 *   (`animationend`, `transitionend`) handles both motion paths
 *   uniformly. The reduced-motion path uses `forceReveal` to jump
 *   straight to `revealed`.
 *
 * - Latching `tappedIndex` on the first tap (and ignoring subsequent
 *   taps until reset) preserves FR-013 determinism at the UI level —
 *   the user cannot swap cards mid-flip.
 *
 * The reducer is intentionally tiny and pure so it can be unit tested
 * without React. The component test exercises the DOM observability;
 * the reducer test exercises the algebra.
 */

export type SpreadPhase = 'idle' | 'moving' | 'centered' | 'pressed' | 'revealed';

export interface SpreadState {
  phase: SpreadPhase;
  /** null until the user taps; otherwise the latched 0..4 index. */
  tappedIndex: number | null;
}

export type SpreadAction =
  | { type: 'tap'; index: number }
  | { type: 'moveDone' }
  | { type: 'centerDone' }
  | { type: 'flipDone' }
  | { type: 'forceReveal'; index?: number }
  | { type: 'reset' };

export const initialSpreadState: SpreadState = {
  phase: 'idle',
  tappedIndex: null,
};

export function spreadReducer(state: SpreadState, action: SpreadAction): SpreadState {
  switch (action.type) {
    case 'tap': {
      // Debounce: only the first tap (from `idle`) latches.
      if (state.phase !== 'idle') return state;
      return { phase: 'moving', tappedIndex: action.index };
    }
    case 'moveDone': {
      // Defensive: ignore stray events from the wrong phase.
      if (state.phase !== 'moving') return state;
      return { ...state, phase: 'centered' };
    }
    case 'centerDone': {
      if (state.phase !== 'centered') return state;
      return { ...state, phase: 'pressed' };
    }
    case 'flipDone': {
      if (state.phase !== 'pressed') return state;
      return { ...state, phase: 'revealed' };
    }
    case 'forceReveal': {
      // Reduced-motion shortcut. If the caller hadn't tapped yet
      // (state.tappedIndex === null), accept an explicit index payload.
      if (state.phase === 'revealed') return state;
      const index = state.tappedIndex !== null ? state.tappedIndex : (action.index ?? 0);
      return { phase: 'revealed', tappedIndex: index };
    }
    case 'reset': {
      return initialSpreadState;
    }
    default: {
      // Exhaustiveness — if a new action lands here TypeScript will
      // flag the missing case at the call site.
      const _exhaustive: never = action;
      void _exhaustive;
      return state;
    }
  }
}
