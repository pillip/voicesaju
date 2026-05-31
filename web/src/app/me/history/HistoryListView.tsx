"use client";

/**
 * `/me/history` — Screen 18 (ISSUE-065): reading history list.
 *
 * The route's `page.tsx` may not export named symbols other than the
 * Next 15 route-config allowlist, so the implementation + its test
 * surface live here. Page module just imports + renders this view.
 *
 * Layout (top → bottom):
 *   1. TopAppBar with "풀이 히스토리" title (copy_guide §13).
 *   2. Loading shell (aria-busy region) while data fetches.
 *   3. Error shell — "잠시 후 다시 시도해주세요" + retry button — on
 *      any non-401 fetch failure (401 redirects to /auth/login).
 *   4. Empty state — 누님 illustration placeholder + "아직 풀이가 없네.
 *      첫 풀이 받아볼래?" + CTA → `/reading/category` (AC2). The
 *      backend returns `[]` for users with zero readings, so an empty
 *      array is the canonical signal for this state.
 *   5. List state — N `<HistoryReadingRow>` items rendered in the
 *      order returned by the backend (AC1). The backend's
 *      `voicesaju.readings.routers.history.list_my_readings` orders by
 *      `started_at` desc with `id` as a stable tiebreaker, so we don't
 *      re-sort client-side.
 *
 * Row behaviour:
 *   - Available audio (`audio_available === true`) renders as a `<Link>`
 *     to `/me/history/[id]?d=<YYYY-MM-DD>` so the player's archive
 *     ribbon can show the started_at date without an extra GET.
 *   - Expired audio (`audio_available === false`) renders as a non-link
 *     `<div>` with the "재생 불가" pill and `aria-disabled='true'`
 *     (AC3). The whole row is greyed out via `text-cream-500` and the
 *     play icon is hidden so it's visually unclickable.
 *
 * AC mapping (ISSUE-065):
 *   AC1 → 5 readings render in desc order (covered by the
 *         backend's `ORDER BY started_at DESC` + the test).
 *   AC2 → empty array → empty state with 누님 illustration + CTA.
 *   AC3 → audio_available=false → "재생 불가" pill + unclickable.
 *   AC4 → tap an available row → navigate to /me/history/[id].
 */

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

import { TopAppBar } from "@/components/nav/TopAppBar";
import {
  fetchMyReadings,
  HistoryFetchError,
  type ReadingHistoryRow,
} from "@/lib/api/history";

type LoadState =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "loaded"; rows: ReadingHistoryRow[] };

export interface HistoryListViewProps {
  /**
   * Test hook: inject a fake fetch so the page can run under vitest's
   * jsdom environment without hitting the network. Production passes
   * the global `fetch`.
   */
  fetchImpl?: typeof fetch;
}

/** Category → Korean badge label. Falls back to the raw value on miss. */
const CATEGORY_LABEL: Readonly<Record<string, string>> = {
  love: "연애",
  work: "직장",
  money: "금전",
  tarot: "타로",
};

/**
 * Format an ISO timestamp into `YYYY-MM-DD` for the row meta strip.
 *
 * `started_at` is nullable on the backend (rows that never started or
 * predate the migration); we render a friendly "날짜 미상" fallback so
 * the row still ships a screen-reader-readable date string.
 */
function formatDate(iso: string | null): string {
  if (iso === null) return "날짜 미상";
  // Crop to YYYY-MM-DD without parsing through `Date` so timezone
  // shifts don't move the calendar day. The backend always emits a
  // timezone suffix, so the prefix is stable.
  const match = /^(\d{4}-\d{2}-\d{2})/.exec(iso);
  return match?.[1] ?? "날짜 미상";
}

