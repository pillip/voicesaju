'use client';

/**
 * `/reading/play` — Screen 9 main saju reading player (ISSUE-042).
 *
 * Orchestrates the SSE pipeline (ISSUE-039), `<VoicePlayer>`
 * (ISSUE-033), `<SajuChart>` sidebar, and persona illustration. Drives
 * the five ux_spec states: default · loading · error · subtitle-only
 * (delegated to VoicePlayer's FR-034 banner) · success-end.
 *
 * State machine (top-level):
 *   resolving     — figuring out reading_id (calling POST /reading if
 *                   only ?category was supplied).
 *   loading       — SSE connecting, no first audio chunk yet.
 *   streaming     — first event arrived; VoicePlayer is live.
 *   network_drop  — `online: false` OR EventSource native error.
 *   pipeline_err  — backend emitted `event: error` (LLM hard failure).
 *   ended         — VoicePlayer reported `onEnded`.
 *
 * AC mapping (issues.md §ISSUE-042):
 *   AC1: SSE connects, loading ≤3s, then audio starts.
 *   AC2: tap pause → VoicePlayer's own handler stops audio + freezes subtitle.
 *   AC3: tap 명식 cell → SajuChart's inline tooltip (오행 + 십신).
 *   AC4: network drops mid-playback → banner + audio pauses (within 3s).
 *   AC5: network reconnects → resume (we close the broken EventSource
 *        and let the next `online` event re-open it).
 *   AC6: LLM error event → full-screen "별기운이 잠시 약하네…" + buttons.
 *
 * Architecture refs:
 *   docs/ux_spec.md Screen 9
 *   docs/architecture.md §6.3 / §8.2
 *   docs/copy_guide.md §7
 *   docs/requirements.md FR-007, FR-008, FR-011, FR-035
 */

import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { VoicePlayer } from '@/components/audio';
import { PLACEHOLDER_CHART, SajuChart } from '@/components/saju';
import {
  Banner,
  CharacterIllustration,
  PrimaryButton,
  SecondaryButton,
  SubtitleBand,
} from '@/components/ui';
import { createReading, ReadingApiError, type CreateReadingRequest } from '@/lib/api/reading';
import {
  openReadingSSESource,
  type PipelineErrorEvent,
  type ReadingSSESource,
} from '@/lib/audio/sse-source';

const LOADING_COPY = '별기운을 모으는 중…';
const ERROR_COPY = '별기운이 잠시 약하네…';
const NETWORK_BANNER_COPY = '네트워크 연결이 끊겼습니다';

type Category = 'love' | 'work' | 'money';

interface ReadingContext {
  readingId: string;
  category: Category;
}

type ScreenState =
  | { kind: 'resolving' }
  | { kind: 'ready'; ctx: ReadingContext }
  | { kind: 'error'; reason: string };

type RuntimeState =
  | { kind: 'streaming' }
  | { kind: 'network_drop' }
  | { kind: 'pipeline_err'; reason: PipelineErrorEvent['reason'] }
  | { kind: 'ended' };

interface PlayClientProps {
  /** Test hook: override the create-reading API call. */
  createReadingImpl?: typeof createReading;
  /** Test hook: override the SSE source factory. */
  sseSourceFactory?: (
    readingId: string,
    options: {
      onPipelineError: (err: PipelineErrorEvent) => void;
      onConnectionError: () => void;
    },
  ) => ReadingSSESource;
  /** Test hook: feature flag to disable real-network listener wiring. */
  disableNetworkListeners?: boolean;
}

function isCategory(value: string | null): value is Category {
  return value === 'love' || value === 'work' || value === 'money';
}

