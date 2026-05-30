/**
 * Tests for `useKstMidnightRefresh` (ISSUE-053 / FR-013).
 *
 * The hook schedules a callback at the next KST midnight boundary
 * (Asia/Seoul, 00:00:00). The `/tarot` page uses it to surface a
 * "새로운 카드가 준비됐어요" banner + trigger `router.refresh()` so
 * a stale face-up card from yesterday is replaced with today's
 * face-down hero.
 *
 * Why we test with fake timers + a frozen `Date.now`:
 *   - The hook computes the delay relative to "now" via
 *     `Intl.DateTimeFormat({timeZone: 'Asia/Seoul'})`. Pinning
 *     `Date.now` to a known UTC instant lets us assert the exact
 *     timeout interval.
 *   - `vi.useFakeTimers()` lets us fast-forward to the boundary
 *     without burning real wall-clock time.
 *
 * The two ACs we cover here:
 *   - AC1 (in KST): user with the page open at 23:59:50 KST sees the
 *     callback fire at 00:00:00 KST (10 seconds later).
 *   - AC2 (non-KST): the boundary is independent of the host's IANA
 *     timezone — we simulate a UTC host and assert the same elapsed
 *     interval until KST midnight.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { renderHook } from "@testing-library/react";

import { useKstMidnightRefresh } from "@/lib/hooks/useKstMidnightRefresh";

beforeEach(() => {
  vi.useFakeTimers();
});

afterEach(() => {
  vi.useRealTimers();
});

describe("useKstMidnightRefresh", () => {
  it("AC1 — fires onMidnight at the next KST midnight (10s away)", () => {
    // KST = UTC+9 (no DST). 23:59:50 KST on 2026-05-30 is
    // 14:59:50 UTC on 2026-05-30. Pinning the system clock there
    // means the next KST midnight (2026-05-31 00:00:00 KST =
    // 2026-05-30 15:00:00 UTC) is exactly 10_000 ms away.
    vi.setSystemTime(new Date("2026-05-30T14:59:50.000Z"));

    const onMidnight = vi.fn();
    renderHook(() => useKstMidnightRefresh(onMidnight));

    // Not yet — we haven't crossed the boundary.
    expect(onMidnight).not.toHaveBeenCalled();

    // Advance 9.99s — still before midnight.
    vi.advanceTimersByTime(9_990);
    expect(onMidnight).not.toHaveBeenCalled();

    // Cross the boundary.
    vi.advanceTimersByTime(20);
    expect(onMidnight).toHaveBeenCalledTimes(1);
  });

  it("AC2 — boundary stays at KST midnight regardless of host TZ", () => {
    // Same instant as AC1, but conceptually the host is in UTC. The
    // hook MUST NOT use the host's local "midnight" — it must compute
    // KST 00:00:00 explicitly.
    //
    // We can't easily change `process.env.TZ` mid-test under jsdom +
    // vitest, but we can verify the property indirectly: pin the
    // system clock to an instant where UTC midnight is *before* KST
    // midnight, and assert the timer fires at KST midnight, not UTC.
    //
    // 23:59:50 KST 2026-05-30 = 14:59:50 UTC 2026-05-30. The very
    // next "UTC midnight" (15:00:00 UTC… wait, that's not midnight;
    // the next UTC midnight is 2026-05-31T00:00:00Z which is 9h05m10s
    // away). KST midnight is only 10s away. The hook must pick the
    // 10s figure.
    vi.setSystemTime(new Date("2026-05-30T14:59:50.000Z"));

    const onMidnight = vi.fn();
    renderHook(() => useKstMidnightRefresh(onMidnight));

    // After exactly 10s the callback should fire — proving the hook
    // is using KST, not UTC, as the reset clock.
    vi.advanceTimersByTime(10_000);
    expect(onMidnight).toHaveBeenCalledTimes(1);
  });

  it("does not fire when the component unmounts before midnight", () => {
    vi.setSystemTime(new Date("2026-05-30T14:59:50.000Z"));

    const onMidnight = vi.fn();
    const { unmount } = renderHook(() => useKstMidnightRefresh(onMidnight));

    // Unmount before the boundary.
    unmount();

    // Cross the would-be boundary — no callback expected.
    vi.advanceTimersByTime(30_000);
    expect(onMidnight).not.toHaveBeenCalled();
  });
});
