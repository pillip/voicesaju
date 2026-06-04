/**
 * ISSUE-095 — TypeScript mirror of `og/layout_v2.json`.
 *
 * Both the Pillow worker (`api/voicesaju/jobs/og_bake.py`) and the
 * `@vercel/og` edge route (`web/src/app/api/og/[slug]/og-helpers.tsx`)
 * read their layout constants from `og/layout_v2.json` so the two
 * renderers stay in lockstep (FR-021 — Pillow vs edge pixel diff < 1 %).
 *
 * Next.js edge runtime forbids filesystem reads at request time, so the
 * edge code can't `fs.readFile()` the JSON file. We could `import
 * "../../../../og/layout_v2.json"` directly, but that ties the route to
 * a particular relative path AND defeats type narrowing. Instead, we
 * keep this TS module as the canonical runtime value AND assert
 * byte-equivalent values against the JSON at test time (see
 * `web/src/lib/__tests__/ogLayoutV2.test.ts`).
 *
 * **Synchronisation rule**: if the JSON changes, this file MUST change
 * in the same commit. The vitest mirror-equality test will fail
 * otherwise. This mirrors the v1 tokens.css ↔ tokens.ts convention from
 * ISSUE-091.
 *
 * The Pillow side reads the JSON file directly (Python is not
 * edge-constrained); see `_load_layout_v2()` in `og_bake.py`.
 */

export interface OgLayoutV2Border {
  width_px: number;
  categories: Record<'love' | 'work' | 'money' | 'tarot', string>;
  fallback: string;
}

export interface OgLayoutV2Seal {
  size_px: number;
  tilt: 'left' | 'right';
  tilt_deg: number;
  corner: 'bottom-right';
  margin_px: number;
  vermilion_fill: string;
  baekrim_text: string;
  category_hanja: Record<'love' | 'work' | 'money' | 'tarot' | 'reading-end', string>;
}

export interface OgLayoutV2 {
  version: 'v2';
  canvas: {
    width: number;
    height: number;
    background: string;
    padding: number;
  };
  border: OgLayoutV2Border;
  tilt: { rotate_deg: number };
  grain: { blend_mode: 'multiply'; token: '--grain-strong' };
  seal: OgLayoutV2Seal;
  typography: {
    quote_color: string;
    quote_font_px: number;
    quote_line_height: number;
    watermark_color: string;
    watermark_font_px: number;
  };
}

export const OG_LAYOUT_V2: OgLayoutV2 = {
  version: 'v2',
  canvas: {
    width: 1080,
    height: 1920,
    background: '#1A1208',
    padding: 96,
  },
  border: {
    width_px: 8,
    categories: {
      love: '#B7414B',
      work: '#16344E',
      money: '#B68B3F',
      tarot: '#5A3666',
    },
    fallback: '#6E5A40',
  },
  tilt: {
    rotate_deg: -1.5,
  },
  grain: {
    blend_mode: 'multiply',
    token: '--grain-strong',
  },
  seal: {
    size_px: 168,
    tilt: 'right',
    tilt_deg: 2.5,
    corner: 'bottom-right',
    margin_px: 96,
    vermilion_fill: '#9B2A1A',
    baekrim_text: '#D9C49A',
    category_hanja: {
      love: '戀',
      work: '業',
      money: '財',
      tarot: '月',
      'reading-end': '明',
    },
  },
  typography: {
    quote_color: '#D9C49A',
    quote_font_px: 84,
    quote_line_height: 1.35,
    watermark_color: '#6E5A40',
    watermark_font_px: 36,
  },
};

/** Resolve a border colour for a category with fallback. */
export function v2BorderColorForCategory(category: string): string {
  const map = OG_LAYOUT_V2.border.categories as Record<string, string>;
  return map[category] ?? OG_LAYOUT_V2.border.fallback;
}

/**
 * Resolve a hanja character for a category for the seal corner. Falls
 * back to "印" (generic seal) when the category isn't in the table —
 * never throws, so an unexpected category never bricks the share UX.
 */
export function v2SealHanjaForCategory(category: string): string {
  const map = OG_LAYOUT_V2.seal.category_hanja as Record<string, string>;
  return map[category] ?? '印';
}
