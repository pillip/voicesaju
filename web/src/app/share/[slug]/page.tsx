/**
 * `/share/[slug]` — public share landing (Screen 23, ISSUE-061).
 *
 * Architecture-Ref: §6.6 (quote card / share endpoints).
 * PRD-Ref: FR-020 (cached OG preview + onboarding hook).
 *
 * This is a React Server Component. It does two jobs:
 *
 * 1. `generateMetadata()` emits the OG / Twitter card meta tags so
 *    KakaoTalk / Twitter / iMessage crawlers see a rich preview pointing
 *    at `/api/og/{slug}` (the route added in ISSUE-060). The metadata
 *    surface is INDEPENDENT of whether the slug exists — even an unknown
 *    slug gets meta tags pointing at the same `/api/og` URL, which itself
 *    returns 404 for unknown slugs (the social crawler then renders a
 *    broken preview, which matches the share UX we want).
 *
 * 2. The page body fetches the quote card via the sibling helper
 *    `fetchQuoteCard()` from `/api/og/[slug]/og-helpers.tsx` (re-used so
 *    both surfaces use the same backend shape). On miss, `notFound()`
 *    bails out to the local `not-found.tsx` (the "expired card" state
 *    from ux_spec Screen 23). On hit, we render a full-bleed quote-card
 *    image (sourced from `/api/og/{slug}` so it's the SAME asset the
 *    crawler showed in the preview) + the "내 풀이도 받아보기" CTA that
 *    routes to `/onboarding/birth-date`.
 *
 * Notes:
 *
 * - We intentionally render an `<img>` (not `next/image`) because the
 *   asset is served by an edge route handler that already controls its
 *   own caching — `next/image` would add an extra optimizer hop with no
 *   benefit for a fixed-dimension 1080×1920 PNG.
 * - The CTA is a `next/link` so client navigation works without a full
 *   page reload once the bundle hydrates. The intent is conversion, so
 *   the page deliberately has zero other interactive surface.
 */

import type { Metadata } from 'next';
import Link from 'next/link';
import { notFound } from 'next/navigation';

import { fetchQuoteCard } from '@/app/api/og/[slug]/og-helpers';

interface ShareRouteParams {
  slug: string;
}

interface ShareRouteProps {
  params: Promise<ShareRouteParams>;
}

/** copy_guide §`/share/[slug]` */
const OG_TITLE_PREFIX = 'VoiceSaju';
const OG_DESCRIPTION = '새벽 3시의 누님이 직접 풀어주는 음성 사주.';
const PAGE_H1 = '흠. 너도 풀어볼래?';
const PAGE_SUB = '1분이면 돼.';
const CTA_PRIMARY = '내 풀이도 받아보기';
const ONBOARDING_HREF = '/onboarding/birth-date';

/**
 * OG / Twitter meta. Runs separately from the page body (Next 15 calls
 * it first for the crawler path). We swallow fetch errors and emit the
 * default tags so a backend hiccup never breaks the preview.
 */
export async function generateMetadata({ params }: ShareRouteProps): Promise<Metadata> {
  const { slug } = await params;
  let quoteText: string | null = null;
  try {
    const card = await fetchQuoteCard(slug);
    quoteText = card?.quote_text ?? null;
  } catch {
    // Backend down or 5xx: still emit the OG tag pointing at the image
    // route. The image route has its own 500 path that returns a plain
    // body so the crawler shows a blank preview rather than a tombstone.
    quoteText = null;
  }

  // og:image URL — points at `/api/og/{slug}`. Use a path so the meta
  // tag is host-relative; the social crawler resolves it against the
  // page's own URL.
  const ogImageUrl = `/api/og/${slug}`;
  const ogTitle = quoteText
    ? `${OG_TITLE_PREFIX} — ${quoteText}`
    : `${OG_TITLE_PREFIX} — 너도 풀어볼래?`;

  return {
    title: ogTitle,
    description: OG_DESCRIPTION,
    openGraph: {
      title: ogTitle,
      description: OG_DESCRIPTION,
      type: 'website',
      images: [
        {
          url: ogImageUrl,
          width: 1080,
          height: 1920,
          alt: ogTitle,
        },
      ],
    },
    twitter: {
      card: 'summary_large_image',
      title: ogTitle,
      description: OG_DESCRIPTION,
      images: [ogImageUrl],
    },
  };
}

/**
 * RSC body. Fetches the card, bails to `not-found.tsx` on miss, else
 * renders the share landing.
 */
export default async function SharePage({ params }: ShareRouteProps) {
  const { slug } = await params;

  // We tolerate backend 5xx by returning `null` (treat as missing). This
  // keeps the share path resilient — the OG image route will return a
  // 500 of its own, but the page itself renders the "expired" state
  // rather than a generic crash. The trade-off: a transient backend
  // blip surfaces as "expired" copy. We accept it because the actual
  // backend SLO is much tighter than the share-card TTL.
  let card;
  try {
    card = await fetchQuoteCard(slug);
  } catch {
    card = null;
  }

  if (card === null) {
    notFound();
  }

  // The OG image URL is the same one we put in the meta tag — sharing
  // the asset cuts cache misses and keeps the visual consistent.
  const ogImageUrl = `/api/og/${slug}`;

  return (
    <main
      className="flex min-h-screen flex-col items-center justify-between bg-ink-900 px-s4 py-s8 text-cream-100"
      data-testid="share-landing"
    >
      {/* Hero — quote card image */}
      <section
        className="flex w-full max-w-md flex-col items-center gap-s4"
        aria-label="공유된 명대사 카드"
      >
        {/*
          We deliberately use a raw <img> rather than next/image: the
          source is an edge route handler that already controls its own
          cache headers, the dimensions are fixed (1080×1920), and
          inserting the next/image optimizer would force an extra hop
          through `/_next/image` with no perceived win for a PNG-of-
          known-size used once per page.
        */}
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={ogImageUrl}
          alt={`${OG_TITLE_PREFIX} 명대사 카드`}
          width={1080}
          height={1920}
          className="aspect-[9/16] w-full max-w-sm rounded-lg shadow-lg"
        />
      </section>

      {/* CTA block */}
      <section className="flex w-full max-w-md flex-col items-center gap-s3 pt-s6 text-center">
        <h1 className="font-display text-3xl font-bold tracking-tight text-cream-50">{PAGE_H1}</h1>
        <p className="font-body text-base text-cream-200">{PAGE_SUB}</p>
        <Link
          href={ONBOARDING_HREF}
          className="mt-s4 inline-flex items-center justify-center gap-s2 rounded-md bg-amber-400 px-s5 py-s3 font-body text-base font-medium text-ink-900 transition-colors hover:bg-amber-300 active:bg-amber-500 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-amber-300"
          data-testid="share-cta"
        >
          {CTA_PRIMARY}
        </Link>
        <p className="mt-s2 max-w-xs font-body text-xs text-cream-300">
          VoiceSaju는 음성으로 듣는 매운맛 사주·타로 서비스야.
        </p>
      </section>
    </main>
  );
}
