'use client';

/**
 * Inner client view for `/me/history/[id]` (ISSUE-066, Screen 19).
 *
 * Lives in a sibling module to the route's `page.tsx` because Next 15
 * forbids any named exports from a Page module other than the small
 * set of route-config symbols (metadata, generateStaticParams, etc.).
 * The page module imports this view and adapts Next's async `params`
 * Promise to the sync object the view expects.
 *
 * The vitest page test renders this component directly so the test
 * can pass an injected `fetchImpl` without having to fake a Promise.
 *
 * ISSUE-104: expired-blob copy migrated from the system-tone "이 풀이는
 * 더 이상 재생할 수 없습니다" (ISSUE-066 baseline) to "이 풀이는 이제 다시
 * 못 들어." — 누님 voice, soft refusal, same informational payload. The
 * ISSUE-097 file-level bypass marker was removed; the file now passes
 * `pnpm copy:lint` cleanly without an exemption.
 */

import { useRouter } from 'next/navigation';
import { useCallback, useEffect, useRef, useState } from 'react';

import { TopAppBar } from '@/components/nav/TopAppBar';
import { HistoryFetchError, probeReadingAudio, readingAudioUrl } from '@/lib/api/history';

type LoadState =
  | { kind: 'loading' }
  | { kind: 'error'; message: string }
  | { kind: 'expired' }
  | { kind: 'loaded' };

export interface MeHistoryItemViewProps {
  params: { id: string };
  /**
   * Test hook: inject a fake fetch so the page can run under vitest's
   * jsdom environment without hitting the network. Production passes
   * the global `fetch`.
   */
  fetchImpl?: typeof fetch;
}

/**
 * Backwards-compat alias retained for any out-of-tree consumers.
 */
export type MeHistoryItemPageProps = MeHistoryItemViewProps;

/**
 * Format the archive ribbon copy from a reading id + started_at-ish
 * ISO timestamp. The page does not have the timestamp until a future
 * iteration (it would require an extra GET /me/readings/{id}), so we
 * fall back to a static "[풀이]" label. The list page (when it lands)
 * will pass the timestamp via query string.
 */
function formatArchiveRibbon(searchParams: URLSearchParams): string {
  const isoDate = searchParams.get('d');
  if (isoDate && /^\d{4}-\d{2}-\d{2}$/.test(isoDate)) {
    return `[${isoDate}] 풀이`;
  }
  return '[풀이]';
}

export function MeHistoryItemView({ params, fetchImpl }: MeHistoryItemViewProps) {
  const router = useRouter();
  const [state, setState] = useState<LoadState>({ kind: 'loading' });

  // Same routerRef pattern as /me/saju (ISSUE-064): the vitest mock
  // returns a fresh router object per render, so wiring the load
  // callback to `router` directly causes an infinite re-render.
  const routerRef = useRef(router);
  routerRef.current = router;

  const fetchRef = useRef(fetchImpl);
  fetchRef.current = fetchImpl;

  const load = useCallback(async () => {
    setState({ kind: 'loading' });
    try {
      const result = await probeReadingAudio(params.id, fetchRef.current ?? fetch);
      if (result.available) {
        setState({ kind: 'loaded' });
      } else {
        setState({ kind: 'expired' });
      }
    } catch (err) {
      if (err instanceof HistoryFetchError && err.status === 401) {
        routerRef.current.replace('/auth/login');
        return;
      }
      if (err instanceof HistoryFetchError && err.status === 404) {
        // The reading does not exist or is not owned by the caller.
        // Bounce back to /me rather than rendering an in-page 404 so
        // direct URL guessing isn't rewarded with a useful surface.
        routerRef.current.replace('/me');
        return;
      }
      setState({ kind: 'error', message: '잠시 후 다시 시도해주세요' });
    }
  }, [params.id]);

  useEffect(() => {
    void load();
  }, [load]);

  const ribbon =
    typeof window !== 'undefined'
      ? formatArchiveRibbon(new URLSearchParams(window.location.search))
      : '[풀이]';

  if (state.kind === 'loading') {
    return (
      <div className="flex min-h-screen flex-col bg-ink-900 text-cream-100">
        <TopAppBar title="풀이 다시 듣기" />
        <main
          className="mx-auto flex w-full max-w-md flex-1 flex-col items-center justify-center px-s4 py-s8"
          aria-busy
          data-testid="me-history-loading"
        >
          <span className="sr-only">로딩 중</span>
        </main>
      </div>
    );
  }

  if (state.kind === 'error') {
    return (
      <div className="flex min-h-screen flex-col bg-ink-900 text-cream-100">
        <TopAppBar title="풀이 다시 듣기" />
        <main
          className="mx-auto flex w-full max-w-md flex-1 flex-col items-center justify-center gap-s4 px-s4 py-s8"
          data-testid="me-history-error"
        >
          <p className="font-body text-sm text-cream-300">{state.message}</p>
          <button
            type="button"
            onClick={() => {
              void load();
            }}
            className="rounded-md border border-ink-700 px-s4 py-s2 font-body text-sm text-cream-50 hover:bg-ink-800"
            data-testid="me-history-retry"
          >
            다시 시도
          </button>
        </main>
      </div>
    );
  }

  if (state.kind === 'expired') {
    return (
      <div className="flex min-h-screen flex-col bg-ink-900 text-cream-100">
        <TopAppBar title="풀이 다시 듣기" />
        <main
          className="mx-auto flex w-full max-w-md flex-1 flex-col items-center justify-center gap-s4 px-s4 py-s8"
          data-testid="me-history-expired"
        >
          <p className="font-body text-base text-cream-200">이 풀이는 이제 다시 못 들어.</p>
          <a
            href="/me"
            className="rounded-md border border-ink-700 px-s4 py-s2 font-body text-sm text-cream-50 hover:bg-ink-800"
            data-testid="me-history-back-link"
          >
            마이페이지로
          </a>
        </main>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen flex-col bg-ink-900 text-cream-100">
      <TopAppBar title="풀이 다시 듣기" />
      <main
        className="mx-auto flex w-full max-w-md flex-1 flex-col gap-s6 px-s4 py-s6"
        data-testid="me-history-loaded"
      >
        <div
          className="rounded-md border border-amber-700/50 bg-amber-900/20 px-s4 py-s2 text-center font-display text-sm text-amber-200"
          data-testid="me-history-ribbon"
        >
          {ribbon}
        </div>

        {/*
          Native <audio controls> handles pause / resume / seek per AC3.
          The browser will issue a GET against `src` on mount; our
          ``probe`` already verified the blob exists so we can rely on
          a successful 200 response.
        */}
        <audio
          controls
          preload="auto"
          src={readingAudioUrl(params.id)}
          className="w-full"
          aria-label="풀이 음성"
          data-testid="me-history-audio"
        >
          <track kind="captions" />
        </audio>
      </main>
    </div>
  );
}
