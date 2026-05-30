/**
 * axe-core WCAG 2.1 AA scan for `/share/[slug]` (ISSUE-061).
 *
 * The share page is a Server Component so we extract the renderable
 * tree by calling the RSC function (it returns plain JSX) and feeding
 * the result into a small client-side wrapper that React Testing Library
 * can mount under jsdom. `color-contrast` is disabled because jsdom
 * doesn't compute real CSS contrast (token-level contrast lives in the
 * design-system preview test).
 */
import { describe, expect, it, vi } from 'vitest';
import { render } from '@testing-library/react';
import { axe, toHaveNoViolations } from 'jest-axe';

import type { QuoteCardBySlugResponse } from '../../../api/og/[slug]/og-helpers';

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

vi.mock('next/navigation', async () => {
  const actual = await vi.importActual<typeof import('next/navigation')>('next/navigation');
  return {
    ...actual,
    notFound: () => {
      throw new Error('notFound called');
    },
  };
});

import SharePage from '../page';
import NotFoundPage from '../not-found';

expect.extend(toHaveNoViolations);

const axeRules = {
  'color-contrast': { enabled: false },
};

const sampleCard: QuoteCardBySlugResponse = {
  quote_card_id: 'uuid-1',
  category: 'love',
  character_key: 'nuna',
  quote_text: '마음 가는 곳에 답이 있다.',
  og_status: 'baked',
  og_r2_key: 'og/uuid-1.png',
};

describe('/share/[slug] — WCAG 2.1 AA', () => {
  it('has zero axe violations on the happy-path render', async () => {
    fetchQuoteCardMock.mockReset();
    fetchQuoteCardMock.mockResolvedValueOnce(sampleCard);
    const tree = await SharePage({ params: Promise.resolve({ slug: 'abc123' }) });
    const { container } = render(tree);
    const results = await axe(container, { rules: axeRules });
    expect(results).toHaveNoViolations();
  }, 15000);

  it('has zero axe violations on the not-found render', async () => {
    const { container } = render(<NotFoundPage />);
    const results = await axe(container, { rules: axeRules });
    expect(results).toHaveNoViolations();
  }, 15000);
});
