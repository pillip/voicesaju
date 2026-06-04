/**
 * Landing — `/` (Screen 1) (ISSUE-086, PRD US-01 / US-06).
 *
 * Server-rendered shell:
 *   - Hero illustration placeholder (real art is DEP-XX).
 *   - Tagline + brand wordmark.
 *   - Primary "지금 풀이 받기" CTA → /onboarding/birth-date.
 *   - Secondary "오늘의 타로" CTA → /tarot.
 *   - Trust strip (separate Client component — fails closed silently).
 *
 * Returning-visitor logic + device-ID issuance live in
 * `LandingCtas` (Client island) so the page itself stays cacheable.
 *
 * AC coverage:
 *   1. New visitor → both CTAs ("지금 풀이 받기" + "오늘의 타로") above the
 *      fold. (Default branch in LandingCtas.)
 *   2. Returning visitor with in-progress session → primary CTA swaps to
 *      "이어서 풀이 받기" (detected via the `vs.in_progress` localStorage
 *      marker set by upstream flows like ISSUE-029 / ISSUE-046).
 *   3. Trust strip API failure → counter row hides silently
 *      (TrustStrip swallows the error).
 *
 * Scope-out: SEO meta + OG tags (deferred to a follow-up).
 */

import { LandingCtas } from '@/components/landing/LandingCtas';
import { TrustStrip } from '@/components/landing/TrustStrip';
import { RouteShell } from '@/components/nav/RouteShell';

export default function LandingPage() {
  // RouteShell mounts the landing chrome (brand mark + back affordance)
  // when NEXT_PUBLIC_NAV_V2 is true; pass-through otherwise. ISSUE-096 AC1.
  return (
    <RouteShell>
      <main
        data-testid="landing"
        className="relative flex min-h-screen flex-col items-center justify-between px-6 py-12 text-center"
      >
        {/* Top region — hero illustration + tagline. */}
        <section className="flex w-full max-w-md flex-col items-center gap-6 pt-6">
          {/* Hero illustration placeholder.
           *
           * The real silhouette pair (시니컬 누님 + 노인 도사) lands as
           * DEP-XX; until then we render a minimal pair of stacked
           * silhouette ovals via inline SVG so the layout doesn't shift
           * when the real art drops in.
           */}
          <div
            aria-hidden="true"
            data-testid="hero-illustration"
            className="flex h-48 w-48 items-center justify-center text-cream-200"
          >
            <svg
              viewBox="0 0 120 120"
              xmlns="http://www.w3.org/2000/svg"
              className="h-full w-full"
              role="img"
              aria-label="silhouette placeholder"
            >
              {/* Left silhouette — younger figure (누님). */}
              <ellipse cx="42" cy="48" rx="14" ry="16" fill="currentColor" opacity="0.7" />
              <path d="M28 100 Q42 70 56 100" fill="currentColor" opacity="0.7" />
              {/* Right silhouette — elder figure (도사). */}
              <ellipse cx="80" cy="54" rx="13" ry="15" fill="currentColor" opacity="0.5" />
              <path d="M67 100 Q80 76 93 100" fill="currentColor" opacity="0.5" />
            </svg>
          </div>

          <div className="flex flex-col items-center gap-2">
            <h1 className="font-display text-4xl italic tracking-tight">VoiceSaju</h1>
            <p className="font-display text-lg text-cream-300">
              새벽 3시의 누님이, 직접 풀어줍니다.
            </p>
            <p className="font-body text-sm text-cream-400">목소리로.</p>
          </div>
        </section>

        {/* Center region — CTAs. Client island so it can read
         * localStorage + POST device-ID after mount.
         */}
        <LandingCtas />

        {/* Bottom region — trust strip. */}
        <TrustStrip />
      </main>
    </RouteShell>
  );
}
