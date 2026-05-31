/**
 * ISSUE-091 — /preview/v2-tokens route.
 *
 * Renders the preview page in jsdom + asserts:
 *  - AC1: `var(--vermilion-500)` resolves to a non-empty color value via
 *    `getComputedStyle` after injecting the tokens.css custom-property
 *    declarations into the document root.
 *  - AC3: An element with the `vignette-edge` class is mounted on the page
 *    (the radial-gradient overlay rendering is verified at the CSS source
 *    level in v2-tokens.test.ts; jsdom does not paint pseudo-elements).
 *  - AC4: `--grain-strong` resolves to a `url("data:image/svg+xml,...")`
 *    custom property value after injection (smoke check).
 *  - AC5: axe-core finds zero violations on the swatch grid (NFR-012).
 *
 * NOTE: Pretty-printing the page does not load real fonts in jsdom; the
 * `var(--font-brush)` -> "Nanum Brush Script" assertion is covered by the
 * source-text test in v2-tokens.test.ts.
 */
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { render } from "@testing-library/react";
import { axe } from "jest-axe";
import { describe, expect, it, beforeAll, afterAll } from "vitest";

import V2TokensPreview from "../page";

let styleEl: HTMLStyleElement | null = null;

beforeAll(() => {
  // Inject tokens.css + utilities.css as raw text so jsdom resolves
  // `getComputedStyle(...).getPropertyValue('--vermilion-500')`.
  const tokensCss = readFileSync(
    resolve(__dirname, "../../../../styles/tokens.css"),
    "utf-8",
  );
  const utilitiesCss = readFileSync(
    resolve(__dirname, "../../../../styles/utilities.css"),
    "utf-8",
  );
  styleEl = document.createElement("style");
  styleEl.textContent = `${tokensCss}\n${utilitiesCss}`;
  document.head.appendChild(styleEl);
});

afterAll(() => {
  if (styleEl) styleEl.remove();
});

describe("ISSUE-091 — /preview/v2-tokens", () => {
  it("AC1: var(--vermilion-500) resolves via getComputedStyle (non-empty)", () => {
    render(<V2TokensPreview />);
    const root = document.documentElement;
    const value = getComputedStyle(root)
      .getPropertyValue("--vermilion-500")
      .trim();
    expect(value).not.toBe("");
    expect(value.toLowerCase()).toBe("#6c1d11");
  });

  it("AC3: page mounts an element with the vignette-edge class", () => {
    const { container } = render(<V2TokensPreview />);
    const vignette = container.querySelector(".vignette-edge");
    expect(vignette).not.toBeNull();
  });

  it("AC4: --grain-strong resolves to an inline svg data URI", () => {
    render(<V2TokensPreview />);
    const value = getComputedStyle(document.documentElement)
      .getPropertyValue("--grain-strong")
      .trim();
    expect(value).toMatch(/^url\(["']?data:image\/svg\+xml,/);
  });

  it("AC5: axe-core finds zero AA violations on the hanji-900/baekrim-200 fixture", async () => {
    const { container } = render(<V2TokensPreview />);
    const results = await axe(container);
    expect(results.violations).toEqual([]);
  });
});
