"use client";

/**
 * `<VoicePlayer>` — chunked audio player UI (ISSUE-033).
 *
 * Wraps `ChunkedPlayer` (MSE) + `SubtitleSync` (NFR-015 timing) inside a
 * React component that renders:
 *
 *   - persona illustration (passed through; defaults to nuna)
 *   - subtitle band (aria-live="polite" so screen readers track changes)
 *   - progress bar (driven by `currentTime` via the audio element)
 *   - pause / play / replay controls
 *   - FR-034 banner when the 5s timeout fires or the player errors
 *
 * AC mapping (issues.md §ISSUE-033):
 *   AC1: `audio_ready` events with chunk URLs → MSE `appendBuffer()`;
 *        playback continues seamlessly.
 *   AC2: `subtitle` event with `{seq, text, audio_offset_ms}` → subtitle
 *        updates within 500ms of audio reaching `audio_offset_ms`.
 *   AC3: tap pause → audio stops, subtitle freezes at current text.
 *   AC4: tap replay → audio restarts from offset 0, subtitle resets.
 *   AC5: no first chunk within 5s → subtitle-only mode + banner
 *        (FR-034 text from `docs/requirements.md`).
 *
 * Scope clarifications:
 *  - The component accepts events via an `AsyncIterable<ChunkEvent>` prop.
 *    Production (ISSUE-039) will pass an SSE adapter; tests pass an
 *    async generator. SSE wiring is OUT OF SCOPE here.
 *  - The "events" contract is defined in `lib/audio/events.ts`.
 *  - MSE codec is `audio/mpeg`; jsdom does not implement MSE so we accept
 *    `mediaSourceFactory` + `fetcher` injection for unit testing.
 *  - `prefers-reduced-motion`: the progress bar's CSS `transition-[width]`
 *    is suppressed via a Tailwind variant on the container.
 */

import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import {
  Banner,
  CharacterIllustration,
  PrimaryButton,
  ProgressBar,
  SecondaryButton,
  SubtitleBand,
  type PersonaKey,
} from "@/components/ui";
import {
  ChunkedPlayer,
  type ChunkFetcher,
  type MediaSourceFactory,
  type PlayerStatus,
} from "@/lib/audio/chunked-player";
import {
  SubtitleSync,
  type ActiveSubtitle,
  type LagObserver,
} from "@/lib/audio/subtitle-sync";
import type {
  ChunkEvent,
  ChunkEventSource,
  SubtitleEvent,
} from "@/lib/audio/events";

/**
 * FR-034 banner copy. Verbatim from `docs/requirements.md` §645.
 */
export const FR_034_BANNER_TEXT =
  "음성 서비스가 일시적으로 불가합니다. 텍스트로 풀이를 제공합니다.";

export interface VoicePlayerProps {
  /**
   * Async iterable of chunk events. Production: SSE adapter from
   * ISSUE-039. Tests: an async generator.
   */
  source: ChunkEventSource;
  /** Persona illustration shown above the subtitle band. */
  persona?: PersonaKey;
  /**
   * Test hook: inject a fake `MediaSource` factory. When omitted the
   * component uses the browser MediaSource. We expose this on the
   * component (rather than only on `ChunkedPlayer`) so tests can mount
   * the full component tree.
   */
  mediaSourceFactory?: MediaSourceFactory;
  /** Test hook: inject a fake chunk fetcher. */
  fetcher?: ChunkFetcher;
  /** Test hook: override the 5s first-chunk timeout. */
  firstChunkTimeoutMs?: number;
  /**
   * Test hook: NFR-015 lag telemetry. Tests assert
   * `measured_lag_ms <= 500`.
   */
  onLagMeasured?: LagObserver;
  /**
   * Fires when playback fully ends (server `end` event + all buffered
   * audio played out). The reading-session page (ISSUE-041) will use
   * this to navigate to follow-up.
   */
  onEnded?: () => void;
  /** Optional aria-label override for the player root. */
  ariaLabel?: string;
}

/**
 * Status fed to the UI. Mirrors `PlayerStatus` plus a `subtitle_only`
 * state which is what the user sees after the 5s timeout or hard error
 * fires.
 */
type UIState = "loading" | "playing" | "paused" | "ended" | "subtitle_only";

