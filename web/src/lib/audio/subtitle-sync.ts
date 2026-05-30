/**
 * Subtitle sync engine (ISSUE-033, NFR-015).
 *
 * Schedules subtitle text to appear within 500ms of the audio playhead
 * reaching each subtitle's `audio_offset_ms`. The component subscribes
 * via `subscribe()` and re-renders whenever the active line changes.
 *
 * NFR-015 says "Subtitle text lag behind audio by ≤ 500ms". We satisfy
 * this with two complementary mechanisms:
 *
 *  1. **Polling tick** — the scheduler reads `getCurrentTimeMs()` on a
 *     regular cadence (default 100ms). Any line whose offset is ≤ now
 *     becomes active. With a 100ms cadence the worst-case lag is one
 *     tick (100ms), well under the 500ms budget.
 *
 *  2. **Event-driven flush** — `notifyEvent(subtitle)` fires the moment
 *     a subtitle event arrives. If the playhead is already past the
 *     line's offset (e.g. the event arrived late), the line is promoted
 *     to active immediately rather than waiting for the next tick.
 *
 * Why a separate module rather than baking into the player?
 *  - Reusable by ISSUE-039's fallback subtitle-only mode where no audio
 *    is playing at all — the scheduler can be driven by a synthetic
 *    monotonic clock (60-WPM cadence per architecture §8.3 FR-034).
 *  - Keeps the player's MSE concerns separate from text rendering.
 *
 * The scheduler holds **all** received subtitles, not a sliding window.
 * Replay (AC4) just calls `reset()` and the same lines play again.
 *
 * Pause behaviour (AC3): the scheduler stops polling but does NOT clear
 * the active line. The component freezes the subtitle band at its
 * current text. Resume re-arms polling.
 */

import type { SubtitleEvent } from "./events";

/**
 * Source of truth for the current audio offset in milliseconds. The
 * React component passes a function that reads `audio.currentTime * 1000`
 * in the live path, or a monotonic synthetic clock in the FR-034
 * subtitle-only fallback path.
 */
export type CurrentTimeMsGetter = () => number;

/**
 * Polling cadence default. 100ms keeps worst-case lag well below the
 * 500ms budget while staying cheap on JSDOM + low-end mobile.
 *
 * Exported so tests can reference the same constant rather than
 * hardcoding numbers.
 */
export const DEFAULT_TICK_INTERVAL_MS = 100;

/**
 * NFR-015 budget. Exported for tests + future telemetry hooks.
 */
export const SUBTITLE_LAG_BUDGET_MS = 500;

/**
 * Optional latency probe. Whenever a subtitle becomes active, we emit
 * the actual measured lag = (now - audio_offset_ms). Tests assert this
 * stays under `SUBTITLE_LAG_BUDGET_MS`. Production can pipe this to
 * analytics for NFR-015 monitoring (out of scope for ISSUE-033).
 */
export type LagObserver = (info: {
  seq: number;
  text: string;
  offset_ms: number;
  measured_lag_ms: number;
}) => void;

export interface SubtitleSyncOptions {
  /** Returns the current playhead position in ms. */
  getCurrentTimeMs: CurrentTimeMsGetter;
  /** Polling cadence; defaults to `DEFAULT_TICK_INTERVAL_MS`. */
  tickIntervalMs?: number;
  /** Lag telemetry hook. */
  onLagMeasured?: LagObserver;
  /**
   * Injectable timer for tests. Defaults to platform setInterval. Note
   * `vi.useFakeTimers()` already monkey-patches the global so most tests
   * leave this alone.
   */
  setIntervalFn?: (cb: () => void, ms: number) => unknown;
  clearIntervalFn?: (handle: unknown) => void;
}

/**
 * The currently-active subtitle line. `null` means "no line yet" — used
 * during the buffering window before the first line's offset is reached.
 */
export interface ActiveSubtitle {
  seq: number;
  text: string;
  offset_ms: number;
}

export type SubtitleObserver = (active: ActiveSubtitle | null) => void;

export class SubtitleSync {
  private lines: SubtitleEvent[] = [];
  private active: ActiveSubtitle | null = null;
  private observers = new Set<SubtitleObserver>();
  private getCurrentTimeMs: CurrentTimeMsGetter;
  private tickIntervalMs: number;
  private intervalHandle: unknown = null;
  private setIntervalFn: (cb: () => void, ms: number) => unknown;
  private clearIntervalFn: (handle: unknown) => void;
  private onLagMeasured?: LagObserver;
  private running = false;
  private disposed = false;

