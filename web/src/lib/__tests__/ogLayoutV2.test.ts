/**
 * ISSUE-095 — drift guard between `og/layout_v2.json` (canonical) and
 * the TS mirror in `web/src/lib/ogLayoutV2.ts`.
 *
 * Why: the Pillow worker reads the JSON file directly; the edge route
 * (`@vercel/og`) cannot read files at runtime, so it imports the TS
 * mirror. If the two drift, the baked PNG and the inline fallback
 * stop matching → AC "Pillow vs edge pixel diff < 1 %" breaks.
 *
 * This test re-parses the JSON at test time and asserts deep equality
 * vs the TS export (modulo the `_comment` key which is JSON-only
 * documentation).
 */
import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import { OG_LAYOUT_V2, v2BorderColorForCategory, v2SealHanjaForCategory } from '@/lib/ogLayoutV2';

const JSON_PATH = join(__dirname, '..', '..', '..', '..', 'og', 'layout_v2.json');

function loadJson(): Record<string, unknown> {
  const raw = readFileSync(JSON_PATH, 'utf8');
  const parsed = JSON.parse(raw) as Record<string, unknown>;
  // Strip the documentation comment — it is JSON-only.
  // eslint-disable-next-line @typescript-eslint/no-unused-vars, @typescript-eslint/naming-convention
  const { _comment, ...rest } = parsed;
  return rest;
}

describe('OG_LAYOUT_V2 vs og/layout_v2.json drift', () => {
  it('matches the JSON file byte-for-byte (modulo _comment)', () => {
    const fromJson = loadJson();
    // Use deep equality — comparing the parsed values rather than raw
    // strings avoids spurious failures from formatter whitespace.
    expect(OG_LAYOUT_V2).toEqual(fromJson);
  });

  it('declares canvas dimensions 1080×1920 (AC2)', () => {
    expect(OG_LAYOUT_V2.canvas.width).toBe(1080);
    expect(OG_LAYOUT_V2.canvas.height).toBe(1920);
  });

  it('declares the v2 category border palette per spec', () => {
    expect(OG_LAYOUT_V2.border.categories).toEqual({
      love: '#B7414B',
      work: '#16344E',
      money: '#B68B3F',
      tarot: '#5A3666',
    });
  });

  it('declares tilt -1.5deg per AC1', () => {
    expect(OG_LAYOUT_V2.tilt.rotate_deg).toBe(-1.5);
  });

  it('declares grain blend-mode multiply with --grain-strong token', () => {
    expect(OG_LAYOUT_V2.grain.blend_mode).toBe('multiply');
    expect(OG_LAYOUT_V2.grain.token).toBe('--grain-strong');
  });

  it('places the seal in the bottom-right corner with tilt=right', () => {
    expect(OG_LAYOUT_V2.seal.corner).toBe('bottom-right');
    expect(OG_LAYOUT_V2.seal.tilt).toBe('right');
  });

  it('uses the FR-038 hanja mapping for the seal corner', () => {
    expect(OG_LAYOUT_V2.seal.category_hanja).toEqual({
      love: '戀',
      work: '業',
      money: '財',
      tarot: '月',
      'reading-end': '明',
    });
  });
});

describe('v2BorderColorForCategory', () => {
  it.each([
    ['love', '#B7414B'],
    ['work', '#16344E'],
    ['money', '#B68B3F'],
    ['tarot', '#5A3666'],
  ])('category=%s → %s', (cat, hex) => {
    expect(v2BorderColorForCategory(cat)).toBe(hex);
  });

  it('falls back to hanji-300 for an unknown category', () => {
    expect(v2BorderColorForCategory('career_v2')).toBe('#6E5A40');
  });
});

describe('v2SealHanjaForCategory', () => {
  it.each([
    ['love', '戀'],
    ['work', '業'],
    ['money', '財'],
    ['tarot', '月'],
    ['reading-end', '明'],
  ])('category=%s → %s', (cat, hanja) => {
    expect(v2SealHanjaForCategory(cat)).toBe(hanja);
  });

  it('falls back to 印 for an unknown category', () => {
    expect(v2SealHanjaForCategory('mystery')).toBe('印');
  });
});
