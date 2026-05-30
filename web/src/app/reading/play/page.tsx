/**
 * Server-component shell for `/reading/play` (ISSUE-042 — Screen 9).
 *
 * The interactive client (`PlayClient`) reads `?reading_id` and
 * `?category` via `useSearchParams()`. Per Next 15's App Router
 * contract, any client component that consumes `useSearchParams` must
 * be wrapped in `<Suspense>` so the static-export prerender can
 * resolve. We do that here.
 *
 * Routing contract:
 *   /reading/play?reading_id=<id>           → resume existing pipeline.
 *   /reading/play?category=<love|work|money> → mint new reading via
 *                                              `POST /api/v1/reading`.
 *   /reading/play                            → redirect to /reading/category
 *                                              (no context to start with).
 */
import { Suspense } from 'react';
import PlayClient from './PlayClient';

export default function PlayRoutePage() {
  return (
    <Suspense fallback={<PlayLoadingFallback />}>
      <PlayClient />
    </Suspense>
  );
}

function PlayLoadingFallback() {
  // Mirrors the loading-state copy from ux_spec Screen 9. Tailwind
  // classes here are limited to avoid pulling in the design system in
  // the Suspense fallback path (server-rendered, no client JS yet).
  return (
    <main
      className="flex min-h-screen flex-col items-center justify-center gap-4 bg-ink-900 text-cream-100"
      aria-busy="true"
      data-testid="play-suspense-fallback"
    >
      <p className="font-body text-base">별기운을 모으는 중…</p>
    </main>
  );
}
