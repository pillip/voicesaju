/**
 * Unit tests for `/api/og/[slug]` (ISSUE-060).
 *
 * We split the assertions across two surfaces:
 *
 * 1. `fetchQuoteCard` — the backend lookup. Mocked `fetch` so we can
 *    pin status-code branches (200 / 404 / 5xx) and shape validation
 *    without touching the real backend.
 *
 * 2. `buildOgJsx` — the React element shape rendered by `@vercel/og`.
 *    We assert the structural pieces (background colour, character
 *    label, quote text, watermark) without invoking `ImageResponse`
 *    itself (which requires the edge runtime).
 *
 * We intentionally do NOT exercise the full `GET` handler end-to-end
 * because `ImageResponse` in `@vercel/og` requires the edge runtime
 * (WebAssembly Resvg + Satori). The two units above cover the
 * load-bearing logic; integration coverage lands at the vercel.json
 * smoke-test layer.
 */

import { describe, it, expect, vi } from 'vitest';
import { buildOgJsx, fetchQuoteCard } from '../og-helpers';
import type { QuoteCardBySlugResponse } from '../og-helpers';

// ---------------------------------------------------------------------------
// fetchQuoteCard — backend status-code branches
// ---------------------------------------------------------------------------

describe('fetchQuoteCard', () => {
  const sampleResponse: QuoteCardBySlugResponse = {
    quote_card_id: 'uuid-1',
    category: 'tarot',
    character_key: 'dosa',
    quote_text: '운명은 네 손 안에 있다.',
    og_status: 'baked',
    og_r2_key: 'og/uuid-1.png',
  };

  it('returns the parsed payload on 200', async () => {
    const fetchMock = vi.fn((async () => {}) as unknown as typeof fetch);
    // Replace impl so the mock retains the (url, init) signature in
    // .mock.calls[0] for the URL assertions below.
    fetchMock.mockImplementation(
      async () =>
        new Response(JSON.stringify(sampleResponse), {
          status: 200,
          headers: { 'content-type': 'application/json' },
        }),
    );

    const result = await fetchQuoteCard('abc123XYZdef', fetchMock as never, 'http://api');

    expect(result).toEqual(sampleResponse);
    expect(fetchMock).toHaveBeenCalledOnce();
    const calledUrl = fetchMock.mock.calls[0][0];
    expect(calledUrl).toBe('http://api/api/v1/quote-cards/by-slug/abc123XYZdef');
  });

  it('URL-encodes the slug parameter', async () => {
    // While the share_slug is base62 (no reserved chars), the route
    // handler still receives the raw path segment and we want to
    // guard against a future change in slug alphabet by always
    // encoding. Test passes a slug with a `/` to assert encoding.
    const fetchMock = vi.fn((async () => {}) as unknown as typeof fetch);
    // Replace impl so the mock retains the (url, init) signature in
    // .mock.calls[0] for the URL assertions below.
    fetchMock.mockImplementation(
      async () => new Response(JSON.stringify(sampleResponse), { status: 200 }),
    );

    await fetchQuoteCard('a/b', fetchMock as never, 'http://api');

    const calledUrl = fetchMock.mock.calls[0][0];
    expect(calledUrl).toBe('http://api/api/v1/quote-cards/by-slug/a%2Fb');
  });

  it('returns null on backend 404', async () => {
    const fetchMock = vi.fn(
      async () =>
        new Response(JSON.stringify({ detail: 'not found' }), {
          status: 404,
        }),
    );

    const result = await fetchQuoteCard('nope', fetchMock as never, 'http://api');

    expect(result).toBeNull();
  });

  it('throws on backend 5xx', async () => {
    const fetchMock = vi.fn(async () => new Response('boom', { status: 500 }));

    await expect(fetchQuoteCard('any', fetchMock as never, 'http://api')).rejects.toThrow(/500/);
  });

  it('throws when the backend payload shape is invalid', async () => {
    const fetchMock = vi.fn(
      async () => new Response(JSON.stringify({ unexpected: 'shape' }), { status: 200 }),
    );

    await expect(fetchQuoteCard('any', fetchMock as never, 'http://api')).rejects.toThrow(
      /shape invalid/,
    );
  });
});

// ---------------------------------------------------------------------------
// buildOgJsx — render shape
// ---------------------------------------------------------------------------

describe('buildOgJsx', () => {
  const baseCard = {
    category: 'love' as const,
    character_key: 'nuna',
    quote_text: '마음 가는 곳에 답이 있다.',
  };

  it('returns a JSX element with the category background colour', () => {
    const el = buildOgJsx(baseCard);
    const outerStyle = (el.props as { style: { backgroundColor: string } }).style;
    // love → #FFB6C1 per A-06
    expect(outerStyle.backgroundColor).toBe('#FFB6C1');
  });

  it.each([
    ['love', '#FFB6C1'],
    ['work', '#87CEEB'],
    ['money', '#FFD700'],
    ['tarot', '#9370DB'],
  ])('category=%s renders background %s', (category, expected) => {
    const el = buildOgJsx({ ...baseCard, category });
    const outerStyle = (el.props as { style: { backgroundColor: string } }).style;
    expect(outerStyle.backgroundColor).toBe(expected);
  });

  it('falls back to neutral grey for unknown categories', () => {
    const el = buildOgJsx({ ...baseCard, category: 'career_v2' });
    const outerStyle = (el.props as { style: { backgroundColor: string } }).style;
    expect(outerStyle.backgroundColor).toBe('#E0E0E0');
  });

  it('includes the character label for known persona keys', () => {
    const el = buildOgJsx({ ...baseCard, character_key: 'dosa' });
    // The outer container has 3 children (label / quote / watermark).
    const children = (el.props as { children: React.ReactElement[] }).children;
    expect(children).toHaveLength(3);

    const labelChild = children[0] as React.ReactElement;
    const labelText = (labelChild.props as { children: string }).children;
    expect(labelText).toBe('도사');
  });

  it('falls back to the raw character_key when not a known persona', () => {
    const el = buildOgJsx({ ...baseCard, character_key: 'unknown_persona' });
    const children = (el.props as { children: React.ReactElement[] }).children;
    const labelChild = children[0] as React.ReactElement;
    const labelText = (labelChild.props as { children: string }).children;
    expect(labelText).toBe('unknown_persona');
  });

  it('renders the quote_text in the middle band', () => {
    const el = buildOgJsx(baseCard);
    const children = (el.props as { children: React.ReactElement[] }).children;
    const quoteChild = children[1] as React.ReactElement;
    const quoteText = (quoteChild.props as { children: string }).children;
    expect(quoteText).toBe('마음 가는 곳에 답이 있다.');
  });

  it("includes a 'VoiceSaju' watermark in the bottom slot", () => {
    const el = buildOgJsx(baseCard);
    const children = (el.props as { children: React.ReactElement[] }).children;
    const watermarkChild = children[2] as React.ReactElement;
    const watermarkText = (watermarkChild.props as { children: string }).children;
    expect(watermarkText).toBe('VoiceSaju');
  });
});