export function HistoryListView({ fetchImpl }: HistoryListViewProps) {
  const router = useRouter();
  const [state, setState] = useState<LoadState>({ kind: "loading" });

  // Same routerRef pattern as /me/saju + /me/history/[id]: vitest mocks
  // useRouter() per render, so referencing `router` from a callback
  // would force the effect to re-fire on every render.
  const routerRef = useRef(router);
  routerRef.current = router;

  const fetchRef = useRef(fetchImpl);
  fetchRef.current = fetchImpl;

  const load = useCallback(async () => {
    setState({ kind: "loading" });
    try {
      const rows = await fetchMyReadings(1, fetchRef.current ?? fetch);
      setState({ kind: "loaded", rows });
    } catch (err) {
      if (err instanceof HistoryFetchError && err.status === 401) {
        routerRef.current.replace("/auth/login");
        return;
      }
      setState({
        kind: "error",
        message: "잠시 후 다시 시도해주세요",
      });
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  if (state.kind === "loading") {
    return (
      <div className="flex min-h-screen flex-col bg-ink-900 text-cream-100">
        <TopAppBar title="풀이 히스토리" />
        <main
          className="mx-auto flex w-full max-w-md flex-1 flex-col items-center justify-center px-s4 py-s8"
          aria-busy
          data-testid="me-history-list-loading"
        >
          <span className="sr-only">로딩 중</span>
        </main>
      </div>
    );
  }

  if (state.kind === "error") {
    return (
      <div className="flex min-h-screen flex-col bg-ink-900 text-cream-100">
        <TopAppBar title="풀이 히스토리" />
        <main
          className="mx-auto flex w-full max-w-md flex-1 flex-col items-center justify-center gap-s4 px-s4 py-s8"
          data-testid="me-history-list-error"
        >
          <p className="font-body text-sm text-cream-300">{state.message}</p>
          <button
            type="button"
            onClick={() => {
              void load();
            }}
            className="rounded-md border border-ink-700 px-s4 py-s2 font-body text-sm text-cream-50 hover:bg-ink-800"
            data-testid="me-history-list-retry"
          >
            다시 시도
          </button>
        </main>
      </div>
    );
  }

  if (state.rows.length === 0) {
    return (
      <div className="flex min-h-screen flex-col bg-ink-900 text-cream-100">
        <TopAppBar title="풀이 히스토리" />
        <main
          className="mx-auto flex w-full max-w-md flex-1 flex-col items-center justify-center gap-s4 px-s4 py-s8 text-center"
          data-testid="me-history-list-empty"
        >
          {/* Phase-1 placeholder for the 누님 illustration (ux_spec
              Screen 18 empty state). The dedicated SVG asset lands in
              the M6 polish pass; until then we render an accessible
              ASCII glyph so the test can assert presence without
              requiring an image fixture. */}
          <div
            aria-hidden="true"
            className="text-5xl text-amber-200"
            data-testid="me-history-list-empty-illustration"
          >
            ✦
          </div>
          <p className="font-display-han text-xl text-cream-50">
            아직 풀이가 없네. 첫 풀이 받아볼래?
          </p>
          <Link
            href="/reading/category"
            className="rounded-md bg-amber-400 px-s4 py-s2 font-body text-sm font-medium text-ink-900 hover:bg-amber-300"
            data-testid="me-history-list-empty-cta"
          >
            카테고리 고르러
          </Link>
        </main>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen flex-col bg-ink-900 text-cream-100">
      <TopAppBar title="풀이 히스토리" />
      <main
        className="mx-auto flex w-full max-w-md flex-1 flex-col gap-s3 px-s4 py-s6"
        data-testid="me-history-list-loaded"
      >
        <ul
          className="flex flex-col divide-y divide-ink-700 rounded-md border border-ink-700 bg-ink-800"
          data-testid="me-history-list"
          aria-label="풀이 히스토리 목록"
        >
          {state.rows.map((row) => (
            <li key={row.id}>
              <HistoryReadingRow row={row} />
            </li>
          ))}
        </ul>
      </main>
    </div>
  );
}

interface HistoryReadingRowProps {
  row: ReadingHistoryRow;
}

/**
 * One row in the history list.
 *
 * Available audio: `<Link>` → `/me/history/[id]?d=<date>`. The `d`
 * query string lets the player render its archive ribbon without an
 * extra fetch.
 *
 * Expired audio: `<div>` with `aria-disabled="true"` + "재생 불가" pill.
 * No tap target — the link is not rendered at all so screen readers
 * announce a static row rather than a "broken" link.
 */
function HistoryReadingRow({ row }: HistoryReadingRowProps) {
  const dateStr = formatDate(row.started_at);
  const categoryLabel = CATEGORY_LABEL[row.category] ?? row.category;
  const summary = row.summary ?? "";
  const baseClass =
    "flex items-center justify-between gap-s2 px-s4 py-s3 font-body text-sm";
  const enabledClass = `${baseClass} text-cream-50 hover:bg-ink-700`;
  const disabledClass = `${baseClass} text-cream-500`;

  const content = (
    <>
      <div className="flex min-w-0 flex-1 flex-col gap-s1">
        <div className="flex items-center gap-s2">
          <span
            className="inline-flex rounded-full border border-amber-700 bg-amber-900/30 px-s2 py-px font-display text-xs text-amber-200"
            data-testid={`me-history-row-category-${row.id}`}
          >
            {categoryLabel}
          </span>
          <span
            className="font-display text-xs text-cream-300"
            data-testid={`me-history-row-date-${row.id}`}
          >
            {dateStr}
          </span>
        </div>
        {summary.length > 0 && (
          <span
            className="truncate text-cream-200"
            data-testid={`me-history-row-summary-${row.id}`}
          >
            {summary}
          </span>
        )}
      </div>
      {row.audio_available ? (
        <span
          aria-hidden="true"
          className="text-base text-cream-300"
          data-testid={`me-history-row-play-${row.id}`}
        >
          ▷
        </span>
      ) : (
        <span
          className="inline-flex rounded-full border border-ink-600 bg-ink-700 px-s2 py-px font-display text-xs text-cream-400"
          data-testid={`me-history-row-disabled-pill-${row.id}`}
        >
          재생 불가
        </span>
      )}
    </>
  );

  if (!row.audio_available) {
    return (
      <div
        className={disabledClass}
        aria-disabled="true"
        data-testid={`me-history-row-${row.id}`}
      >
        {content}
      </div>
    );
  }

  // Encode just the YYYY-MM-DD slice (formatDate already cropped it)
  // unless we're on the "날짜 미상" fallback path. The player view
  // checks the regex and ignores the query when malformed.
  const queryDate = /^\d{4}-\d{2}-\d{2}$/.test(dateStr) ? dateStr : "";
  const href = queryDate
    ? `/me/history/${row.id}?d=${queryDate}`
    : `/me/history/${row.id}`;

  return (
    <Link
      href={href}
      className={enabledClass}
      data-testid={`me-history-row-${row.id}`}
    >
      {content}
    </Link>
  );
}
