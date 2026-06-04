/**
 * Vitest unit tests for `<QuoteCardPreview v="v2">` (ISSUE-095).
 *
 * AC coverage:
 *   AC1 — category=love → border #B7414B, transform rotate(-1.5deg).
 *   AC3 — category=tarot → DOM contains <Seal hanja="月" tilt="right" />
 *         at bottom-right of the card.
 *   Borderline colour per category (love/work/money/tarot + fallback).
 *   Tilt value is constant -1.5deg regardless of category.
 *   Grain overlay uses --grain-strong via background-blend-mode: multiply.
 *   v1 path (default / v="v1") still renders the legacy `<img src=/api/og/...>`
 *   so the rollback (NEXT_PUBLIC_QUOTE_CARD_V2=false) keeps working.
 */
import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';

import { QuoteCardPreview } from '@/components/share/QuoteCardPreview';
import type { QuoteCardBySlugResponse } from '@/app/api/og/[slug]/og-helpers';

const baseCard: QuoteCardBySlugResponse = {
  quote_card_id: 'qc-2',
  category: 'love',
  character_key: 'nuna',
  quote_text: '그 사람은 너랑 코드가 안 맞아.',
  og_status: 'baked',
  og_r2_key: 'og/qc-2.png',
};

describe('QuoteCardPreview v="v2" (ISSUE-095)', () => {
  it('AC1 — love → border #B7414B + transform rotate(-1.5deg)', () => {
    render(<QuoteCardPreview slug="lv" card={baseCard} v="v2" />);
    const card = screen.getByTestId('quote-card-v2');
    expect(card).toBeInTheDocument();
    // Inline styles drive both the border and the tilt — assert via the
    // style attribute so we're checking the rendered DOM, not the
    // component internal state.
    expect(card.getAttribute('data-cat')).toBe('love');
    expect(card.style.borderColor).toBe('rgb(183, 65, 75)'); // #B7414B
    expect(card.style.transform).toContain('rotate(-1.5deg)');
  });

  it.each<[string, string]>([
    ['work', 'rgb(22, 52, 78)'],
    ['money', 'rgb(182, 139, 63)'],
    ['tarot', 'rgb(90, 54, 102)'],
  ])('category=%s → border %s', (category, rgb) => {
    render(<QuoteCardPreview slug={category} card={{ ...baseCard, category }} v="v2" />);
    const card = screen.getByTestId('quote-card-v2');
    expect(card.getAttribute('data-cat')).toBe(category);
    expect(card.style.borderColor).toBe(rgb);
  });

  it('AC3 — tarot → <Seal hanja="月" tilt="right" /> bottom-right', () => {
    render(<QuoteCardPreview slug="t1" card={{ ...baseCard, category: 'tarot' }} v="v2" />);
    const card = screen.getByTestId('quote-card-v2');
    const seal = card.querySelector('[data-testid="seal"]') as HTMLElement | null;
    expect(seal).not.toBeNull();
    expect(seal!.getAttribute('data-hanja')).toBe('月');
    expect(seal!.getAttribute('data-tilt')).toBe('right');
    // Bottom-right placement: the seal is a direct descendant of the
    // .quote-card-v2__seal-slot which is absolutely positioned at the
    // bottom-right corner.
    const slot = card.querySelector('[data-slot="seal"]') as HTMLElement | null;
    expect(slot).not.toBeNull();
    expect(slot!.style.position).toBe('absolute');
    expect(slot!.style.bottom).not.toBe('');
    expect(slot!.style.right).not.toBe('');
  });

  it('renders the per-category hanja for all 4 categories', () => {
    const cases: Array<[QuoteCardBySlugResponse['category'], string]> = [
      ['love', '戀'],
      ['work', '業'],
      ['money', '財'],
      ['tarot', '月'],
    ];
    for (const [cat, hanja] of cases) {
      const { unmount } = render(
        <QuoteCardPreview slug="x" card={{ ...baseCard, category: cat }} v="v2" />,
      );
      const seal = screen.getByTestId('seal');
      expect(seal.getAttribute('data-hanja')).toBe(hanja);
      unmount();
    }
  });

  it('falls back to 印 + neutral border for unknown category', () => {
    render(<QuoteCardPreview slug="x" card={{ ...baseCard, category: 'career_v2' }} v="v2" />);
    const card = screen.getByTestId('quote-card-v2');
    expect(card.style.borderColor).toBe('rgb(110, 90, 64)'); // #6E5A40
    const seal = card.querySelector('[data-testid="seal"]') as HTMLElement;
    expect(seal.getAttribute('data-hanja')).toBe('印');
  });

  it('applies the --grain-strong overlay with background-blend-mode: multiply', () => {
    render(<QuoteCardPreview slug="x" card={baseCard} v="v2" />);
    const grain = screen.getByTestId('quote-card-v2-grain');
    expect(grain).toBeInTheDocument();
    expect(grain.style.backgroundBlendMode).toBe('multiply');
    // jsdom silently drops `background-image: url("data:image/svg+xml,…")`
    // from inline styles because its CSS parser doesn't recognise the
    // SVG-noise payload. The component therefore tags the overlay
    // node with `data-grain-token="--grain-strong"` so the unit test
    // can still assert that the grain layer is wired to the v2 token.
    expect(grain.getAttribute('data-grain-token')).toBe('--grain-strong');
  });

  it('renders the quote text and an aria-label including the quote', () => {
    render(<QuoteCardPreview slug="x" card={baseCard} v="v2" />);
    const card = screen.getByTestId('quote-card-v2');
    expect(card.textContent).toContain(baseCard.quote_text);
    expect(card.getAttribute('role')).toBe('img');
    expect(card.getAttribute('aria-label')).toMatch(/명대사 카드/);
    expect(card.getAttribute('aria-label')).toContain(baseCard.quote_text);
  });

  it('still renders the v1 <img> when v is omitted (default)', () => {
    render(<QuoteCardPreview slug="legacy" card={baseCard} />);
    const img = screen.getByRole('img', { name: /명대사 카드/ });
    expect(img.tagName).toBe('IMG');
    expect(img.getAttribute('src')).toBe('/api/og/legacy');
  });

  it('still renders the v1 <img> when v="v1" is explicitly passed', () => {
    render(<QuoteCardPreview slug="legacy" card={baseCard} v="v1" />);
    const img = screen.getByRole('img', { name: /명대사 카드/ });
    expect(img.tagName).toBe('IMG');
  });

  it('v2 renders skeleton when card is undefined (loading)', () => {
    render(<QuoteCardPreview slug="x" card={undefined} v="v2" />);
    expect(screen.getByTestId('quote-card-skeleton')).toBeInTheDocument();
    expect(screen.queryByTestId('quote-card-v2')).toBeNull();
  });

  it('v2 still falls back to the failed-state panel when og_status=failed', () => {
    render(
      <QuoteCardPreview
        slug="x"
        card={{ ...baseCard, og_status: 'failed', og_r2_key: null }}
        v="v2"
      />,
    );
    expect(screen.getByTestId('quote-card-fallback')).toBeInTheDocument();
  });
});
