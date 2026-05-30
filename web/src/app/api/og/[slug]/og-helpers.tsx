/**
 * Helpers extracted from `route.tsx` (ISSUE-060).
 *
 * Next.js Route Handlers may only export route-method names (GET, POST,
 * etc.) plus a fixed set of route-config exports (`runtime`, `dynamic`,
 * etc.). Anything else triggers a build error
 * ("X is not a valid Route export field"). Helpers and types therefore
 * live in this sibling module so the route file can import them
 * without violating the Next 15 export rule.
 *
 * Architecture-Ref: §6.6 (quote card / share endpoints).
 */

import type * as React from 'react';

// ---------------------------------------------------------------------------
// Layout constants — mirror `voicesaju.jobs.og_bake` (ISSUE-058)
// ---------------------------------------------------------------------------

/**
 * Open-Graph canvas size. The Pillow bake worker uses (1080, 1920) and
 * the test in this PR asserts the inline fallback matches.
 */
export const OG_WIDTH = 1080;
export const OG_HEIGHT = 1920;

/**
 * Category → background hex per A-06. Mirrors
 * `CATEGORY_BACKGROUNDS` in `api/voicesaju/jobs/og_bake.py`. Keep these
 * in sync — a category-colour drift between baked and fallback paths
 * would make the share UX inconsistent.
 */
export const CATEGORY_BG: Record<string, string> = {
  love: '#FFB6C1',
  work: '#87CEEB',
  money: '#FFD700',
  tarot: '#9370DB',
};

/** Fallback colour for unknown categories — neutral grey. */
export const FALLBACK_BG = '#E0E0E0';

/**
 * Character key → display label. The bake worker uses the same map
 * (private to og_bake.py); duplicated here so the JSX is self-contained.
 */
export const CHARACTER_LABEL: Record<string, string> = {
  nuna: '누나',
  dosa: '도사',
};

// ---------------------------------------------------------------------------
// Backend lookup
// ---------------------------------------------------------------------------

/**
 * Shape of the backend `GET /api/v1/quote-cards/by-slug/{slug}` response.
 * Mirrors `QuoteCardBySlugResponse` in
 * `api/voicesaju/content/routers/quote_cards.py`.
 */
export interface QuoteCardBySlugResponse {
  quote_card_id: string;
  category: string;
  character_key: string;
  quote_text: string;
  og_status: 'pending' | 'baked' | 'failed';
  og_r2_key: string | null;
}

/**
 * Resolve the backend base URL.
 *
 * In production a reverse proxy fronts both `web` and `api` on the
 * same host, so a relative `/api/v1/...` path works. The Edge runtime
 * forbids `fetch()` of relative URLs (no notion of "this host"); we
 * therefore read `BACKEND_INTERNAL_URL` from the env, with a sensible
 * dev default of `http://localhost:8000` (the FastAPI port).
 *
 * Tests inject the URL via the `fetchImpl` parameter, so this function
 * is only consulted on the real edge path.
 */
export function getBackendBaseUrl(): string {
  // `process.env` is fine on the edge — Next.js inlines it at build
  // time so the value is constant at runtime.
  return process.env.BACKEND_INTERNAL_URL ?? 'http://localhost:8000';
}

/**
 * Fetch the quote-card payload from the backend. Returns `null` when
 * the slug is unknown (backend 404). Throws on any other failure so
 * the caller can surface a 500.
 */
export async function fetchQuoteCard(
  slug: string,
  fetchImpl: typeof fetch = fetch,
  baseUrl: string = getBackendBaseUrl(),
): Promise<QuoteCardBySlugResponse | null> {
  const url = `${baseUrl}/api/v1/quote-cards/by-slug/${encodeURIComponent(slug)}`;
  const res = await fetchImpl(url, {
    method: 'GET',
    headers: { Accept: 'application/json' },
    // The endpoint is public — no credentials needed.
  });

  if (res.status === 404) {
    return null;
  }
  if (!res.ok) {
    throw new Error(`backend quote-cards lookup failed: ${res.status}`);
  }
  const json = (await res.json()) as unknown;
  if (
    !json ||
    typeof json !== 'object' ||
    typeof (json as Record<string, unknown>).quote_card_id !== 'string' ||
    typeof (json as Record<string, unknown>).category !== 'string' ||
    typeof (json as Record<string, unknown>).character_key !== 'string' ||
    typeof (json as Record<string, unknown>).quote_text !== 'string' ||
    typeof (json as Record<string, unknown>).og_status !== 'string'
  ) {
    throw new Error('backend quote-cards response shape invalid');
  }
  return json as QuoteCardBySlugResponse;
}

// ---------------------------------------------------------------------------
// Inline OG render
// ---------------------------------------------------------------------------

/**
 * Build the JSX that `@vercel/og`'s `ImageResponse` renders to a PNG.
 *
 * The layout deliberately mirrors `og_bake.py`'s Pillow layout so the
 * baked and inline paths produce visually similar cards:
 *
 * - Solid category-colour background.
 * - Character label ("누나" / "도사") in the upper third.
 * - Quote text (≤ 40 chars by ISSUE-056 invariant) centered in the
 *   middle band.
 * - "VoiceSaju" watermark in the bottom-right corner.
 *
 * Exported for unit tests so the render shape can be asserted without
 * triggering `ImageResponse` (which needs the edge runtime).
 */
export function buildOgJsx(card: {
  category: string;
  character_key: string;
  quote_text: string;
}): React.ReactElement {
  const bg = CATEGORY_BG[card.category] ?? FALLBACK_BG;
  const characterLabel = CHARACTER_LABEL[card.character_key] ?? card.character_key;

  return (
    <div
      style={{
        width: '100%',
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'space-between',
        backgroundColor: bg,
        padding: '120px 80px',
        fontFamily: 'sans-serif',
      }}
    >
      {/* Upper third — character label */}
      <div
        style={{
          fontSize: 96,
          color: '#1f1f1f',
          fontWeight: 700,
          letterSpacing: '-0.02em',
        }}
      >
        {characterLabel}
      </div>

      {/* Middle band — quote */}
      <div
        style={{
          display: 'flex',
          textAlign: 'center',
          fontSize: 88,
          lineHeight: 1.3,
          color: '#1f1f1f',
          fontWeight: 600,
          maxWidth: '900px',
          padding: '0 40px',
        }}
      >
        {card.quote_text}
      </div>

      {/* Bottom-right — watermark */}
      <div
        style={{
          alignSelf: 'flex-end',
          fontSize: 48,
          color: 'rgba(31, 31, 31, 0.6)',
          fontWeight: 500,
        }}
      >
        VoiceSaju
      </div>
    </div>
  );
}
