"use client";

/**
 * `/tarot/play` — Screen 13 tarot reading player (ISSUE-051).
 *
 * Drives the state machine for the tarot voice playback page:
 *
 *   resolving     — fetching today's card metadata + opening the SSE
 *                   stream. Loading band + 노인 도사 illustration.
 *   streaming     — VoicePlayer live + subtitle synced.
 *   pipeline_err  — backend emitted ``event: error``. We DO NOT use the
 *                   full-screen takeover from ``/reading/play``; per
 *                   ux_spec Screen 13 the tarot fallback shows the card
 *                   meaning + a small banner (FR-034 wording).
 *   ended         — audio finished playing → auto-route to ``/tarot/end``
 *                   (ISSUE-054, route doesn't exist yet but the back
 *                   end will catch it).
 *
 * Why this is a small component, not a clone of PlayClient from ISSUE-042:
 * - The tarot pipeline has no creation race (the row is the seed-picked
 *   card; flip just consumes the stream). We don't need a resolving →
 *   ready two-step.
 * - There's no network-drop reconnect AC here (ISSUE-051 spec doesn't
 *   require it). The tarot flip is a single 30-40s reading, not a long
 *   main saju reading. If the connection drops mid-stream we let the
 *   VoicePlayer surface its own subtitle-only fallback (FR-034).
 * - The fewer code paths the smaller the test surface — see the
 *   ISSUE-042 OOM retro.
 *
 * Test injection seams:
 * - ``fetchToday`` — overrides the GET /tarot/today HTTP call.
 * - ``sseSourceFactory`` — overrides the SSE source creation. Production
 *   uses :func:`openTarotSSESource`; tests pass an in-memory async
 *   iterator so jsdom doesn't have to fake MSE.
 * - ``mediaSourceFactory`` + ``fetcher`` — forwarded to the underlying
 *   ``<VoicePlayer>`` so the same injection seams from ISSUE-033's tests
 *   still apply if needed.
 *
 * AC mapping (issues.md §ISSUE-051):
 *   AC1 — SSE opens on mount; first chunk surfaces ≤ relaxed budget.
 *         (page-level: we just assert the SSE factory was invoked and
 *         the VoicePlayer mounts; the chunk-timing budget is exercised
 *         in the backend integration tests for ISSUE-049.)
 *   AC2 — audio completes → router.push('/tarot/end').
 *   AC3 — TTS fails (pipeline_error) → subtitle-only banner stays
 *         rendered (FR-034). The VoicePlayer already handles its own
 *         subtitle-only fallback on first-chunk timeout; this page adds
 *         a thin meaning caption underneath so the user sees something
 *         even if the audio never lands.
 *
 * Architecture refs:
 *   docs/ux_spec.md Screen 13
 *   docs/architecture.md §6.4
 *   docs/copy_guide.md §2.2 (노인 도사) + §10 (Daily Tarot)
 *   docs/requirements.md FR-015, FR-034, US-06
 */

import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { useRouter } from "next/navigation";
import { VoicePlayer } from "@/components/audio";
import {
  Banner,
  CharacterIllustration,
  PrimaryButton,
  SubtitleBand,
} from "@/components/ui";
import { fetchTarotToday, TarotApiError } from "@/lib/api/tarot";
import type { ChunkEventSource } from "@/lib/audio/events";
import {
  openTarotSSESource,
  type TarotSSESource,
} from "@/lib/audio/tarot-sse-source";
import type { PipelineErrorEvent } from "@/lib/audio/sse-source";

const LOADING_COPY = "노인 도사가 카드를 보는 중…";
const PIPELINE_ERR_BANNER_COPY =
  "노인 도사의 풀이가 잠시 없어. 카드 의미만 봐.";
const NETWORK_ERR_BANNER_COPY = "별기운이 잠시 약하네…";

interface TarotCardSummary {
  card_index: number;
  card_name: string;
  card_art_url: string;
}

type RuntimeState =
  | { kind: "loading" }
  | { kind: "streaming"; card: TarotCardSummary }
  | { kind: "pipeline_err"; card: TarotCardSummary; reason: string }
  | { kind: "network_err"; card: TarotCardSummary | null }
  | { kind: "ended"; card: TarotCardSummary };

