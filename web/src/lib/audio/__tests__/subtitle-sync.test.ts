/**
 * Unit tests for `SubtitleSync` (ISSUE-033 / NFR-015).
 *
 * Covers:
 *   - AC2 — subtitle text updates within 500ms of audio offset.
 *   - AC3 — stop() preserves active line (subtitle freezes on pause).
 *   - AC4 — reset() clears the active line so replay starts fresh.
 *   - Out-of-order ingestion still produces correctly-ordered active line.
 *   - Late-arriving subtitle whose offset is already in the past is
 *     promoted on the next event.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  SubtitleSync,
  SUBTITLE_LAG_BUDGET_MS,
  type ActiveSubtitle,
} from "@/lib/audio/subtitle-sync";
import type { SubtitleEvent } from "@/lib/audio/events";

function makeSub(seq: number, text: string, offset_ms: number): SubtitleEvent {
  return { type: "subtitle", seq, text, audio_offset_ms: offset_ms };
}

describe("SubtitleSync — NFR-015 (AC2)", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it("activates a subtitle within 500ms of the playhead reaching audio_offset_ms", () => {
    // Simulated playhead. Start at 0; tests advance via `setNow()`.
    let now = 0;
    const sync = new SubtitleSync({
      getCurrentTimeMs: () => now,
      tickIntervalMs: 100,
    });

    const observed: (ActiveSubtitle | null)[] = [];
    sync.subscribe((active) => observed.push(active));

    // Queue three subtitle events.
    sync.notifyEvent(makeSub(0, "첫번째", 0));
    sync.notifyEvent(makeSub(1, "두번째", 2000));
    sync.notifyEvent(makeSub(2, "세번째", 5000));

    sync.start();

    // At t=0 the first line should be active.
    expect(sync.getActive()?.seq).toBe(0);

    // Advance playhead + tick clock to t=2000ms.
    now = 2000;
    vi.advanceTimersByTime(100);
    // Per NFR-015 the lag must be ≤ 500ms. Our tick cadence is 100ms so
    // worst case is 100ms. With now=2000 exactly the active line is
    // already (seq=1).
    expect(sync.getActive()?.seq).toBe(1);

    // Hop the playhead to just past line 2's offset. Within one tick the
    // active line should advance.
    now = 5050;
    vi.advanceTimersByTime(100);
    expect(sync.getActive()?.seq).toBe(2);

    sync.dispose();
  });

  it("emits lag telemetry that stays within the NFR-015 budget", () => {
    let now = 0;
    const lagSamples: number[] = [];
    const sync = new SubtitleSync({
      getCurrentTimeMs: () => now,
      tickIntervalMs: 100,
      onLagMeasured: (info) => lagSamples.push(info.measured_lag_ms),
    });

    sync.notifyEvent(makeSub(0, "안녕", 0));
    sync.notifyEvent(makeSub(1, "다음 줄", 1000));
    sync.notifyEvent(makeSub(2, "마지막", 3000));
    sync.start();

    // March through the timeline tick-by-tick.
    for (let t = 0; t <= 3500; t += 100) {
      now = t;
      vi.advanceTimersByTime(100);
    }

    expect(lagSamples.length).toBeGreaterThanOrEqual(3);
    for (const lag of lagSamples) {
      expect(lag).toBeLessThanOrEqual(SUBTITLE_LAG_BUDGET_MS);
    }
    sync.dispose();
  });

  it("late-arriving subtitle (offset already in the past) is promoted on notifyEvent", () => {
    let now = 0;
    const sync = new SubtitleSync({
      getCurrentTimeMs: () => now,
      tickIntervalMs: 100,
    });
    sync.start();
    // Playhead is already at 2000ms when a subtitle for offset 1500 arrives.
    now = 2000;
    sync.notifyEvent(makeSub(0, "지각", 1500));
    // No tick advance — the active line should have updated synchronously
    // in notifyEvent's event-driven flush path.
    expect(sync.getActive()?.text).toBe("지각");
    sync.dispose();
  });
});

describe("SubtitleSync — AC3 freeze on pause / AC4 reset on replay", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it("stop() preserves the active line (subtitle freezes at current text)", () => {
    let now = 0;
    const sync = new SubtitleSync({
      getCurrentTimeMs: () => now,
      tickIntervalMs: 100,
    });
    sync.notifyEvent(makeSub(0, "첫번째", 0));
    sync.notifyEvent(makeSub(1, "두번째", 1000));
    sync.start();
    now = 1000;
    vi.advanceTimersByTime(100);
    expect(sync.getActive()?.seq).toBe(1);

    sync.stop();
    // Even if the simulated playhead jumps further, the active line
    // should NOT change because polling is stopped.
    now = 5000;
    vi.advanceTimersByTime(1000);
    expect(sync.getActive()?.seq).toBe(1);
    sync.dispose();
  });

  it("reset() clears the active line so replay starts fresh", () => {
    let now = 0;
    const sync = new SubtitleSync({
      getCurrentTimeMs: () => now,
      tickIntervalMs: 100,
    });
    sync.notifyEvent(makeSub(0, "첫번째", 0));
    sync.notifyEvent(makeSub(1, "두번째", 1000));
    sync.start();
    now = 1000;
    vi.advanceTimersByTime(100);
    expect(sync.getActive()?.seq).toBe(1);

    // User taps replay → playhead jumps back to 0 and sync.reset() fires.
    now = 0;
    sync.reset();
    // After reset, the first line (offset 0) is the active one again.
    expect(sync.getActive()?.seq).toBe(0);
    sync.dispose();
  });
});

describe("SubtitleSync — robustness", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it("handles out-of-order ingestion (seq 1 arrives before seq 0)", () => {
    let now = 0;
    const sync = new SubtitleSync({
      getCurrentTimeMs: () => now,
      tickIntervalMs: 100,
    });
    // Note seq 1 arrives FIRST.
    sync.notifyEvent(makeSub(1, "B", 2000));
    sync.notifyEvent(makeSub(0, "A", 0));
    sync.start();
    expect(sync.getActive()?.text).toBe("A");
    now = 2000;
    vi.advanceTimersByTime(100);
    expect(sync.getActive()?.text).toBe("B");
    sync.dispose();
  });

  it("dedupes duplicate seq", () => {
    const now = 0;
    const sync = new SubtitleSync({
      getCurrentTimeMs: () => now,
      tickIntervalMs: 100,
    });
    sync.notifyEvent(makeSub(0, "First", 0));
    sync.notifyEvent(makeSub(0, "Duplicate", 0));
    sync.start();
    // First-write-wins — the dup is ignored.
    expect(sync.getActive()?.text).toBe("First");
    sync.dispose();
  });
});