  constructor(options: SubtitleSyncOptions) {
    this.getCurrentTimeMs = options.getCurrentTimeMs;
    this.tickIntervalMs = options.tickIntervalMs ?? DEFAULT_TICK_INTERVAL_MS;
    this.onLagMeasured = options.onLagMeasured;
    this.setIntervalFn =
      options.setIntervalFn ??
      ((cb, ms) => globalThis.setInterval(cb, ms) as unknown);
    this.clearIntervalFn =
      options.clearIntervalFn ??
      ((handle) =>
        globalThis.clearInterval(handle as ReturnType<typeof setInterval>));
  }

  /**
   * Register a callback fired whenever the active subtitle changes.
   * Returns an unsubscribe function. Initial active state is `null`.
   */
  subscribe(observer: SubtitleObserver): () => void {
    this.observers.add(observer);
    // Immediately push current state so subscribers don't miss the
    // first transition if they subscribe after the line was set.
    observer(this.active);
    return () => {
      this.observers.delete(observer);
    };
  }

  /**
   * Ingest a subtitle event from the SSE stream. If the playhead is
   * already past `audio_offset_ms`, promote immediately (event-driven
   * flush). Otherwise the next tick will pick it up.
   */
  notifyEvent(ev: SubtitleEvent): void {
    if (this.disposed) return;
    // Dedup by seq.
    if (this.lines.some((l) => l.seq === ev.seq)) return;
    this.lines.push(ev);
    this.lines.sort((a, b) => a.audio_offset_ms - b.audio_offset_ms);
    // If the playhead is already past this offset, evaluate now so the
    // active line updates within one event loop turn.
    if (this.getCurrentTimeMs() >= ev.audio_offset_ms) {
      this.evaluate();
    }
  }

  /**
   * Start the polling tick. Idempotent. The component calls this on
   * play() and `stop()` on pause(). Reset does not stop polling.
   */
  start(): void {
    if (this.disposed) return;
    if (this.running) return;
    this.running = true;
    // Evaluate once synchronously so subscribers see the initial state
    // without waiting for the first tick.
    this.evaluate();
    this.intervalHandle = this.setIntervalFn(() => {
      this.evaluate();
    }, this.tickIntervalMs);
  }

  /**
   * Stop polling. Active line is preserved — AC3 wants the band to
   * freeze at its current text on pause.
   */
  stop(): void {
    if (!this.running) return;
    this.running = false;
    if (this.intervalHandle !== null) {
      this.clearIntervalFn(this.intervalHandle);
      this.intervalHandle = null;
    }
  }

  /**
   * Reset to offset 0 (AC4 replay). Clears the active line; the next
   * tick will re-pick the first line.
   */
  reset(): void {
    if (this.active !== null) {
      this.active = null;
      this.emit(null);
    }
    // Don't drop `lines` — replay should re-play the same subtitle
    // stream. Just re-evaluate so any line at offset 0 becomes active.
    this.evaluate();
  }

  /** Snapshot accessor. */
  getActive(): ActiveSubtitle | null {
    return this.active;
  }

  dispose(): void {
    this.disposed = true;
    this.stop();
    this.observers.clear();
  }

  // --- internal ---------------------------------------------------------

  /**
   * Find the latest line whose offset ≤ now. That line is the active
   * one. If it differs from current active, emit.
   */
  private evaluate(): void {
    if (this.disposed) return;
    const now = this.getCurrentTimeMs();
    let candidate: SubtitleEvent | null = null;
    for (const line of this.lines) {
      if (line.audio_offset_ms <= now) {
        candidate = line;
      } else {
        // lines is sorted by offset; we can stop early.
        break;
      }
    }
    if (candidate === null) {
      if (this.active !== null) {
        this.active = null;
        this.emit(null);
      }
      return;
    }
    if (this.active?.seq === candidate.seq) return;
    const nextActive: ActiveSubtitle = {
      seq: candidate.seq,
      text: candidate.text,
      offset_ms: candidate.audio_offset_ms,
    };
    this.active = nextActive;
    const lag = Math.max(0, now - candidate.audio_offset_ms);
    this.onLagMeasured?.({
      seq: candidate.seq,
      text: candidate.text,
      offset_ms: candidate.audio_offset_ms,
      measured_lag_ms: lag,
    });
    this.emit(nextActive);
  }

  private emit(active: ActiveSubtitle | null): void {
    for (const observer of this.observers) {
      observer(active);
    }
  }
}
