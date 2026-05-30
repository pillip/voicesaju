"use client";

/**
 * `useKstMidnightRefresh` — fires once at the next KST (Asia/Seoul)
 * midnight (ISSUE-053 / FR-013).
 *
 * The daily-tarot reset clock is KST (`Asia/Seoul`, UTC+9, no DST).
 * When a user keeps the `/tarot` page open past midnight, yesterday's
 * card stays on screen until they manually refresh. This hook fixes
 * that: it schedules a single `setTimeout` for the delta until the
 * next KST midnight and invokes the supplied callback when it fires.
 *
 * The host's local timezone is irrelevant — we compute the boundary
 * using `Intl.DateTimeFormat({timeZone: 'Asia/Seoul'})`. This keeps
 * the implementation dependency-free (no `date-fns-tz`) and behaves
 * correctly on every modern browser, including Toss WebView and the
 * Safari/Chrome combos we ship to.
 *
 * Lifecycle:
 *   - Schedules the timer on mount.
 *   - Clears the timer on unmount (or when the callback identity
 *     changes — see `onMidnight` in the effect deps).
 *   - The hook itself does NOT re-arm after the first fire. The
 *     consumer typically responds by triggering a refresh that
 *     re-mounts the page, which restarts the scheduling cycle. If
 *     you need a recurring timer, wrap with `setInterval` at the
 *     call site.
 */
import { useEffect } from "react";

/**
 * Compute the milliseconds remaining until the next KST midnight
 * (00:00:00 Asia/Seoul) from the supplied UTC instant.
 *
 * Algorithm:
 *   1. Use `Intl.DateTimeFormat` with `timeZone: 'Asia/Seoul'` to
 *      extract the KST calendar year/month/day for the current
 *      instant. This gives us "today" in KST terms.
 *   2. Build tomorrow's KST date components (year/month/day) by
 *      adding one day to that calendar date.
 *   3. Convert "tomorrow 00:00:00 KST" to a UTC instant by treating
 *      it as if it were a UTC wall-clock time and subtracting the KST
 *      offset (UTC+9 → subtract 9 hours). This works because KST has
 *      no DST, so the offset is fixed at +9 hours year-round.
 *   4. Return the delta in ms.
 *
 * Exported for unit-testing convenience and reuse — keeping it pure
 * lets the test file pin `Date.now` and assert the exact delta
 * without going through React.
 */
export function msUntilNextKstMidnight(nowMs: number = Date.now()): number {
  const KST_OFFSET_MS = 9 * 60 * 60 * 1000;

  // Step 1 + 2: read the KST calendar date of "now". The DateTimeFormat
  // ISO parts give us a deterministic 4-2-2 split irrespective of
  // host locale.
  const fmt = new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Seoul",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  });
  const parts = fmt.formatToParts(new Date(nowMs));
  const year = Number(parts.find((p) => p.type === "year")?.value);
  const month = Number(parts.find((p) => p.type === "month")?.value);
  const day = Number(parts.find((p) => p.type === "day")?.value);

  // Step 3: build the UTC instant for "tomorrow 00:00:00 KST".
  // `Date.UTC(year, monthIndex, day+1)` returns the UTC ms for that
  // wall-clock midnight; subtract the KST offset to get the actual
  // UTC instant when KST wall clocks read 00:00:00 the next day.
  // JS Date months are 0-indexed.
  const tomorrowKstAsUtcWall = Date.UTC(year, month - 1, day + 1);
  const tomorrowKstMidnightUtc = tomorrowKstAsUtcWall - KST_OFFSET_MS;

  // Step 4: delta (always positive — we'd only be at-or-past the
  // boundary mid-tick, and even then the next-tick `setTimeout(0)`
  // semantics make a 0/negative delta safe).
  return Math.max(0, tomorrowKstMidnightUtc - nowMs);
}

/**
 * Schedule `onMidnight()` to fire once at the next KST midnight.
 *
 * @param onMidnight - Callback invoked when the boundary is crossed.
 *   Treat the call as a one-shot signal; the hook does not re-arm.
 */
export function useKstMidnightRefresh(onMidnight: () => void): void {
  useEffect(() => {
    const delayMs = msUntilNextKstMidnight();
    const timer = setTimeout(() => {
      onMidnight();
    }, delayMs);

    return () => {
      clearTimeout(timer);
    };
  }, [onMidnight]);
}
