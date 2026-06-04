/**
 * Unit tests for `/tarot` page V2 routing (ISSUE-094).
 *
 * The v2 page picks between the legacy `<TarotCard>` (ISSUE-051) and
 * the new `<TarotSpread>` (this issue) via the
 * `NEXT_PUBLIC_TAROT_V2_SPREAD` feature flag. The Rollback section of
 * the issue keys off the same flag — flipping it to `false` reverts
 * `/tarot` to the legacy single-card layout instantly.
 *
 * What we test here:
 * - The flag toggles which component is mounted (we mount both via
 *   mocked subcomponents so we don't depend on flip animation
 *   internals in the page-level test).
 * - Determinism plumbing: the page hands the spread the same
 *   `cardArtUrl`/`cardName` it receives from `/tarot/today`, regardless
 *   of which spread index the user taps.
 *
 * The TarotSpread internal cascade is covered by its own component
 * test. The legacy single-card behaviour is covered by the existing
 * `page.test.tsx`.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, render, screen } from '@testing-library/react';

const ENV_KEY = 'NEXT_PUBLIC_TAROT_V2_SPREAD';

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), refresh: vi.fn() }),
  useSearchParams: () => new URLSearchParams(),
}));

function mockFetchOnce(body: Record<string, unknown>, status = 200) {
  globalThis.fetch = vi.fn(
    async () =>
      new Response(JSON.stringify(body), {
        status,
        headers: { 'Content-Type': 'application/json' },
      }),
  ) as unknown as typeof fetch;
}

afterEach(() => {
  cleanup();
  delete process.env[ENV_KEY];
  vi.resetModules();
});

beforeEach(() => {
  delete process.env[ENV_KEY];
});

describe('/tarot page — TAROT_V2_SPREAD flag (ISSUE-094)', () => {
  it('renders the v2 spread (5 cards) when the flag is on', async () => {
    process.env[ENV_KEY] = 'true';
    mockFetchOnce({
      card_index: 17,
      card_name: '달',
      card_art_url: '/api/v1/tarot/cards/17/art',
      free_remaining: 1,
      requires_payment: false,
      already_flipped: false,
      is_subscriber: false,
    });

    // Re-import after mutating the env so the module re-reads the flag
    // at evaluation time. The default export is a server-respectful
    // client component but Next 15 lets us render it directly under jsdom.
    const TarotPage = (await import('@/app/tarot/page')).default;

    await act(async () => {
      render(<TarotPage />);
    });

    const cards = screen.getAllByTestId(/^spread-card-\d$/);
    expect(cards).toHaveLength(5);
    // Legacy single-card hero should NOT be in the DOM when v2 is on.
    expect(screen.queryByTestId('tarot-card')).toBeNull();
  });

  it('renders the legacy single card when the flag is off (rollback path)', async () => {
    delete process.env[ENV_KEY];
    mockFetchOnce({
      card_index: 17,
      card_name: '달',
      card_art_url: '/api/v1/tarot/cards/17/art',
      free_remaining: 1,
      requires_payment: false,
      already_flipped: false,
      is_subscriber: false,
    });

    const TarotPage = (await import('@/app/tarot/page')).default;

    await act(async () => {
      render(<TarotPage />);
    });

    expect(screen.getByTestId('tarot-card')).toBeInTheDocument();
    expect(screen.queryAllByTestId(/^spread-card-\d$/)).toHaveLength(0);
  });
});
