/**
 * Server-component shell for `/reading/end` (ISSUE-059 — Screen 11).
 *
 * `<EndClient>` reads `?slug` + `?member` via `useSearchParams()`. Per
 * Next 15's App Router contract, any client component that consumes
 * `useSearchParams` must be wrapped in `<Suspense>` so the static-export
 * prerender can resolve. We mirror the pattern from
 * `web/src/app/reading/play/page.tsx`.
 */
import { Suspense } from "react";

import EndClient from "./EndClient";

export default function ReadingEndPage() {
  return (
    <Suspense fallback={<EndLoadingFallback />}>
      <EndClient />
    </Suspense>
  );
}

function EndLoadingFallback() {
  // Reading-end has no "loading-pretty" copy in copy_guide; the
  // skeleton inside `<QuoteCardPreview>` is the real loading surface.
  // The Suspense fallback only fires before hydration so it's
  // intentionally minimal.
  return (
    <main
      className="flex min-h-screen flex-col items-center justify-center gap-4 bg-ink-900 text-cream-100"
      aria-busy="true"
      data-testid="reading-end-suspense-fallback"
    >
      <p className="font-body text-sm">잠시만…</p>
    </main>
  );
}
