/**
 * `GET /api/og/[slug]` — 1080×1920 PNG share asset (ISSUE-060).
 *
 * Architecture-Ref: §6.6 (quote card / share endpoints).
 * PRD-Ref: FR-020 (cached OG image for social previews).
 *
 * Flow:
 *
 * 1. Look up the `quote_cards` row via the backend
 *    `GET /api/v1/quote-cards/by-slug/{slug}` endpoint
 *    (added in the same PR). The response carries `og_status`,
 *    `og_r2_key`, plus the inputs needed to render an inline
 *    fallback (category, character_key, quote_text).
 *
 * 2. Branch on `og_status`:
 *    - `baked` AND `og_r2_key` present → **future** path: 302 to a
 *      signed R2 URL. Phase-1 has no signed-URL service wired
 *      (`R2StorageAdapter` is a stub — see ISSUE-005), so we
 *      fall through to the inline branch below. This is
 *      documented inline so the Phase-2 swap is a one-line edit.
 *    - `pending` / `failed` / Phase-1-baked → render inline via
 *      `@vercel/og`. The image is a 1080×1920 PNG matching the
 *      bake worker's layout (A-06 category colour + character
 *      label + quote text + watermark) at JSX level.
 *
 * 3. Unknown slug → propagate the backend's 404. The social crawler
 *    surfaces a broken-link preview, which is the right UX.
 *
 * Caching:
 *
 * - Baked redirect (future): `Cache-Control: public, max-age=31536000,
 *   immutable` — the R2 key is content-addressed by `quote_card_id`.
 * - Inline fallback: `Cache-Control: public, max-age=3600` — shorter
 *   so the next request gets the baked version once the worker lands.
 * - 404: `Cache-Control: public, max-age=60` so an inflight social
 *   share doesn't hammer the backend.
 *
 * Edge runtime:
 *
 * The route exports `runtime = "edge"` per Vercel `@vercel/og`
 * requirements. `ImageResponse` from `next/og` (re-exported by
 * `@vercel/og`) renders the JSX to a PNG using Resvg/Satori under
 * the hood. We use the `next/og` import path because Next.js 15
 * publishes its own re-export with the right edge bindings.
 *
 * Helpers (`fetchQuoteCard`, `buildOgJsx`, constants, types) live in
 * the sibling `og-helpers.tsx` because Next.js Route Handler files may
 * only export route-method names (GET, POST, etc.) plus route-config
 * exports (`runtime`, `dynamic`, …). Anything else triggers a
 * "not a valid Route export field" build error.
 */

import { ImageResponse } from 'next/og';
import { NextRequest, NextResponse } from 'next/server';

import {
  OG_HEIGHT,
  OG_WIDTH,
  QuoteCardBySlugResponse,
  buildOgJsx,
  fetchQuoteCard,
} from './og-helpers';

export const runtime = 'edge';

/**
 * `GET /api/og/[slug]` — return the 1080×1920 PNG for the share asset.
 *
 * - 200 image/png — happy path (inline OR future-redirect path).
 * - 404 — slug not found in the DB.
 * - 500 — backend fetch failed for a non-404 reason. We surface a plain
 *   text body; the social crawler's preview will be empty, which is
 *   the right UX for transient errors.
 */
export async function GET(
  _request: NextRequest,
  context: { params: Promise<{ slug: string }> },
): Promise<Response> {
  // Next.js 15: dynamic route params are async-awaitable.
  const { slug } = await context.params;

  let card: QuoteCardBySlugResponse | null;
  try {
    card = await fetchQuoteCard(slug);
  } catch (err) {
    return new NextResponse(`og lookup failed: ${err instanceof Error ? err.message : 'unknown'}`, {
      status: 500,
    });
  }

  if (card === null) {
    return new NextResponse('quote card not found', {
      status: 404,
      headers: {
        // Brief negative cache so an inflight crawler retry doesn't
        // hammer the backend.
        'Cache-Control': 'public, max-age=60',
      },
    });
  }

  // Future-redirect branch:
  // When the bake worker has uploaded to real R2 (ISSUE-005), we'd 302
  // here to a presigned URL. Phase-1 storage is local-fs so there is
  // no externally addressable URL to redirect to; fall through to the
  // inline render below. The `og_r2_key` is still consulted so a
  // baked card uses the cached bytes once the R2 swap lands:
  //
  //   if (card.og_status === "baked" && card.og_r2_key && hasR2PublicBase()) {
  //     return NextResponse.redirect(buildSignedR2Url(card.og_r2_key), 302);
  //   }
  //
  // Until then both `baked` and `pending` go through @vercel/og.

  // Inline render via @vercel/og.
  return new ImageResponse(buildOgJsx(card), {
    width: OG_WIDTH,
    height: OG_HEIGHT,
    headers: {
      // 1-hour cache so the bake worker has time to land + the next
      // crawler hit picks up the cached version. The actual baked
      // image (when wired) gets a 1-year immutable cache via the
      // redirect path above.
      'Cache-Control': 'public, max-age=3600, s-maxage=3600',
    },
  });
}