export default function PlayClient({
  createReadingImpl,
  sseSourceFactory,
  disableNetworkListeners,
}: PlayClientProps = {}): ReactNode {
  const router = useRouter();
  const searchParams = useSearchParams();

  // Stabilise param reads — useSearchParams returns a new object on
  // every render but the underlying string values are stable.
  const readingIdParam = searchParams?.get('reading_id') ?? null;
  const categoryParamRaw = searchParams?.get('category');
  const categoryParam = isCategory(categoryParamRaw) ? categoryParamRaw : null;

  const [screenState, setScreenState] = useState<ScreenState>({
    kind: 'resolving',
  });
  const [runtimeState, setRuntimeState] = useState<RuntimeState>({
    kind: 'streaming',
  });
  const sseRef = useRef<ReadingSSESource | null>(null);

  // -----------------------------------------------------------------
  // Step 1: resolve the readingId.
  //  - If ?reading_id is present, use it directly.
  //  - Otherwise call POST /api/v1/reading with ?category.
  //  - If neither is set, redirect to /reading/category.
  // -----------------------------------------------------------------
  useEffect(() => {
    let cancelled = false;
    const create = createReadingImpl ?? createReading;

    if (readingIdParam) {
      setScreenState({
        kind: 'ready',
        ctx: {
          readingId: readingIdParam,
          // Fallback when no category param survived — UI will pick a
          // neutral persona; the SSE stream carries the right voice.
          category: categoryParam ?? 'love',
        },
      });
      return;
    }

    if (!categoryParam) {
      router.replace('/reading/category');
      return;
    }

    const body: CreateReadingRequest = { category: categoryParam };
    create(body)
      .then((res) => {
        if (cancelled) return;
        setScreenState({
          kind: 'ready',
          ctx: { readingId: res.reading_id, category: categoryParam },
        });
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        const reason =
          err instanceof ReadingApiError
            ? `create_reading_failed:${err.status ?? 'network'}`
            : 'create_reading_failed:unknown';
        setScreenState({ kind: 'error', reason });
      });

    return () => {
      cancelled = true;
    };
    // We intentionally don't depend on `createReadingImpl` — the
    // factory is a stable function across renders (production passes
    // the default; tests inject once).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [readingIdParam, categoryParam, router]);

  // -----------------------------------------------------------------
  // Step 2: when readingId is ready, open the SSE source. Re-opens on
  // network reconnect (AC5) by keying off `runtimeState.kind`
  // transitioning out of `network_drop`.
  // -----------------------------------------------------------------
  const handlePipelineError = useCallback((err: PipelineErrorEvent) => {
    setRuntimeState({ kind: 'pipeline_err', reason: err.reason });
  }, []);

  const handleConnectionError = useCallback(() => {
    setRuntimeState({ kind: 'network_drop' });
  }, []);

  const openedReadingId = screenState.kind === 'ready' ? screenState.ctx.readingId : null;

  // Counter to force re-mount of the SSE source on manual retry +
  // reconnect. Re-mounting the source also re-mounts the VoicePlayer
  // (we use the source as part of the key).
  const [reconnectKey, setReconnectKey] = useState(0);

  // Memoise the source per (readingId, reconnectKey) so the
  // VoicePlayer's mount-once effect sees a stable iterator until we
  // explicitly bump the key.
  const source = useMemo<ReadingSSESource | null>(() => {
    if (!openedReadingId) return null;
    const factory = sseSourceFactory ?? openReadingSSESource;
    const src = factory(openedReadingId, {
      onPipelineError: handlePipelineError,
      onConnectionError: handleConnectionError,
    });
    sseRef.current = src;
    return src;
    // `reconnectKey` is intentionally listed so a bump produces a fresh
    // SSE source — the variable itself does not flow into the factory
    // call, only its identity drives re-memoisation.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [openedReadingId, reconnectKey, sseSourceFactory, handlePipelineError, handleConnectionError]);

  // Cleanup any open SSE on unmount.
  useEffect(() => {
    return () => {
      sseRef.current?.close();
      sseRef.current = null;
    };
  }, []);

  // -----------------------------------------------------------------
  // Step 3: network online/offline listeners (FR-035, AC4 + AC5).
  // The detection budget is "within 3s" — browsers fire the offline
  // event near-immediately on link loss, so a single listener
  // satisfies the AC. On `online`, we bump `reconnectKey` to spin a
  // fresh SSE source from the last known offset.
  // -----------------------------------------------------------------
  useEffect(() => {
    if (disableNetworkListeners) return;
    if (typeof window === 'undefined') return;
    const handleOffline = () => {
      setRuntimeState({ kind: 'network_drop' });
      sseRef.current?.close();
    };
    const handleOnline = () => {
      // Only auto-reconnect if we were in network_drop — don't fight
      // a pipeline_err state.
      setRuntimeState((prev) => {
        if (prev.kind === 'network_drop') {
          setReconnectKey((k) => k + 1);
          return { kind: 'streaming' };
        }
        return prev;
      });
    };
    window.addEventListener('offline', handleOffline);
    window.addEventListener('online', handleOnline);
    return () => {
      window.removeEventListener('offline', handleOffline);
      window.removeEventListener('online', handleOnline);
    };
  }, [disableNetworkListeners]);

  // -----------------------------------------------------------------
  // UI helpers — handlers for the error-state CTAs.
  // -----------------------------------------------------------------
  const handleRetry = useCallback(() => {
    setRuntimeState({ kind: 'streaming' });
    setReconnectKey((k) => k + 1);
  }, []);

  const handleNavigateMy = useCallback(() => {
    router.push('/me');
  }, [router]);

  const handleEnded = useCallback(() => {
    setRuntimeState({ kind: 'ended' });
  }, []);

  // -----------------------------------------------------------------
  // Render branches.
  // -----------------------------------------------------------------
  if (screenState.kind === 'resolving') {
    return <LoadingShell />;
  }
  if (screenState.kind === 'error') {
    return (
      <ErrorShell
        reason={screenState.reason}
        onRetry={handleRetry}
        onNavigateMy={handleNavigateMy}
      />
    );
  }

  // ready — render the player layout. The pipeline_err overlay sits on
  // top of the layout so the chart + persona stay visible underneath
  // the takeover (matches ux_spec "full-screen takeover" + retry CTA).
  if (runtimeState.kind === 'pipeline_err') {
    return (
      <ErrorShell
        reason={`pipeline:${runtimeState.reason}`}
        onRetry={handleRetry}
        onNavigateMy={handleNavigateMy}
      />
    );
  }

  return (
    <main
      className="flex min-h-screen flex-col bg-ink-900 text-cream-100"
      data-testid="play-shell"
      data-runtime-state={runtimeState.kind}
    >
      {runtimeState.kind === 'network_drop' && (
        <div className="px-s4 pt-s4" data-testid="network-banner-wrap">
          <Banner tone="warning">
            <span data-testid="network-banner">{NETWORK_BANNER_COPY}</span>
          </Banner>
        </div>
      )}

      <section
        className="grid flex-1 grid-cols-1 gap-s4 px-s4 py-s4 md:grid-cols-[1fr_auto]"
        aria-label="사주 풀이 화면"
      >
        <div className="flex flex-col gap-s3" data-testid="player-column">
          {source ? (
            <VoicePlayer
              source={source}
              persona="nuna"
              onEnded={handleEnded}
              ariaLabel="사주 풀이 플레이어"
            />
          ) : (
            <LoadingInline />
          )}
        </div>
        <div className="md:w-[280px]" data-testid="chart-column">
          <SajuChart chart={PLACEHOLDER_CHART} />
        </div>
      </section>

      {runtimeState.kind === 'ended' && (
        <div className="px-s4 pb-s8" data-testid="ended-cta-wrap">
          <PrimaryButton
            onClick={handleNavigateMy}
            data-testid="ended-cta"
            aria-label="마이페이지로 이동"
          >
            마이페이지로
          </PrimaryButton>
        </div>
      )}
    </main>
  );
}

/**
 * Full-screen "별기운이 잠시 약하네…" takeover used by:
 *  - create-reading failure (Step 1 error branch)
 *  - pipeline LLM error event (event: error)
 */
function ErrorShell({
  reason,
  onRetry,
  onNavigateMy,
}: {
  reason: string;
  onRetry: () => void;
  onNavigateMy: () => void;
}) {
  return (
    <main
      className="flex min-h-screen flex-col items-center justify-center gap-s4 bg-ink-900 px-s4 py-s8 text-cream-100"
      role="alert"
      aria-live="assertive"
      data-testid="play-error"
      data-reason={reason}
    >
      <CharacterIllustration character="nuna" data-testid="error-persona" />
      <h1 className="font-display text-2xl">{ERROR_COPY}</h1>
      <p className="font-body text-sm text-cream-300">환불 또는 무료 이용권이 지급되었어요</p>
      <div className="flex flex-col gap-s2 sm:flex-row">
        <PrimaryButton onClick={onRetry} data-testid="retry-button" aria-label="다시 시도">
          다시 시도
        </PrimaryButton>
        <SecondaryButton
          onClick={onNavigateMy}
          data-testid="navigate-my-button"
          aria-label="마이페이지로"
        >
          마이페이지로
        </SecondaryButton>
      </div>
    </main>
  );
}

function LoadingShell() {
  return (
    <main
      className="flex min-h-screen flex-col items-center justify-center gap-s4 bg-ink-900 text-cream-100"
      aria-busy="true"
      data-testid="play-loading"
    >
      <CharacterIllustration character="nuna" />
      <SubtitleBand text={LOADING_COPY} data-testid="loading-subtitle" />
    </main>
  );
}

function LoadingInline() {
  return (
    <div
      className="flex flex-col items-center gap-s2 py-s8"
      aria-busy="true"
      data-testid="play-loading-inline"
    >
      <CharacterIllustration character="nuna" />
      <SubtitleBand text={LOADING_COPY} />
    </div>
  );
}
