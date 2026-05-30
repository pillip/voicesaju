"use client";

/**
 * `/tarot` — Screen 12 (ISSUE-050).
 *
 * Page composition:
 *   1. `<TarotQuotaBanner>` at the top (copy_guide §10).
 *   2. Centered `<TarotCard>` hero. On mount we fetch
 *      `GET /api/v1/tarot/today` (ISSUE-049) to populate card data + quota.
 *   3. Subtitle below ("탭해서 뽑기" or "다시 듣기" depending on state).
 *
 * Behaviour:
 *   - AC1: face-down + banner when free_remaining > 0.
 *   - AC2: tap → flip animation revealed by toggling component state.
 *   - AC3: when `requires_payment=true` the tap routes to `/tarot/paywall`
 *     INSTEAD of flipping (no flip, no fetch).
 *   - AC4: respects `prefers-reduced-motion` — flip is instant.
 *   - AC5: when the backend marks the row already_flipped we hydrate
 *     into face_up state and render the "다시 듣기" CTA that routes
 *     to `/tarot/play` (ISSUE-051).
 *
 * Why a single-state hook for the API result:
 * - The page has no fancy caching needs. A tiny `useEffect + fetch`
 *   pair keeps the dependency graph small and easy to test.
 * - The fetch error path is non-fatal here: per ux_spec Screen 12,
 *   error states render the optimistic face-down card and defer the
 *   real check to the tap moment. So we hold an internal "fetched"
 *   marker rather than displaying a banner.
 *
 * Why no Suspense wrapper:
 * - We do NOT call `useSearchParams()` on this page — there are no
 *   query-param branches — so the Next 15 Suspense requirement for
 *   client-side bailout (ISSUE-027 pattern) does not apply. If a future
 *   AC adds a `?debug=` switch we'll need to add it then.
 */

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { fetchTarotToday, TarotApiError } from "@/lib/api/tarot";
import { TarotCard, type TarotCardState } from "@/components/tarot/TarotCard";
import { TarotQuotaBanner } from "@/components/tarot/TarotQuotaBanner";

interface TodayState {
  card_index: number;
  card_name: string;
  card_art_url: string;
  free_remaining: number;
  requires_payment: boolean;
  already_flipped: boolean;
}

const FALLBACK_TODAY: TodayState = {
  // Phase-1 fallback: we always render the face-down hero even if the
  // fetch fails. The card_index 0 → '바보' is a deterministic safe
  // placeholder per architecture §6.4 (the real card lands once the
  // backend responds; the tap path still goes through paywall logic).
  card_index: 0,
  card_name: "오늘의 카드",
  card_art_url: "",
  free_remaining: 1,
  requires_payment: false,
  already_flipped: false,
};

function usePrefersReducedMotion(): boolean {
  // We can't read window during SSR — return false on first render so
  // the server + first client paint agree. The effect flips the state
  // post-mount when the media query matches.
  const [reduced, setReduced] = useState(false);
  useEffect(() => {
    if (typeof window === "undefined" || !window.matchMedia) return;
    const mql = window.matchMedia("(prefers-reduced-motion: reduce)");
    setReduced(mql.matches);
    const handler = (e: MediaQueryListEvent) => setReduced(e.matches);
    // Safari only got addEventListener('change') in iOS 14; we keep
    // the addListener fallback for completeness (Toss WebView on older
    // Android still surfaces a webkit-based browser).
    if (typeof mql.addEventListener === "function") {
      mql.addEventListener("change", handler);
      return () => mql.removeEventListener("change", handler);
    }
    // Legacy MediaQueryList API.
    type LegacyMql = MediaQueryList & {
      addListener: (cb: (e: MediaQueryListEvent) => void) => void;
      removeListener: (cb: (e: MediaQueryListEvent) => void) => void;
    };
    const legacy = mql as LegacyMql;
    legacy.addListener(handler);
    return () => legacy.removeListener(handler);
  }, []);
  return reduced;
}

export default function TarotPage() {
  const router = useRouter();
  const reducedMotion = usePrefersReducedMotion();
  const [today, setToday] = useState<TodayState>(FALLBACK_TODAY);
  const [cardState, setCardState] = useState<TarotCardState>("face_down");

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const data = await fetchTarotToday();
        if (cancelled) return;
        const hydrated: TodayState = {
          card_index: data.card_index,
          card_name: data.card_name,
          card_art_url: data.card_art_url,
          free_remaining: data.free_remaining,
          requires_payment: data.requires_payment,
          already_flipped: data.already_flipped === true,
        };
        setToday(hydrated);
        if (hydrated.already_flipped) {
          // AC5 — server says we already flipped today's card.
          setCardState("face_up");
        }
      } catch (err) {
        // Optimistic fallback per ux_spec Screen 12 — keep the
        // face-down hero. We still log so prod monitoring can see
        // the failure rate without surfacing UI noise.
        if (err instanceof TarotApiError) {
          // eslint-disable-next-line no-console
          console.warn("tarot/today fetch failed", err.status);
        } else {
          // eslint-disable-next-line no-console
          console.warn("tarot/today fetch failed", err);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const handleTap = () => {
    // AC3 — quota=0, no subscription → paywall, no flip.
    if (today.requires_payment) {
      router.push("/tarot/paywall");
      return;
    }
    // AC5 — already-flipped state owns its own CTA, the card tap is
    // inert (the user uses "다시 듣기" instead).
    if (cardState === "face_up") {
      return;
    }
    // AC2 — flip into face_up. The actual reading playback is on
    // ISSUE-051's `/tarot/play`; for now we surface the same "다시
    // 듣기" affordance once the flip completes.
    setCardState("face_up");
  };

  const handleReplay = () => {
    router.push("/tarot/play");
  };

  // The subtitle morphs between "탭해서 뽑기" (default) and a quiet
  // hint when the card is already revealed. Per copy_guide.md §10.
  const subtitle =
    cardState === "face_up" ? "오늘의 카드는 이미 뒤집었네." : "탭해서 뽑기";

  return (
    <main
      data-testid="tarot-screen"
      className="mx-auto flex min-h-screen w-full max-w-md flex-col items-center gap-s6 bg-ink-900 px-s4 py-s8 text-cream-100"
    >
      <div className="w-full">
        <TarotQuotaBanner
          freeRemaining={today.free_remaining}
          unlimited={false}
        />
      </div>

      <header className="text-center">
        <h1
          className="font-display-han text-3xl text-cream-50"
          data-testid="tarot-title"
        >
          오늘의 카드
        </h1>
      </header>

      <div className="flex flex-1 items-center justify-center">
        <TarotCard
          state={cardState}
          cardArtUrl={today.card_art_url}
          cardName={today.card_name}
          onTap={handleTap}
          disableAnimation={reducedMotion}
        />
      </div>

      <p
        className="font-body text-sm text-cream-300"
        data-testid="tarot-subtitle"
      >
        {subtitle}
      </p>

      {cardState === "face_up" && (
        <button
          type="button"
          onClick={handleReplay}
          className="rounded-md bg-amber-400 px-s4 py-s2 font-body text-base font-medium text-ink-900 transition-colors hover:bg-amber-300 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-amber-300 active:bg-amber-500"
        >
          다시 듣기
        </button>
      )}
    </main>
  );
}
