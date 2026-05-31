/**
 * ISSUE-091 — v2 design tokens (Ink, Amber & 印).
 *
 * These tests pin the source-text of the new token files so the CSS
 * custom properties stay byte-identical with the TS typed exports.
 * `getComputedStyle` is exercised via jsdom for a smoke check on
 * `--vermilion-500` (AC1) and `--grain-strong` (AC4); the resolved
 * font-family + radial-gradient assertions (AC2, AC3) live in the
 * preview route test where actual DOM rendering happens.
 *
 * v1 tokens are NOT touched — see tokens.test.tsx for the v1 anchors.
 */
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

import {
  V2_COLOR_TOKENS,
  V2_FONT_TOKENS,
  V2_GRAIN_TOKENS,
  V2_TOKEN_NAMES,
} from "@/lib/tokens";

const STYLES_DIR = resolve(__dirname, "../../styles");
const TOKENS_CSS = readFileSync(resolve(STYLES_DIR, "tokens.css"), "utf-8");
const UTILITIES_CSS = readFileSync(
  resolve(STYLES_DIR, "utilities.css"),
  "utf-8",
);

describe("ISSUE-091 — tokens.css declares v2 vermilion + hanji + baekrim", () => {
  it.each([
    ["--vermilion-100", "#C95F4A"],
    ["--vermilion-300", "#9B2A1A"],
    ["--vermilion-500", "#6C1D11"],
    ["--hanji-900", "#0A0604"],
    ["--hanji-800", "#1A1208"],
    ["--hanji-700", "#241810"],
    ["--hanji-500", "#3A2A18"],
    ["--hanji-300", "#6E5A40"],
    ["--baekrim-200", "#D9C49A"],
  ])("declares %s = %s (per design_system.md §v2 ADDITIONS)", (name, hex) => {
    const re = new RegExp(
      `${name}\\s*:\\s*${hex.replace(/[-/\\^$*+?.()|[\]{}]/g, "\\$&")}\\s*;`,
      "i",
    );
    expect(TOKENS_CSS).toMatch(re);
  });

  it("declares --font-brush, --font-mincho with the documented stacks", () => {
    expect(TOKENS_CSS).toMatch(/--font-brush\s*:\s*['"]Nanum Brush Script['"]/);
    expect(TOKENS_CSS).toMatch(/--font-mincho\s*:\s*['"]Noto Serif KR['"]/);
  });

  it("declares --grain-strong as an inline SVG data URI noise", () => {
    expect(TOKENS_CSS).toMatch(
      /--grain-strong\s*:\s*url\(["']data:image\/svg\+xml,/,
    );
    expect(TOKENS_CSS).toMatch(/feTurbulence/);
  });
});

describe("ISSUE-091 — tokens.ts mirrors tokens.css byte-identical", () => {
  it("V2_COLOR_TOKENS keys match the CSS --vermilion/--hanji/--baekrim names", () => {
    const expected = [
      "--vermilion-100",
      "--vermilion-300",
      "--vermilion-500",
      "--hanji-900",
      "--hanji-800",
      "--hanji-700",
      "--hanji-500",
      "--hanji-300",
      "--baekrim-200",
    ];
    expect(Object.keys(V2_COLOR_TOKENS).sort()).toEqual(expected.sort());
  });

  it.each([
    ["--vermilion-100", "#C95F4A"],
    ["--vermilion-300", "#9B2A1A"],
    ["--vermilion-500", "#6C1D11"],
    ["--hanji-900", "#0A0604"],
    ["--hanji-800", "#1A1208"],
    ["--hanji-700", "#241810"],
    ["--hanji-500", "#3A2A18"],
    ["--hanji-300", "#6E5A40"],
    ["--baekrim-200", "#D9C49A"],
  ])("V2_COLOR_TOKENS[%s] === %s", (name, hex) => {
    expect(V2_COLOR_TOKENS[name as keyof typeof V2_COLOR_TOKENS]).toBe(hex);
  });

  it("V2_FONT_TOKENS exposes brush + mincho stacks", () => {
    expect(V2_FONT_TOKENS["--font-brush"]).toMatch(/Nanum Brush Script/);
    expect(V2_FONT_TOKENS["--font-mincho"]).toMatch(/Noto Serif KR/);
  });

  it("V2_GRAIN_TOKENS --grain-strong is an inline SVG data URI", () => {
    expect(V2_GRAIN_TOKENS["--grain-strong"]).toMatch(
      /^url\(["']data:image\/svg\+xml,/,
    );
    expect(V2_GRAIN_TOKENS["--grain-strong"]).toMatch(/feTurbulence/);
  });

  it("every TS key appears in tokens.css (string equality)", () => {
    for (const name of V2_TOKEN_NAMES) {
      expect(TOKENS_CSS, `${name} missing from tokens.css`).toContain(name);
    }
  });
});

describe("ISSUE-091 — utilities.css declares .vignette-edge radial gradient", () => {
  it("declares .vignette-edge with a radial-gradient overlay", () => {
    expect(UTILITIES_CSS).toMatch(/\.vignette-edge/);
    expect(UTILITIES_CSS).toMatch(/radial-gradient\s*\(/);
  });

  it("references --hanji-900 as the vignette edge color (per design_system.md)", () => {
    expect(UTILITIES_CSS).toMatch(/var\(--hanji-900\)/);
  });
});
