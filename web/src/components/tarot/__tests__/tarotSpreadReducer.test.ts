/**
 * Unit tests for the TarotSpread state-machine reducer (ISSUE-094).
 *
 * The reducer is the single source of truth for the visual cascade
 * described in interactions.md §Flow C (v2):
 *
 *   idle ──tap(i)──▶ moving ──animationend──▶ centered
 *        ──animationend──▶ pressed ──transitionend──▶ revealed
 *
 * Reduced-motion shortcut: tap on `prefersReducedMotion=true` jumps
 * directly from `idle` to `revealed` (no choreography).
 *
 * Why a reducer (not chained `setTimeout`s):
 * - The issue's AC explicitly forbids relying on timer chains because
 *   they break for users with `prefers-reduced-motion: reduce` (the
 *   transitions never fire, so the chain stalls). A reducer driven by
 *   `animationend`/`transitionend` events (or by a `forceReveal` action
 *   for reduced-motion) cleanly handles both paths.
 *
 * AC coverage (ISSUE-094):
 * - AC2 — tap cascade reaches `revealed` only through the four-stage
 *   sequence (`moving`/`centered`/`pressed`/`revealed`).
 * - AC3 — `tappedIndex` is preserved across the cascade so determinism
 *   tests can later verify it does NOT influence reveal card art.
 * - Reduced-motion — tap goes straight from `idle` to `revealed`.
 */
import { describe, expect, it } from 'vitest';
import {
  initialSpreadState,
  spreadReducer,
  type SpreadAction,
  type SpreadState,
} from '@/components/tarot/tarotSpreadReducer';

function play(state: SpreadState, actions: SpreadAction[]): SpreadState {
  return actions.reduce((s, a) => spreadReducer(s, a), state);
}

describe('spreadReducer (ISSUE-094 state machine)', () => {
  it('starts in `idle` with no tapped index', () => {
    expect(initialSpreadState).toEqual({ phase: 'idle', tappedIndex: null });
  });

  it('AC2 — full cascade: idle → moving → centered → pressed → revealed', () => {
    const result = play(initialSpreadState, [
      { type: 'tap', index: 2 },
      { type: 'moveDone' },
      { type: 'centerDone' },
      { type: 'flipDone' },
    ]);
    expect(result).toEqual({ phase: 'revealed', tappedIndex: 2 });
  });

  it('AC2 — phases transition in the documented order', () => {
    let state = initialSpreadState;
    state = spreadReducer(state, { type: 'tap', index: 0 });
    expect(state.phase).toBe('moving');
    state = spreadReducer(state, { type: 'moveDone' });
    expect(state.phase).toBe('centered');
    state = spreadReducer(state, { type: 'centerDone' });
    expect(state.phase).toBe('pressed');
    state = spreadReducer(state, { type: 'flipDone' });
    expect(state.phase).toBe('revealed');
  });

  it('AC3 — tappedIndex is preserved across every transition', () => {
    let state = initialSpreadState;
    for (const index of [0, 1, 2, 3, 4]) {
      // Reset (treat as a fresh session) before tapping the next index.
      state = initialSpreadState;
      state = spreadReducer(state, { type: 'tap', index });
      state = spreadReducer(state, { type: 'moveDone' });
      state = spreadReducer(state, { type: 'centerDone' });
      state = spreadReducer(state, { type: 'flipDone' });
      expect(state.tappedIndex).toBe(index);
      expect(state.phase).toBe('revealed');
    }
  });

  it('reduced-motion shortcut: tap → forceReveal jumps to `revealed`', () => {
    const state = play(initialSpreadState, [{ type: 'tap', index: 3 }, { type: 'forceReveal' }]);
    expect(state).toEqual({ phase: 'revealed', tappedIndex: 3 });
  });

  it('forceReveal is also valid from `idle` (reduced-motion immediate tap path)', () => {
    // Some callers prefer to dispatch forceReveal directly when they know
    // motion is reduced — the reducer must accept it from any non-revealed phase.
    const state = spreadReducer(
      { phase: 'idle', tappedIndex: null },
      { type: 'forceReveal', index: 4 },
    );
    expect(state).toEqual({ phase: 'revealed', tappedIndex: 4 });
  });

  it('ignores duplicate taps once a tap is in flight (debounce)', () => {
    // The first tap latches `tappedIndex`. A second tap during the
    // moving/centered/pressed cascade must NOT swap the latched index
    // — otherwise the reveal could swap cards mid-flip.
    let state = spreadReducer(initialSpreadState, { type: 'tap', index: 1 });
    state = spreadReducer(state, { type: 'tap', index: 4 });
    expect(state.tappedIndex).toBe(1);
    expect(state.phase).toBe('moving');
  });

  it('transition events from the wrong phase are no-ops (defensive)', () => {
    // If `transitionend` fires before `tap` (e.g., a stray browser event),
    // the reducer must not advance phase silently — that would lock the
    // UI into `centered` without any visible cards moving.
    const state = spreadReducer(initialSpreadState, { type: 'moveDone' });
    expect(state).toEqual(initialSpreadState);
  });

  it('reset returns the reducer to `idle`', () => {
    const reset = play(initialSpreadState, [{ type: 'tap', index: 2 }, { type: 'reset' }]);
    expect(reset).toEqual(initialSpreadState);
  });
});
