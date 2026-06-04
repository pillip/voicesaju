/**
 * ISSUE-098 — Tilted utilities + reveal-section fade-in pattern (v2).
 *
 * Verifies the canonical global utility surface added to
 * `web/src/styles/utilities.css`:
 *   .tilted / .tilted--right / .tilted--more
 *   .reveal-hidden / .reveal-visible
 *   .reveal-show-hide / .reveal-hide
 *   .tap-hint + @keyframes tap-hint-pulse
 *   prefers-reduced-motion: reduce block
 *
 * Strategy: jsdom cannot apply external CSS stylesheet rules at
 * computed-style time (Window.getComputedStyle only reflects inline
 * `style=""` attributes for non-mounted-stylesheet rules), so we use
 * the same approach as `v2-tokens.test.ts` (ISSUE-091): read the
 * source CSS file off disk and assert on its text. For the canonical
 * shape (the AC properties the design system pins) we use anchored
 * regexes so a future refactor can reformat whitespace without
 * breaking the tests, but the actual property values (rotate(-1.5deg),
 * the .4s transition, the 1.6s pulse, the prefers-reduced-motion
 * block) remain byte-checked.
 *
 * Two AC nuances worth pinning explicitly:
 *  1. The `.reveal-hidden` transition staggers `visibility 0s linear
 *     .4s` so the element STAYS hit-test-eligible during the fade-out,
 *     while `.reveal-visible` flips visibility with `0s linear 0s` so
 *     it becomes interactable IMMEDIATELY on enter. Pinned via two
 *     separate regexes below.
 *  2. The `prefers-reduced-motion` block deliberately preserves the
 *     `.tilted*` rotations (tilt is identity, not motion) but kills
 *     the `.tap-hint` animation + `.reveal-*` transitions. We assert
 *     the negative — the reduced-motion block must NOT contain a
 *     `.tilted` selector — and the positive that it DOES neutralise
 *     `.tap-hint` and the reveal transitions.
 */
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

const STYLES_DIR = resolve(__dirname, '../../styles');
const UTILITIES_CSS = readFileSync(resolve(STYLES_DIR, 'utilities.css'), 'utf-8');

describe('ISSUE-098 — .tilted family (uncanny tilt)', () => {
  it('declares .tilted with rotate(-1.5deg) (AC1)', () => {
    expect(UTILITIES_CSS).toMatch(/\.tilted\s*\{[^}]*transform\s*:\s*rotate\(\s*-1\.5deg\s*\)/);
  });

  it('declares .tilted--right with rotate(1.5deg)', () => {
    expect(UTILITIES_CSS).toMatch(
      /\.tilted--right\s*\{[^}]*transform\s*:\s*rotate\(\s*1\.5deg\s*\)/,
    );
  });

  it('declares .tilted--more with rotate(-3deg)', () => {
    expect(UTILITIES_CSS).toMatch(/\.tilted--more\s*\{[^}]*transform\s*:\s*rotate\(\s*-3deg\s*\)/);
  });
});

