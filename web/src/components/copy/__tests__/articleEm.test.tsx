/**
 * ISSUE-097 — global `article em` marker-highlight rule (AC4).
 *
 * The rule lives in `web/src/styles/copy-system.css` inside the
 * `@layer copy-system` cascade. jsdom does not run the CSS engine for
 * `linear-gradient(...)` so we cannot resolve the computed background
 * via `getComputedStyle()`; instead we read the stylesheet source and
 * assert the documented selector + gradient stops are present.
 *
 * This protects against accidental rule removal during the v2 → v3
 * migration window. A future refactor that drops the rule must
 * intentionally update this test, making the divergence explicit.
 */

import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

import { describe, expect, it } from 'vitest';

const CSS_PATH = resolve(__dirname, '../../../styles/copy-system.css');
const css = readFileSync(CSS_PATH, 'utf8');

describe('copy-system.css — ISSUE-097 AC4 (article em marker)', () => {
  it('declares an `article em` rule', () => {
    expect(css).toMatch(/article\s+em\s*\{/);
  });

  it('uses a linear-gradient stopping at 60% for the marker stripe', () => {
    expect(css).toContain('linear-gradient(180deg, transparent 60%');
  });

  it('uses the vermilion ink at low opacity (~0.22) for the highlight', () => {
    // The exact rgba is locked in by the issue spec so a future tweak is intentional.
    expect(css).toContain('rgba(155, 42, 26, 0.22)');
  });

  it('lives inside @layer copy-system so Tailwind utilities can still override', () => {
    expect(css).toMatch(/@layer\s+copy-system\s*\{/);
  });
});

describe('copy-system.css — ISSUE-097 AC5 (data-pause leading)', () => {
  it('declares a `br[data-pause]` rule', () => {
    expect(css).toMatch(/br\[data-pause\]\s*\{/);
  });

  it('uses margin-block-start to insert a visible breath after the break', () => {
    expect(css).toContain('margin-block-start');
  });
});