function statusToUI(status: PlayerStatus): UIState {
  switch (status) {
    case "idle":
    case "buffering":
      return "loading";
    case "playing":
      return "playing";
    case "paused":
      return "paused";
    case "ended":
      return "ended";
    case "fallback_timeout":
    case "error":
      return "subtitle_only";
  }
}

export function VoicePlayer({
  source,
  persona = "nuna",
  mediaSourceFactory,
  fetcher,
  firstChunkTimeoutMs,
  onLagMeasured,
  onEnded,
  ariaLabel = "음성 플레이어",
}: VoicePlayerProps): ReactNode {
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const playerRef = useRef<ChunkedPlayer | null>(null);
  const syncRef = useRef<SubtitleSync | null>(null);

  // We mirror player state into React so the JSX re-renders on
  // transitions. `playerStatus` drives the UI variant; `activeSubtitle`
  // drives the subtitle band; `elapsedMs` drives the progress bar.
  const [playerStatus, setPlayerStatus] = useState<PlayerStatus>("idle");
  const [activeSubtitle, setActiveSubtitle] = useState<ActiveSubtitle | null>(
    null,
  );
  const [elapsedMs, setElapsedMs] = useState(0);
  // Total duration so the progress bar has a stable max. We approximate
  // it as `last_subtitle_offset_ms + some_slack` because the server does
  // not pre-announce length (streaming). The component starts with a
  // sensible default (60s — main reading lower bound from architecture
  // §8.2) and widens as later subtitles land.
  const [knownDurationMs, setKnownDurationMs] = useState(60_000);

  /**
   * Stable callback that reads the audio element's currentTime in ms.
   * Used by `SubtitleSync` as its clock source. Falls back to the React
   * `elapsedMs` state if the audio element isn't mounted yet (jsdom path).
   */
  const getCurrentTimeMs = useCallback((): number => {
    const a = audioRef.current;
    if (a && Number.isFinite(a.currentTime)) {
      return a.currentTime * 1000;
    }
    return elapsedMs;
  }, [elapsedMs]);

  // Wire up the player + subtitle sync on mount. We deliberately use a
  // ref + a single effect rather than recreating on every render so the
  // MSE source buffer survives state updates.
  useEffect(() => {
    const audio = audioRef.current;
    if (!audio) return;

    const sync = new SubtitleSync({
      getCurrentTimeMs,
      onLagMeasured,
    });
    syncRef.current = sync;

    const player = new ChunkedPlayer({
      audioElement: audio,
      mediaSourceFactory,
      fetcher,
      firstChunkTimeoutMs,
      onStatusChange: (next) => {
        setPlayerStatus(next);
        if (next === "playing") {
          sync.start();
        } else if (
          next === "paused" ||
          next === "ended" ||
          next === "fallback_timeout" ||
          next === "error"
        ) {
          // Pause/end stops polling; fallback_timeout also stops because
          // there is no audio playhead to track. Subtitle-only fallback
          // uses a synthetic clock; out of scope for ISSUE-033 (ISSUE-039
          // will own the synthetic clock pumping for the subtitle-only
          // branch). For unit tests we still want subtitle events to
          // surface in fallback mode — so we leave the lines accessible
          // but stop the polling tick.
          sync.stop();
        }
        if (next === "ended") {
          onEnded?.();
        }
      },
    });
    playerRef.current = player;

    const unsubscribe = sync.subscribe((active) => {
      setActiveSubtitle(active);
    });

    // Pump the event source. We branch by event type so subtitle events
    // route to the sync engine + audio events to the player. `end` is
    // handled by the player; the component is notified via
    // `onStatusChange('ended')`.
    let cancelled = false;
    const pump = async () => {
      try {
        for await (const ev of source) {
          if (cancelled) return;
          if (ev.type === "subtitle") {
            const sub = ev as SubtitleEvent;
            sync.notifyEvent(sub);
            setKnownDurationMs((prev) =>
              Math.max(prev, sub.audio_offset_ms + 5_000),
            );
          } else if (ev.type === "audio_ready") {
            await player.handleAudioReady(ev);
          } else if (ev.type === "end") {
            player.handleEnd();
          }
        }
      } catch (err) {
        // eslint-disable-next-line no-console
        console.warn("[VoicePlayer] event source error", err);
      }
    };
    void pump();

    return () => {
      cancelled = true;
      unsubscribe();
      sync.dispose();
      player.dispose();
      syncRef.current = null;
      playerRef.current = null;
    };
    // We intentionally exclude `source` from deps — the source is an
    // async iterable that should be consumed exactly once. Re-running the
    // effect on every render would restart the player. The caller is
    // expected to stabilise `source` (the test harness does so by
    // creating it inside a `useMemo`; ISSUE-039 will do the same in the
    // SSE adapter).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // currentTime tracking for the progress bar. We use the `timeupdate`
  // DOM event rather than rAF to align with the browser's playback clock.
  useEffect(() => {
    const audio = audioRef.current;
    if (!audio) return;
    const handleTimeUpdate = () => {
      setElapsedMs(audio.currentTime * 1000);
    };
    audio.addEventListener("timeupdate", handleTimeUpdate);
    return () => audio.removeEventListener("timeupdate", handleTimeUpdate);
  }, []);

  // --- imperative controls ---------------------------------------------

  const handlePause = useCallback(() => {
    playerRef.current?.pause();
    // Subtitle freeze is automatic: sync.stop() preserves active line.
  }, []);

  const handlePlay = useCallback(() => {
    void playerRef.current?.play();
  }, []);

  const handleReplay = useCallback(() => {
    void playerRef.current?.replay();
    syncRef.current?.reset();
    syncRef.current?.start();
    setElapsedMs(0);
  }, []);

  // --- render -----------------------------------------------------------

  const ui = statusToUI(playerStatus);
  const showFallbackBanner = ui === "subtitle_only";
  const subtitleText = activeSubtitle?.text ?? "";
  const subtitleTone: "default" | "static" =
    ui === "subtitle_only" ? "static" : "default";

  // Memoise the controls block so the snapshot of which buttons render
  // is stable for tests.
  const controls = useMemo(() => {
    if (ui === "subtitle_only") {
      // FR-034: no audio playback path. Replay is also disabled because
      // there's no audio to restart. Skip + paywall navigation is owned
      // by the parent reading-session screen.
      return null;
    }
    return (
      <div className="flex items-center justify-center gap-s3">
        {ui === "playing" ? (
          <SecondaryButton
            onClick={handlePause}
            aria-label="일시정지"
            data-testid="pause-button"
          >
            일시정지
          </SecondaryButton>
        ) : (
          <SecondaryButton
            onClick={handlePlay}
            aria-label="재생"
            data-testid="play-button"
            disabled={ui === "loading"}
          >
            재생
          </SecondaryButton>
        )}
        <PrimaryButton
          onClick={handleReplay}
          aria-label="처음부터 다시"
          data-testid="replay-button"
        >
          처음부터 다시
        </PrimaryButton>
      </div>
    );
  }, [ui, handlePause, handlePlay, handleReplay]);

  return (
    <section
      aria-label={ariaLabel}
      data-testid="voice-player"
      data-status={ui}
      className="flex w-full flex-col items-center gap-s4 motion-reduce:transition-none"
    >
      <CharacterIllustration character={persona} data-testid="player-persona" />

      {showFallbackBanner && (
        <Banner tone="warning">
          <span data-testid="fallback-banner">{FR_034_BANNER_TEXT}</span>
        </Banner>
      )}

      <SubtitleBand
        text={subtitleText}
        tone={subtitleTone}
        data-testid="subtitle-band"
      />

      <ProgressBar
        value={Math.min(elapsedMs, knownDurationMs)}
        max={knownDurationMs}
        label="재생 진행도"
        data-testid="player-progress"
      />

      {controls}

      {/* The actual media element. We render even in fallback mode so
          the player's MSE attachment retains a valid sink — the audio
          element being detached can leak the MediaSource object URL. */}
      <audio
        ref={audioRef}
        preload="auto"
        // We intentionally omit `controls`/`autoplay` because the
        // component renders its own UI. play() is called explicitly by
        // the player once the first chunk lands.
        aria-hidden
        data-testid="player-audio"
      />
    </section>
  );
}

/**
 * Convenience re-export so consumers can `import { VoicePlayer,
 * type ChunkEvent } from '@/components/audio/VoicePlayer'`.
 */
export type { ChunkEvent };