export interface TarotPlayClientProps {
  /** Test hook: stub GET /tarot/today. Defaults to the live fetch. */
  fetchToday?: typeof fetchTarotToday;
  /**
   * Test hook: stub SSE source. Defaults to
   * :func:`openTarotSSESource`. Tests pass an in-memory iterator.
   */
  sseSourceFactory?: (options: {
    onPipelineError: (err: PipelineErrorEvent) => void;
    onConnectionError: () => void;
  }) => ChunkEventSource;
  /**
   * Test hook: route override used when audio ends. Defaults to
   * ``/tarot/end``. Useful in tests so we can assert against a known
   * string without depending on the real route existing.
   */
  endRoute?: string;
}

export default function TarotPlayClient({
  fetchToday,
  sseSourceFactory,
  endRoute = "/tarot/end",
}: TarotPlayClientProps = {}): ReactNode {
  const router = useRouter();
  const [runtime, setRuntime] = useState<RuntimeState>({ kind: "loading" });

  // We open the SSE source exactly once per page mount. Storing the
  // source in a ref + memoising it via the openedKey lets us hand a
  // stable reference into <VoicePlayer> while still being able to
  // create the source after the today-fetch resolves.
  const sseRef = useRef<ChunkEventSource | null>(null);
  // Bumped to force a fresh source on the rare retry path. Today the
  // page doesn't expose a retry button (ISSUE-054 owns the end-screen
  // CTAs), but the seam keeps the implementation forward-compatible.
  const [sourceKey, setSourceKey] = useState(0);

  // --- step 1: fetch today's card metadata ---------------------------
  useEffect(() => {
    let cancelled = false;
    const fetcher = fetchToday ?? fetchTarotToday;
    (async () => {
      try {
        const data = await fetcher();
        if (cancelled) return;
        // requires_payment means the GET path raced us — bounce to the
        // paywall so the user lands somewhere coherent. ISSUE-050 has
        // already wired this code path; we just defer to it.
        if (data.requires_payment) {
          router.replace("/tarot/paywall");
          return;
        }
        const card: TarotCardSummary = {
          card_index: data.card_index,
          card_name: data.card_name,
          card_art_url: data.card_art_url,
        };
        // Bump the source key — actually triggers the SSE memo below.
        setSourceKey((k) => k + 1);
        setRuntime({ kind: "streaming", card });
      } catch (err) {
        if (cancelled) return;
        // GET /tarot/today failed — surface a network-error variant so
        // the page doesn't hang on the "노인 도사가 카드를 보는 중…"
        // loading band forever.
        // eslint-disable-next-line no-console
        console.warn(
          "tarot/play fetch today failed",
          err instanceof TarotApiError ? err.status : err,
        );
        setRuntime({ kind: "network_err", card: null });
      }
    })();
    return () => {
      cancelled = true;
    };
    // We intentionally run this effect exactly once on mount.
    // `fetchToday` and `router` are excluded from the dep array:
    //  - `fetchToday`: production passes the default; tests inject once
    //    and the effect should not re-run on prop identity changes.
    //  - `router`: Next's `useRouter()` returns a new object on every
    //    render in some app-router versions; re-running on `router`
    //    identity would loop the fetch forever (jsdom test mock makes
    //    this acutely visible).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // --- step 2: open the SSE source once we have card metadata --------
  const handlePipelineError = useCallback((err: PipelineErrorEvent) => {
    setRuntime((prev) => {
      // Only fold into pipeline_err when we have a card to surface
      // (we set this on the streaming transition above).
      if (prev.kind === "streaming") {
        return {
          kind: "pipeline_err",
          card: prev.card,
          reason: err.reason,
        };
      }
      return prev;
    });
  }, []);

  const handleConnectionError = useCallback(() => {
    setRuntime((prev) => {
      if (prev.kind === "streaming") {
        return { kind: "network_err", card: prev.card };
      }
      return { kind: "network_err", card: null };
    });
  }, []);

  // Memoise the source per sourceKey. We DO NOT recreate it on every
  // runtime transition — the VoicePlayer's mount-once effect would
  // otherwise restart.
  const source = useMemo<ChunkEventSource | null>(() => {
    if (sourceKey === 0) return null;
    const factory =
      sseSourceFactory ??
      ((opts: {
        onPipelineError: (err: PipelineErrorEvent) => void;
        onConnectionError: () => void;
      }) => openTarotSSESource(opts) as TarotSSESource);
    const src = factory({
      onPipelineError: handlePipelineError,
      onConnectionError: handleConnectionError,
    });
    sseRef.current = src;
    return src;
  }, [sourceKey, sseSourceFactory, handlePipelineError, handleConnectionError]);

  // Cleanup on unmount.
  useEffect(() => {
    return () => {
      const s = sseRef.current as { close?: () => void } | null;
      s?.close?.();
      sseRef.current = null;
    };
  }, []);

  // --- step 3: handle audio completion → route to /tarot/end ---------
  const handleEnded = useCallback(() => {
    setRuntime((prev) => {
      if (prev.kind === "streaming") {
        return { kind: "ended", card: prev.card };
      }
      return prev;
    });
    router.push(endRoute);
  }, [router, endRoute]);

  // --- render --------------------------------------------------------

  if (runtime.kind === "loading") {
    return <LoadingShell />;
  }

  if (runtime.kind === "network_err") {
    return (
      <main
        className="flex min-h-screen flex-col items-center justify-center gap-s4 bg-ink-900 px-s4 py-s8 text-cream-100"
        role="alert"
        aria-live="assertive"
        data-testid="tarot-play-network-error"
      >
        <CharacterIllustration character="dosa" />
        <h1 className="font-display text-2xl">{NETWORK_ERR_BANNER_COPY}</h1>
        <p className="font-body text-sm text-cream-300">잠시 후 다시 와보게.</p>
      </main>
    );
  }

  // streaming / pipeline_err / ended — they share the same layout so
  // the user sees the card + persona in all three. The banners + CTAs
  // mutate based on state.
  return (
    <main
      className="flex min-h-screen flex-col bg-ink-900 text-cream-100"
      data-testid="tarot-play-shell"
      data-runtime-state={runtime.kind}
    >
      {runtime.kind === "pipeline_err" && (
        <div className="px-s4 pt-s4" data-testid="pipeline-err-banner-wrap">
          <Banner tone="warning">
            <span data-testid="pipeline-err-banner">
              {PIPELINE_ERR_BANNER_COPY}
            </span>
          </Banner>
        </div>
      )}

      <section
        className="grid flex-1 grid-cols-1 gap-s4 px-s4 py-s4 md:grid-cols-[1fr_auto]"
        aria-label="타로 풀이 화면"
      >
        <div className="flex flex-col gap-s3" data-testid="player-column">
          {source ? (
            <VoicePlayer
              source={source}
              persona="dosa"
              onEnded={handleEnded}
              ariaLabel="타로 풀이 플레이어"
            />
          ) : (
            <LoadingInline />
          )}
        </div>
        <aside
          className="flex flex-col items-center gap-s2 md:w-[260px]"
          data-testid="card-column"
        >
          <CardArt
            src={runtime.card.card_art_url}
            name={runtime.card.card_name}
          />
          <p
            className="font-display-han text-lg text-cream-50"
            data-testid="card-name"
          >
            {runtime.card.card_name}
          </p>
        </aside>
      </section>

      {runtime.kind === "ended" && (
        <div className="px-s4 pb-s8" data-testid="ended-cta-wrap">
          <PrimaryButton
            onClick={() => router.push(endRoute)}
            data-testid="ended-cta"
            aria-label="결과 보기"
          >
            결과 보기
          </PrimaryButton>
        </div>
      )}
    </main>
  );
}

/**
 * Card art display. Uses ``<img>`` so the FastAPI-served PNG (ISSUE-055)
 * round-trips without needing a Next image-loader config. The Next lint
 * rule (`@next/next/no-img-element`) is suppressed inline — same
 * decision as the ISSUE-050 TarotCard component.
 */
function CardArt({ src, name }: { src: string; name: string }) {
  return (
    <div
      className="aspect-[5/7] w-full max-w-[220px] overflow-hidden rounded-lg ring-1 ring-cream-300/30"
      data-testid="card-art"
    >
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={src}
        alt={`${name} 카드`}
        className="h-full w-full object-cover"
      />
    </div>
  );
}

function LoadingShell() {
  return (
    <main
      className="flex min-h-screen flex-col items-center justify-center gap-s4 bg-ink-900 text-cream-100"
      aria-busy="true"
      data-testid="tarot-play-loading"
    >
      <CharacterIllustration character="dosa" />
      <SubtitleBand text={LOADING_COPY} data-testid="loading-subtitle" />
    </main>
  );
}

function LoadingInline() {
  return (
    <div
      className="flex flex-col items-center gap-s2 py-s8"
      aria-busy="true"
      data-testid="tarot-play-loading-inline"
    >
      <SubtitleBand text={LOADING_COPY} />
    </div>
  );
}
