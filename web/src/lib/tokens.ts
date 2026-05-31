/**
 * ISSUE-091 — v2 design tokens (typed TS mirror of tokens.css).
 *
 * These constants exist so React/TS code can refer to v2 tokens
 * without hard-coding hex values, AND so the byte-equality test in
 * `v2-tokens.test.ts` can detect drift between the CSS file and TS.
 *
 * Authoritative source (hex values, font stacks): docs/design_system.md
 * §"v2 ADDITIONS — 새 토큰". If a value changes there, update both
 * `tokens.css` and this file in the same commit — the test will fail
 * otherwise.
 *
 * v1 tokens are NOT mirrored here yet — they live in tailwind.config.ts
 * (see web/src/components/ui/__tests__/tokens.test.tsx for the v1
 * snapshot). Mirroring v1 is out of scope for ISSUE-091; the v1 + v2
 * token systems must coexist throughout M2.5 (issues 092..098).
 */

export const V2_COLOR_TOKENS = {
  "--vermilion-100": "#C95F4A",
  "--vermilion-300": "#9B2A1A",
  "--vermilion-500": "#6C1D11",
  "--hanji-900": "#0A0604",
  "--hanji-800": "#1A1208",
  "--hanji-700": "#241810",
  "--hanji-500": "#3A2A18",
  "--hanji-300": "#6E5A40",
  "--baekrim-200": "#D9C49A",
} as const;

export const V2_FONT_TOKENS = {
  "--font-brush": "'Nanum Brush Script', 'East Sea Dokdo', cursive",
  "--font-mincho": "'Noto Serif KR', 'Gowun Batang', serif",
} as const;

/**
 * Inline SVG noise data URI. Kept here as a single source so component
 * code can compose `background-image: ${V2_GRAIN_TOKENS["--grain-strong"]}`
 * directly in TS-driven style objects without re-encoding the SVG.
 */
export const V2_GRAIN_TOKENS = {
  "--grain-strong":
    "url(\"data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 200 200'><filter id='n'><feTurbulence type='fractalNoise' baseFrequency='0.9'/></filter><rect width='100%25' height='100%25' filter='url(%23n)' opacity='0.10'/></svg>\")",
} as const;

export type V2ColorTokenName = keyof typeof V2_COLOR_TOKENS;
export type V2FontTokenName = keyof typeof V2_FONT_TOKENS;
export type V2GrainTokenName = keyof typeof V2_GRAIN_TOKENS;
export type V2TokenName = V2ColorTokenName | V2FontTokenName | V2GrainTokenName;

/** Flat list of every v2 custom-property name — used by drift tests. */
export const V2_TOKEN_NAMES: readonly V2TokenName[] = [
  ...(Object.keys(V2_COLOR_TOKENS) as V2ColorTokenName[]),
  ...(Object.keys(V2_FONT_TOKENS) as V2FontTokenName[]),
  ...(Object.keys(V2_GRAIN_TOKENS) as V2GrainTokenName[]),
];

/** Convenience helper: produce a `var(--token-name)` reference string. */
export function v2Var(token: V2TokenName): string {
  return `var(${token})`;
}
