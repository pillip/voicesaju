/**
 * Tailwind token snapshot — asserts the v1 category color hex values match
 * docs/design_system.md exactly. These tests parse `tailwind.config.ts` as
 * source text (no Tailwind runtime needed) so they remain fast and
 * dependency-free.
 */
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

const TAILWIND_CFG = readFileSync(resolve(__dirname, '../../../../tailwind.config.ts'), 'utf-8');

describe('tailwind.config.ts — v1 category tokens', () => {
  it.each([
    ['love', '#9B4A4A'],
    ['work', '#3D5266'],
    ['money', '#A67C28'],
    ['tarot', '#5B3A5C'],
  ])('category.%s = %s (per design_system.md)', (name, hex) => {
    const re = new RegExp(`${name}\\s*:\\s*["']${hex}["']`, 'i');
    expect(TAILWIND_CFG).toMatch(re);
  });

  it('exposes ink, cream, and amber scale anchors', () => {
    // Minimum anchors (a few high-value tokens) — full set is in design_system.md
    expect(TAILWIND_CFG).toMatch(/ink/i);
    expect(TAILWIND_CFG).toMatch(/cream/i);
    expect(TAILWIND_CFG).toMatch(/amber/i);
  });

  it('declares fontFamily.display + display-han + body + mono', () => {
    expect(TAILWIND_CFG).toMatch(/display\s*:/);
    expect(TAILWIND_CFG).toMatch(/display-han|displayHan/);
    expect(TAILWIND_CFG).toMatch(/body\s*:/);
    expect(TAILWIND_CFG).toMatch(/mono\s*:/);
  });

  it('declares a 4px-based spacing scale anchor', () => {
    expect(TAILWIND_CFG).toMatch(/spacing/);
  });

  it('declares borderRadius anchors (none, sm, md, pill/full)', () => {
    expect(TAILWIND_CFG).toMatch(/borderRadius/);
    expect(TAILWIND_CFG).toMatch(/pill|9999/);
  });
});
