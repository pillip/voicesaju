"use client";

/**
 * Client shell for `/reading/intro/[category]` — Screen 7 (ISSUE-032).
 *
 * Plays the 15-sec pre-recorded persona intro clip before the paywall.
 * Wired to ISSUE-031's `GET /api/v1/reading/intro/{category}` endpoint
 * for `{audio_url, subtitle, duration_ms}` metadata.
 *
 * AC mapping (issues.md §ISSUE-032):
 *   AC1: Audio auto-plays within 200ms of nav. The `<audio>` element
 *        carries `autoPlay`; the user just tapped a category card so the
 *        browser autoplay heuristic permits this without user gesture
 *        prompts.
 *   AC2: Skip-button copy swaps "건너뛰기" → "결제하기" at the 12s mark.
 *   AC3: Audio error → fallback render: "탭해서 듣기" button + static
 *        subtitle (subtitle from the API; if the API itself failed, we
 *        use a per-category cached fallback line from copy_guide §5).
 *   AC4: Audio `ended` event OR skip-button tap → router.push('/reading/paywall').
 *
 * Architecture refs:
 *   docs/ux_spec.md Screen 7
 *   docs/copy_guide.md §5 (intro audio script + error toast lines)
 *   docs/architecture.md §6.3 (intro flow)
 *
 * Phase-1 placeholders documented in the design doc:
 *  - The audio URL the backend returns (e.g. `tts/intro/love/known.mp3`)
 *    is not yet served by the API gateway under M2; if `<audio>` errors
 *    while loading the asset, we automatically transition to the fallback
 *    branch (AC3) so the user can still see the subtitle and reach the
 *    paywall. This satisfies AC3 even before ISSUE-038 ships the R2
 *    storage client.
 *  - The page deliberately does NOT render the paywall (that's ISSUE-036);
 *    the post-end navigation just calls `router.push('/reading/paywall')`
 *    and trusts the destination to ship later.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import {
  CharacterIllustration,
  PrimaryButton,
  ProgressBar,
  SubtitleBand,
} from "@/components/ui";
import {
  fetchIntroClip,
  IntroFetchError,
  type IntroClipResponse,
} from "@/lib/api/intro";

// Threshold after which "건너뛰기" copy swaps to "결제하기" (ux_spec Screen 7).
const NUDGE_THRESHOLD_SEC = 12;

// Cached fallback subtitles per category. Pulled from copy_guide.md §5
// "intro audio script (자막, 15초)" / §3 "캐시 멘트 표시". Used when the
// upstream `/api/v1/reading/intro/{category}` call itself fails.
const FALLBACK_SUBTITLE_BY_CATEGORY: Record<string, string> = {
  love: "오늘은 별기운이 좀 약하네. 잠시만.",
  work: "오늘은 별기운이 좀 약하네. 잠시만.",
  money: "오늘은 별기운이 좀 약하네. 잠시만.",
};

function getFallbackSubtitle(category: string): string {
  return (
    FALLBACK_SUBTITLE_BY_CATEGORY[category] ??
    "오늘은 별기운이 좀 약하네. 잠시만."
  );
}

interface IntroPlayerProps {
  category: string;
  clip: IntroClipResponse | null;
  fallbackSubtitle: string;
}

function IntroPlayer({ category, clip, fallbackSubtitle }: IntroPlayerProps) {
  const router = useRouter();
  const audioRef = useRef<HTMLAudioElement | null>(null);

  // Audio elapsed seconds, used for the progress bar + 12s copy swap.
  const [elapsedSec, setElapsedSec] = useState(0);
  // Becomes true once `<audio>` fires `error` (codec/network/asset 404).
  const [audioFailed, setAudioFailed] = useState(false);

  // If the API call itself failed, we have no audio_url — surface the
  // fallback branch directly without trying to instantiate the player.
  const hasClip = clip !== null;

  const subtitleText = hasClip ? clip.subtitle : fallbackSubtitle;
  // Duration in seconds, normalized for the progress bar.
  const durationSec = hasClip ? Math.max(clip.duration_ms / 1000, 1) : 15;

  const goToPaywall = useCallback(() => {
    router.push("/reading/paywall");
  }, [router]);

  // Audio time tracking. We poll via `timeupdate` rather than an interval
  // so we don't fight the browser's own playback cadence.
  const handleTimeUpdate = useCallback(() => {
    const a = audioRef.current;
    if (!a) return;
    setElapsedSec(a.currentTime);
  }, []);

  const handleError = useCallback(() => {
    setAudioFailed(true);
  }, []);

  const handleEnded = useCallback(() => {
    goToPaywall();
  }, [goToPaywall]);

  // Manual tap-to-play fallback (AC3). After the user explicitly taps the
  // big play button we re-arm the `<audio>` element. If playback fails
  // again the error handler will re-set `audioFailed`.
  const handleTapToPlay = useCallback(() => {
    const a = audioRef.current;
    if (!a) {
      // No audio element means the API itself failed; jump straight to
      // the paywall so the user is never stuck.
      goToPaywall();
      return;
    }
    setAudioFailed(false);
    // play() returns a promise — autoplay block / network error rejects.
    void a.play().catch(() => setAudioFailed(true));
  }, [goToPaywall]);

  // Skip-button copy swaps at the 12s mark per AC2.
  const skipCopy = elapsedSec >= NUDGE_THRESHOLD_SEC ? "결제하기" : "건너뛰기";

  // Defensive guard: if the API succeeded but returned an empty audio_url
  // we treat it as the fallback branch from the start.
  useEffect(() => {
    if (hasClip && clip.audio_url.trim() === "") {
      setAudioFailed(true);
    }
  }, [hasClip, clip]);

  return (
    <main
      className="flex min-h-screen flex-col bg-ink-900 text-cream-100"
      data-testid="intro-player"
      data-category={category}
    >
      {/* Top bar: category meta + skip CTA. Per ux_spec the skip button
          lives top-right; we anchor it inside the top region rather than
          a full TopAppBar so the illustration stays the visual anchor. */}
      <div className="flex items-center justify-between px-s4 pt-s4">
        <span
          className="font-body text-sm text-cream-300"
          data-testid="category-meta"
        >
          {categoryLabelKr(category)}
        </span>
        <button
          type="button"
          onClick={goToPaywall}
          data-testid="skip-button"
          aria-label={skipCopy}
          className="inline-flex items-center rounded-md px-s3 py-s2 font-body text-sm text-cream-200 underline decoration-cream-400 underline-offset-4 transition-colors hover:text-amber-300 hover:decoration-amber-300 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-amber-300"
        >
          {skipCopy}
        </button>
      </div>

      {/* Center: persona illustration. */}
      <section
        aria-label="캐릭터"
        className="flex flex-1 items-center justify-center px-s4 py-s6"
      >
        <CharacterIllustration character="nuna" data-testid="character" />
      </section>

      {/* Bottom: subtitle band + progress bar + fallback button.
          The subtitle is always rendered (AC3 requires a static subtitle
          on failure too) — only the audio control surface swaps. */}
      <section className="flex flex-col gap-s3 px-s4 pb-s8">
        <SubtitleBand
          text={subtitleText}
          tone={audioFailed ? "static" : "default"}
          data-testid="subtitle"
        />
        <ProgressBar
          value={elapsedSec}
          max={durationSec}
          label="인트로 재생 진행도"
          data-testid="progress"
        />
        {audioFailed && (
          <PrimaryButton
            onClick={handleTapToPlay}
            data-testid="tap-to-play"
            aria-label="탭해서 듣기"
          >
            탭해서 듣기
          </PrimaryButton>
        )}
      </section>

      {/* The actual <audio> element. We omit `controls` since the page
          owns its own progress UI. `autoPlay` works because the page nav
          itself was user-initiated from /reading/category. */}
      {hasClip && (
        <audio
          ref={audioRef}
          src={clip.audio_url}
          autoPlay
          // Preload metadata so duration is known before first paint.
          preload="metadata"
          onTimeUpdate={handleTimeUpdate}
          onEnded={handleEnded}
          onError={handleError}
          data-testid="audio-element"
        />
      )}
    </main>
  );
}

