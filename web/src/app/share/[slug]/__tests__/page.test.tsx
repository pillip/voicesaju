/**
 * Unit tests for `/share/[slug]` SSR landing page (ISSUE-061).
 *
 * The page is an RSC that:
 *
 * 1. Fetches the quote-card metadata via `fetchQuoteCard` (re-used from the
 *    sibling `/api/og/[slug]` helpers added in ISSUE-060).
 * 2. Calls `notFound()` on missing slug so Next.js renders the local
 *    `not-found.tsx`.
 * 3. Renders an `<img src="/api/og/{slug}">` quote card + a "내 풀이도
 *    받아보기" CTA `<Link>` to `/onboarding/birth-date`.
 *
 * Plus `generateMetadata()` must return OG meta values pointing at
 * `/api/og/{slug}` (FR-020). We assert that surface directly.
 *
 * We intentionally do NOT exercise the full Next.js render pipeline —
 * vitest + jsdom can't run Server Components without elaborate
 * scaffolding. Instead we call the RSC function (it's an async function
 * that returns JSX) and inspect the React element tree the same way the
 * `og-helpers.tsx` route tests inspect `buildOgJsx`. This keeps the test
 * file fast (no React reconciler) and lets us assert OG meta + CTA
 * without needing a server harness.
 */
import { describe, expect, it, vi } from 'vitest';
import type { ReactElement } from 'react';

import type { QuoteCardBySlugResponse } from '../../../api/og/[slug]/og-helpers';

// Mock the backend fetch helper. We re-export the sibling module so the
// page imports the same function path; `vi.mock` replaces `fetchQuoteCard`
// in-place.
const fetchQuoteCardMock = vi.fn();
vi.mock('@/app/api/og/[slug]/og-helpers', async () => {
  const actual = await vi.importActual<typeof import('@/app/api/og/[slug]/og-helpers')>(
    '@/app/api/og/[slug]/og-helpers',
  );
  return {
    ...actual,
    fetchQuoteCard: (...args: unknown[]) => fetchQuoteCardMock(...args),
  };
});

// `notFound()` from `next/navigation` throws a special sentinel inside
// Next.js. In our jsdom test we replace it with a plain `Error` so we can
// assert the page bailed out via the 404 branch.
class NotFoundCalled extends Error {}
vi.mock('next/navigation', async () => {
  const actual = await vi.importActual<typeof import('next/navigation')>('next/navigation');
  return {
    ...actual,
    notFound: () => {
      throw new NotFoundCalled('notFound called');
    },
  };
});

import SharePage, { generateMetadata } from '../page';

const sampleCard: QuoteCardBySlugResponse = {
  quote_card_id: 'uuid-1',
  category: 'love',
  character_key: 'nuna',
  quote_text: '마음 가는 곳에 답이 있다.',
  og_status: 'baked',
  og_r2_key: 'og/uuid-1.png',
};

// ---------------------------------------------------------------------------
// generateMetadata — OG meta surface
// ---------------------------------------------------------------------------

describe('generateMetadata', () => {
  it('returns og:image / twitter:image pointing at /api/og/{slug}', async () => {
    fetchQuoteCardMock.mockReset();
    fetchQuoteCardMock.mockResolvedValueOnce(sampleCard);

    const meta = await generateMetadata({
      params: Promise.resolve({ slug: 'abc123' }),
    });

    // og:image — the load-bearing field for share previews.
    expect(meta.openGraph?.images).toBeDefined();
    const ogImages = meta.openGraph?.images;
    const ogImage = Array.isArray(ogImages) ? ogImages[0] : ogImages;
    const ogImageUrl =
      typeof ogImage === 'string' ? ogImage : (ogImage as { url: string | URL } | undefined)?.url;
    expect(String(ogImageUrl)).toContain('/api/og/abc123');

    // Twitter mirror — `summary_large_image` per FR-020.
    // `Metadata['twitter']` is a discriminated union; the `card` discriminator
    // is only exposed on the `summary_large_image` variant, so we narrow
    // through `unknown` to read it back in the test.
    const twitter = meta.twitter as { card?: string; images?: unknown } | undefined;
    expect(twitter?.card).toBe('summary_large_image');
    const twitterImages = twitter?.images;
    const twImage = Array.isArray(twitterImages) ? twitterImages[0] : twitterImages;
    expect(String(twImage)).toContain('/api/og/abc123');

    // Title / description — copy_guide /share/[slug] section.
    expect(meta.openGraph?.title).toContain('VoiceSaju');
    expect(meta.openGraph?.description).toBeTruthy();
  });

  it('falls back to default share metadata when slug is missing', async () => {
    fetchQuoteCardMock.mockReset();
    fetchQuoteCardMock.mockResolvedValueOnce(null);

    const meta = await generateMetadata({
      params: Promise.resolve({ slug: 'missing' }),
    });

    // Even when the slug is unknown we still emit the OG image URL so
    // social platforms have something to render (the /api/og/{slug}
    // endpoint itself handles the 404). The page body renders the
    // 404 state via `notFound()`; this metadata surface is independent.
    expect(meta.openGraph?.images).toBeDefined();
    const ogImages = meta.openGraph?.images;
    const ogImage = Array.isArray(ogImages) ? ogImages[0] : ogImages;
    const ogImageUrl =
      typeof ogImage === 'string' ? ogImage : (ogImage as { url: string | URL } | undefined)?.url;
    expect(String(ogImageUrl)).toContain('/api/og/missing');
  });
});

