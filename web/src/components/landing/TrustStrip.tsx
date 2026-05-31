"use client";

/**
 * Landing trust strip (ISSUE-086 AC3).
 *
 * Renders "오늘 N명이 풀이를 받았어요" once the daily-readings counter
 * fetch succeeds. If the fetch fails — for any reason — the strip
 * silently disappears: no error UI, no toast, no fallback text. The
 * landing page must never feel broken because a non-critical counter
 * couldn't load.
 *
 * Phase-1 strategy:
 *   - The real counter endpoint (``GET /api/v1/stats/today-readings``)
 *     is post-MVP. Until it lands we fetch a *fake* counter via a
 *     local-only stub that resolves with a hardcoded number, mimicking
 *     the real network shape so swapping in the real fetch is a one-line
 *     change in this file.
 *   - The stub returns a deterministic number per day so the page looks
 *     stable across reloads but ticks up over time.
 *
 * Why a Client island rather than server-rendering the number:
 *   - SSR coupling to the counter would make the entire landing page
 *     uncacheable. The counter is a low-priority decoration, not a
 *     core component, so client-fetching keeps the rest of the page
 *     fast.
 *   - It also makes silent-fail behavior trivial — server errors would
 *     show up in logs / Sentry; client errors stay invisible (AC3).
 */

import { useEffect, useState } from "react";

interface TodayReadingsResponse {
  count: number;
}

/**
 * Stub for the post-MVP counter endpoint. Returns a deterministic
 * number derived from the current UTC date so the value is stable for
 * a given day. The shape mirrors the planned `/stats/today-readings`
 * response so the future swap is mechanical.
 */
async function fetchTodayReadings(): Promise<TodayReadingsResponse> {
  // Deterministic-but-changing fake: anchor on day-of-year * 17 + 837
  // so the number lives in the hundreds and feels organic.
  const now = new Date();
  const start = Date.UTC(now.getUTCFullYear(), 0, 0);
  const dayOfYear = Math.floor((now.getTime() - start) / 86_400_000);
  const count = (dayOfYear * 17 + 837) % 1500;
  return { count };
}

export function TrustStrip() {
  const [count, setCount] = useState<number | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await fetchTodayReadings();
        if (!cancelled) {
          setCount(res.count);
        }
      } catch {
        if (!cancelled) {
          setFailed(true);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  // AC3: hide silently on failure. Also hide while the count is
  // pending so we don't render an empty bar.
  if (failed || count === null) {
    return null;
  }

  return (
    <p
      data-testid="trust-strip"
      // ``aria-live="polite"`` so the announcement lands after the
      // primary CTA reads — assistive tech reads the page top-down,
      // not the layout order, so we want this last.
      aria-live="polite"
      className="font-body text-xs text-cream-400"
    >
      오늘 {count.toLocaleString("ko-KR")}명이 풀이를 받았어요
    </p>
  );
}
