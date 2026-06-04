/**
 * ISSUE-095 — `buildOgJsxV2` edge-route shape tests.
 *
 * We assert the v2 OG JSX:
 *   - canvas background = #1A1208 (hanji-800)
 *   - per-category border colour drawn as a thick frame
 *   - vermilion seal embedded bottom-right with the per-category hanja
 *   - watermark + quote text still present
 *
 * We do NOT exercise @vercel/og's `ImageResponse` here (edge runtime
 * only). The pixel-diff guard against the Pillow worker lives in the
 * integration tier; this unit exists so a JSX-shape regression fails
 * fast at component test time.
 */
import { describe, expect, it } from 'vitest';
import type { ReactElement } from 'react';
import { buildOgJsxV2 } from '@/app/api/og/[slug]/og-helpers';

interface AnyEl extends ReactElement {
  props: { style?: Record<string, unknown>; children?: unknown };
}

function flattenStringText(node: unknown): string {
  if (node == null) return '';
  if (typeof node === 'string' || typeof node === 'number') return String(node);
  if (Array.isArray(node)) return node.map(flattenStringText).join(' ');
  if (typeof node === 'object' && node !== null && 'props' in (node as ReactElement)) {
    const el = node as AnyEl;
    return flattenStringText((el.props as { children?: unknown }).children);
  }
  return '';
}

describe('buildOgJsxV2 — ISSUE-095 (edge JSX shape)', () => {
  const baseCard = {
    category: 'love' as const,
    character_key: 'nuna',
    quote_text: '마음 가는 곳에 답이 있다.',
  };

  it('uses the hanji-800 canvas background', () => {
    const el = buildOgJsxV2(baseCard) as AnyEl;
    expect(el.props.style!.backgroundColor).toBe('#1A1208');
  });

  it.each([
    ['love', '#B7414B'],
    ['work', '#16344E'],
    ['money', '#B68B3F'],
    ['tarot', '#5A3666'],
  ] as const)('category=%s → border %s', (category, hex) => {
    const el = buildOgJsxV2({ ...baseCard, category }) as AnyEl;
    expect(el.props.style!.borderColor).toBe(hex);
    expect(el.props.style!.borderStyle).toBe('solid');
  });

  it('falls back to hanji-300 border for unknown categories', () => {
    const el = buildOgJsxV2({ ...baseCard, category: 'unknown' }) as AnyEl;
    expect(el.props.style!.borderColor).toBe('#6E5A40');
  });

  it('renders the category hanja in the seal corner', () => {
    const cases: Array<[string, string]> = [
      ['love', '戀'],
      ['work', '業'],
      ['money', '財'],
      ['tarot', '月'],
    ];
    for (const [cat, hanja] of cases) {
      const el = buildOgJsxV2({ ...baseCard, category: cat }) as AnyEl;
      const text = flattenStringText(el);
      expect(text).toContain(hanja);
    }
  });

  it('renders the quote text', () => {
    const el = buildOgJsxV2(baseCard) as AnyEl;
    expect(flattenStringText(el)).toContain('마음 가는 곳에 답이 있다.');
  });

  it("renders a 'VoiceSaju' watermark", () => {
    const el = buildOgJsxV2(baseCard) as AnyEl;
    expect(flattenStringText(el)).toContain('VoiceSaju');
  });

  it('seal uses the vermilion fill from the layout JSON', () => {
    // Walk the JSX tree to find a child with backgroundColor == #9B2A1A.
    const el = buildOgJsxV2(baseCard) as AnyEl;
    const stack: AnyEl[] = [el];
    let found = false;
    while (stack.length) {
      const cur = stack.pop()!;
      const style = (cur.props?.style ?? {}) as Record<string, unknown>;
      if (style.backgroundColor === '#9B2A1A') {
        found = true;
        break;
      }
      const kids = cur.props?.children;
      if (Array.isArray(kids)) {
        for (const k of kids) {
          if (k && typeof k === 'object' && 'props' in (k as ReactElement)) {
            stack.push(k as AnyEl);
          }
        }
      } else if (kids && typeof kids === 'object' && 'props' in (kids as ReactElement)) {
        stack.push(kids as AnyEl);
      }
    }
    expect(found).toBe(true);
  });
});