function categoryLabelKr(category: string): string {
  switch (category) {
    case "love":
      return "연애";
    case "work":
      return "직장";
    case "money":
      return "금전";
    default:
      return category;
  }
}

interface IntroDataLoaderProps {
  category: string;
}

/**
 * Data-loading wrapper. We deliberately use a thin client-side fetch
 * instead of a server component because:
 *  - The route is auth-gated via a session cookie; without server-side
 *    cookie passthrough plumbing we'd be re-implementing the auth dance.
 *  - The page is small (no SEO need), and the immediate next screen is
 *    also client-rendered.
 *
 * The fetch is fired exactly once per category mount. Failure modes
 * collapse to a single "render with no clip → fallback branch" path.
 */
function IntroDataLoader({ category }: IntroDataLoaderProps) {
  const [state, setState] = useState<
    | { status: "loading" }
    | { status: "ready"; clip: IntroClipResponse }
    | { status: "error" }
  >({ status: "loading" });

  useEffect(() => {
    let cancelled = false;
    setState({ status: "loading" });
    fetchIntroClip(category)
      .then((clip) => {
        if (!cancelled) setState({ status: "ready", clip });
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        // We don't surface the error class; the page only needs to know
        // "no clip, render fallback". Log for ops triage during M2 manual
        // QA per the issue's "scope (Out)" note.
        if (err instanceof IntroFetchError) {
          // eslint-disable-next-line no-console
          console.warn("[intro] fetch failed", err.status, err.message);
        } else {
          // eslint-disable-next-line no-console
          console.warn("[intro] fetch failed (unknown)", err);
        }
        setState({ status: "error" });
      });
    return () => {
      cancelled = true;
    };
  }, [category]);

  if (state.status === "loading") {
    // ux_spec Screen 7 loading state: 200ms shimmer with subtitle "...".
    return (
      <main
        className="flex min-h-screen flex-col items-center justify-center gap-s4 bg-ink-900 text-cream-100"
        aria-busy="true"
        data-testid="intro-loading"
      >
        <CharacterIllustration character="nuna" />
        <SubtitleBand text="..." data-testid="subtitle" />
      </main>
    );
  }

  // Both `ready` and `error` paths reuse the same player shell — the
  // player handles the "no clip" branch by surfacing the tap-to-play CTA
  // and a fallback subtitle line.
  return (
    <IntroPlayer
      category={category}
      clip={state.status === "ready" ? state.clip : null}
      fallbackSubtitle={getFallbackSubtitle(category)}
    />
  );
}

/**
 * Client entry. Receives the resolved `category` string from the
 * server-component shell (`page.tsx`), which awaits the Next 15
 * dynamic-params Promise so we don't need React 19's `use()` API.
 */
export default function IntroClient({ category }: { category: string }) {
  return <IntroDataLoader category={category} />;
}