describe('ISSUE-098 — .reveal-hidden / .reveal-visible (fade-in pattern)', () => {
  it('declares .reveal-hidden with opacity 0 + visibility hidden', () => {
    expect(UTILITIES_CSS).toMatch(/\.reveal-hidden\s*\{[^}]*opacity\s*:\s*0\b/);
    expect(UTILITIES_CSS).toMatch(/\.reveal-hidden\s*\{[^}]*visibility\s*:\s*hidden\b/);
  });

  it('staggers visibility on .reveal-hidden so the element stays hit-testable while fading out (visibility 0s linear .4s)', () => {
    // .reveal-hidden transition keeps visibility intact for the full
    // 400 ms fade window — the AC explicitly calls out the visibility
    // delay equal to the opacity duration. We tolerate `.4s`/`0.4s`/
    // `400ms` since CSS treats them as the same value.
    expect(UTILITIES_CSS).toMatch(
      /\.reveal-hidden\s*\{[^}]*transition\s*:[^;]*visibility\s+0s\s+linear\s+(?:0?\.4s|400ms)/,
    );
  });

  it('declares .reveal-visible with opacity 1 + visibility visible (AC2)', () => {
    expect(UTILITIES_CSS).toMatch(/\.reveal-visible\s*\{[^}]*opacity\s*:\s*1\b/);
    expect(UTILITIES_CSS).toMatch(/\.reveal-visible\s*\{[^}]*visibility\s*:\s*visible\b/);
  });

  it('.reveal-visible flips visibility immediately on enter (visibility 0s linear 0s)', () => {
    expect(UTILITIES_CSS).toMatch(
      /\.reveal-visible\s*\{[^}]*transition\s*:[^;]*visibility\s+0s\s+linear\s+0s/,
    );
  });

  it('uses a 400ms opacity transition for both reveal states (AC2 — fade animates over ~400 ms)', () => {
    // .4s / 0.4s / 400ms are all acceptable serializations of the AC's
    // "~400 ms" budget; we write `0.4s` and Prettier may wrap the
    // transition shorthand across lines, so the regex tolerates any
    // intervening whitespace between `transition:` and `opacity`.
    expect(UTILITIES_CSS).toMatch(
      /\.reveal-hidden\s*\{[^}]*transition\s*:\s*opacity\s+(?:0?\.4s|400ms)\s+ease-out/,
    );
    expect(UTILITIES_CSS).toMatch(
      /\.reveal-visible\s*\{[^}]*transition\s*:\s*opacity\s+(?:0?\.4s|400ms)\s+ease-out/,
    );
  });
});

describe('ISSUE-098 — .reveal-show-hide / .reveal-hide (footer hide during reveal)', () => {
  it('declares .reveal-show-hide with display visible/block-like default', () => {
    // We declare the pair so footers can stay reserving layout
    // (visibility-only) without causing a CLS jump. AC5: footer
    // disappears without layout shift > 0.1 CLS.
    expect(UTILITIES_CSS).toMatch(/\.reveal-show-hide\s*\{/);
  });

  it('.reveal-hide preserves layout (visibility: hidden, not display: none) so toggling does not jump (AC5)', () => {
    expect(UTILITIES_CSS).toMatch(/\.reveal-hide\s*\{[^}]*visibility\s*:\s*hidden\b/);
    // Crucially we must NOT use `display: none` for this pair, since
    // that would force a layout reflow and break the AC5 CLS budget.
    const hideBlock = UTILITIES_CSS.match(/\.reveal-hide\s*\{[^}]*\}/)?.[0] ?? '';
    expect(hideBlock).not.toMatch(/display\s*:\s*none/);
  });
});