// ---------------------------------------------------------------------------
// SharePage RSC — happy path renders image + CTA
// ---------------------------------------------------------------------------

describe('SharePage RSC', () => {
  it('renders the OG image + CTA when the slug resolves', async () => {
    fetchQuoteCardMock.mockReset();
    fetchQuoteCardMock.mockResolvedValueOnce(sampleCard);

    const tree = (await SharePage({
      params: Promise.resolve({ slug: 'abc123' }),
    })) as ReactElement;

    // Walk the tree looking for the <img> and CTA. We don't render the
    // tree (no client-side hooks needed); structural inspection is
    // enough to assert AC 3.
    const html = stringifyJsx(tree);

    // OG image — sourced from the share path so the same asset the
    // crawler sees is what the user sees.
    expect(html).toContain('/api/og/abc123');
    expect(html).toContain('<img');

    // CTA — Korean copy from copy_guide. The destination is
    // /onboarding/birth-date per ux_spec Screen 23.
    expect(html).toContain('내 풀이도 받아보기');
    expect(html).toContain('/onboarding/birth-date');
  });

  it('calls notFound() when the slug is unknown', async () => {
    fetchQuoteCardMock.mockReset();
    fetchQuoteCardMock.mockResolvedValueOnce(null);

    await expect(
      SharePage({ params: Promise.resolve({ slug: 'missing' }) }),
    ).rejects.toBeInstanceOf(NotFoundCalled);
  });
});

// ---------------------------------------------------------------------------
// Tiny JSX → string serializer for structural assertions.
// We can't use ReactDOMServer.renderToString in a vitest worker without
// the React server-renderer entry point; this walker is enough to pull
// out element types, text, and the href/src/alt props we care about.
// ---------------------------------------------------------------------------
function stringifyJsx(node: unknown): string {
  if (node === null || node === undefined || node === false) {
    return '';
  }
  if (typeof node === 'string' || typeof node === 'number') {
    return String(node);
  }
  if (Array.isArray(node)) {
    return node.map(stringifyJsx).join('');
  }
  if (typeof node !== 'object') {
    return '';
  }
  const el = node as ReactElement & { type: unknown; props: Record<string, unknown> };
  const typeName =
    typeof el.type === 'function'
      ? // Function components: invoke them so we can inspect the children
        // (Link from next/link is a function component that renders an <a>).
        renderFunctionComponent(el.type as (p: unknown) => ReactElement, el.props)
      : typeof el.type === 'string'
        ? el.type
        : 'unknown';

  if (typeof typeName !== 'string') {
    return stringifyJsx(typeName);
  }

  const attrs: string[] = [];
  for (const [key, value] of Object.entries(el.props ?? {})) {
    if (key === 'children') continue;
    if (typeof value === 'string') {
      attrs.push(`${key}="${value}"`);
    } else if (typeof value === 'number' || typeof value === 'boolean') {
      attrs.push(`${key}="${value}"`);
    }
  }
  const open = attrs.length > 0 ? `<${typeName} ${attrs.join(' ')}>` : `<${typeName}>`;
  const inner = stringifyJsx(el.props?.children);
  return `${open}${inner}</${typeName}>`;
}

function renderFunctionComponent(
  fn: (p: unknown) => ReactElement,
  props: Record<string, unknown>,
): string | ReactElement {
  try {
    const out = fn(props);
    return out;
  } catch {
    // Some components (e.g., next/link) may throw without the app router
    // context. In that case we still want the test to see the prop hints
    // — fall back to the function's name as the tag and let the
    // serializer pick up href + children from the original element.
    const name = fn.name || 'unknown';
    return name;
  }
}