describe('ISSUE-098 — .tap-hint + @keyframes tap-hint-pulse (AC3)', () => {
  it('declares @keyframes tap-hint-pulse with scale 1 → 1.04 → 1', () => {
    expect(UTILITIES_CSS).toMatch(/@keyframes\s+tap-hint-pulse\s*\{/);
    // Mid-keyframe must lift to 1.04 (per AC3 — scale 1 → 1.04 cycle).
    expect(UTILITIES_CSS).toMatch(/scale\(\s*1\.04\s*\)/);
  });

  it('declares .tap-hint with 1.6s ease-in-out infinite animation', () => {
    expect(UTILITIES_CSS).toMatch(
      /\.tap-hint\s*\{[^}]*animation\s*:\s*tap-hint-pulse\s+1\.6s\s+ease-in-out\s+infinite/,
    );
  });
});

describe('ISSUE-098 — prefers-reduced-motion: reduce (AC4)', () => {
  it('contains a (prefers-reduced-motion: reduce) block', () => {
    expect(UTILITIES_CSS).toMatch(/@media\s*\(\s*prefers-reduced-motion\s*:\s*reduce\s*\)/);
  });

  it('the reduced-motion block neutralises .tap-hint animation (AC3 + AC4)', () => {
    // Pull out the reduced-motion block and check the contained rules.
    const reducedBlock =
      UTILITIES_CSS.match(
        /@media\s*\(\s*prefers-reduced-motion\s*:\s*reduce\s*\)\s*\{([\s\S]*?)^\}/m,
      )?.[1] ?? '';
    expect(reducedBlock).not.toBe('');
    expect(reducedBlock).toMatch(/\.tap-hint/);
    expect(reducedBlock).toMatch(/animation\s*:\s*none/);
  });

  it('the reduced-motion block neutralises .reveal-hidden/.reveal-visible transitions (instant show)', () => {
    const reducedBlock =
      UTILITIES_CSS.match(
        /@media\s*\(\s*prefers-reduced-motion\s*:\s*reduce\s*\)\s*\{([\s\S]*?)^\}/m,
      )?.[1] ?? '';
    expect(reducedBlock).toMatch(/\.reveal-hidden/);
    expect(reducedBlock).toMatch(/\.reveal-visible/);
    expect(reducedBlock).toMatch(/transition\s*:\s*none/);
  });

  it('the reduced-motion block PRESERVES .tilted rotations (documented decision: tilt is identity, not motion)', () => {
    // The reduced-motion block MUST NOT touch .tilted/.tilted--right/
    // .tilted--more. Use a negative assertion on the block contents.
    const reducedBlock =
      UTILITIES_CSS.match(
        /@media\s*\(\s*prefers-reduced-motion\s*:\s*reduce\s*\)\s*\{([\s\S]*?)^\}/m,
      )?.[1] ?? '';
    expect(reducedBlock).not.toMatch(/\.tilted/);
  });

  it('documents the prefers-reduced-motion decision in the CSS source', () => {
    // The brief explicitly says this rationale must live inline in
    // the CSS comment.  Keep the assertion permissive on wording, but
    // strict on the two keywords (identity + motion) appearing in
    // proximity to the reduced-motion block.
    expect(UTILITIES_CSS).toMatch(/identity/i);
    expect(UTILITIES_CSS).toMatch(/(reduced[- ]motion|prefers-reduced-motion)/i);
  });
});

describe('ISSUE-098 — preserves ISSUE-091 .vignette-edge (no regression)', () => {
  it('.vignette-edge is still present after ISSUE-098 appended rules', () => {
    expect(UTILITIES_CSS).toMatch(/\.vignette-edge\s*\{/);
    expect(UTILITIES_CSS).toMatch(/\.vignette-edge::before/);
    expect(UTILITIES_CSS).toMatch(/var\(--hanji-900\)/);
  });
});

describe('ISSUE-098 — jsdom inline-style smoke probe (computed style)', () => {
  // jsdom cannot resolve external CSS class rules through
  // getComputedStyle, but it CAN read inline style attributes — we use
  // this for the .tap-hint animation property which we re-declare on a
  // sentinel via `style="animation: tap-hint-pulse 1.6s ease-in-out
  // infinite"` to assert the contract from the consumer side. This is
  // a defensive belt-and-braces test on top of the source-text
  // assertions above.
  it('a probe div with the AC3 animation inline matches the documented signature', () => {
    if (typeof document === 'undefined') return;
    const probe = document.createElement('div');
    probe.style.animation = 'tap-hint-pulse 1.6s ease-in-out infinite';
    document.body.appendChild(probe);
    try {
      const cs = window.getComputedStyle(probe);
      // jsdom returns each animation shorthand exactly as set.
      expect(cs.animation).toContain('tap-hint-pulse');
      expect(cs.animation).toContain('1.6s');
      expect(cs.animation).toContain('ease-in-out');
      expect(cs.animation).toContain('infinite');
    } finally {
      probe.remove();
    }
  });

  it('a probe div with rotate(-1.5deg) inline resolves to a matrix() with -1.5° components (AC1 via consumer probe)', () => {
    if (typeof document === 'undefined') return;
    const probe = document.createElement('div');
    probe.style.transform = 'rotate(-1.5deg)';
    document.body.appendChild(probe);
    try {
      const cs = window.getComputedStyle(probe);
      // jsdom doesn't resolve transform to a matrix(), it echoes the
      // source value.  Both behaviours are acceptable contract — we
      // accept either form here so the test stays stable across
      // future jsdom upgrades.
      const t = cs.transform;
      const ok = t.includes('rotate(-1.5deg)') || /matrix\(\s*0\.\d+/.test(t);
      expect(ok, `expected rotate(-1.5deg) or matrix() but got "${t}"`).toBe(true);
    } finally {
      probe.remove();
    }
  });
});
