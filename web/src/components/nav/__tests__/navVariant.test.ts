/**
 * ISSUE-096 — unit tests for the route → variant resolver.
 *
 * Maps to AC1–AC4 + AC6 (no-flash-of-wrong-chrome relies on the resolver
 * being deterministic and synchronous so React commits the correct variant
 * before paint).
 */
import { describe, expect, it } from 'vitest';
import { resolveNavVariant, activeHanjaTabKey, HANJA_TABS } from '@/components/nav/navVariant';

describe('resolveNavVariant', () => {
  it("returns 'landing' for the root path", () => {
    expect(resolveNavVariant('/')).toBe('landing');
  });

  it("returns 'vertical' for /reading/category exactly", () => {
    expect(resolveNavVariant('/reading/category')).toBe('vertical');
  });

  it('trims a trailing slash before matching', () => {
    // Next.js usually normalises but defensive normalisation prevents a
    // bad-trailing-slash route from falling into 'default'.
    expect(resolveNavVariant('/reading/category/')).toBe('vertical');
    expect(resolveNavVariant('/me/')).toBe('hanja-tab');
  });

  it("returns 'bottom-v2' for /reading/play and any nested route", () => {
    expect(resolveNavVariant('/reading/play')).toBe('bottom-v2');
    expect(resolveNavVariant('/reading/play/followup')).toBe('bottom-v2');
  });

  it("returns 'hanja-tab' for /me and all /me/* routes", () => {
    expect(resolveNavVariant('/me')).toBe('hanja-tab');
    expect(resolveNavVariant('/me/saju')).toBe('hanja-tab');
    expect(resolveNavVariant('/me/history')).toBe('hanja-tab');
    expect(resolveNavVariant('/me/billing')).toBe('hanja-tab');
    expect(resolveNavVariant('/me/account')).toBe('hanja-tab');
  });

  it("returns 'default' for unmapped routes", () => {
    expect(resolveNavVariant('/auth/login')).toBe('default');
    expect(resolveNavVariant('/tarot')).toBe('default');
    expect(resolveNavVariant('/reading/end')).toBe('default');
    expect(resolveNavVariant('/onboarding/birth-date')).toBe('default');
  });

  it('does NOT match /reading/category as a prefix of unrelated routes', () => {
    // Defence against accidental prefix-leak — /reading/category-something
    // should NOT inherit the vertical chrome.
    expect(resolveNavVariant('/reading/category-foo')).toBe('default');
  });

  it('never returns undefined for arbitrary input', () => {
    // Resolver must always commit a variant so React can render synchronously
    // and AC6 (no flash-of-wrong-chrome / CLS < 0.1) holds.
    const inputs = ['/', '/asdf', '/me/x/y/z', '', '/anything-else'];
    for (const i of inputs) {
      const v = resolveNavVariant(i);
      expect(typeof v).toBe('string');
      expect(v.length).toBeGreaterThan(0);
    }
  });
});

describe('HANJA_TABS table (AC4)', () => {
  it('has exactly four tabs in the spec order 家 命 月 我', () => {
    expect(HANJA_TABS).toHaveLength(4);
    expect(HANJA_TABS.map((t) => t.hanja)).toEqual(['家', '命', '月', '我']);
  });

  it('each tab has a Korean aria-label (AC5 — SR announces 홈, not the hanja)', () => {
    const labels = HANJA_TABS.map((t) => t.ariaLabel);
    expect(labels).toEqual(['홈', '사주', '타로', '마이']);
    // None of the aria-labels should leak the hanja character.
    for (const t of HANJA_TABS) {
      expect(t.ariaLabel).not.toContain(t.hanja);
    }
  });

  it('each tab points to a documented Next route', () => {
    const hrefs = HANJA_TABS.map((t) => t.href);
    expect(hrefs).toEqual(['/me', '/me/saju', '/tarot', '/me/account']);
  });
});

describe('activeHanjaTabKey', () => {
  it("returns 'home' for /me exactly", () => {
    expect(activeHanjaTabKey('/me')).toBe('home');
    expect(activeHanjaTabKey('/me/')).toBe('home');
  });

  it("returns 'saju' for /me/saju and any nested route", () => {
    expect(activeHanjaTabKey('/me/saju')).toBe('saju');
    expect(activeHanjaTabKey('/me/saju/edit')).toBe('saju');
  });

  it("returns 'tarot' for /tarot and any nested route", () => {
    expect(activeHanjaTabKey('/tarot')).toBe('tarot');
    expect(activeHanjaTabKey('/tarot/play')).toBe('tarot');
  });

  it("returns 'me' for /me/account and any nested route", () => {
    expect(activeHanjaTabKey('/me/account')).toBe('me');
    expect(activeHanjaTabKey('/me/account/edit')).toBe('me');
  });

  it('returns undefined for /me/history (not a tab destination)', () => {
    // /me/history is a sub-screen of My Page but doesn't map to one of the
    // four hanja anchors — better to show no active state than to mis-
    // assign one.
    expect(activeHanjaTabKey('/me/history')).toBeUndefined();
  });

  it('returns undefined for unrelated routes', () => {
    expect(activeHanjaTabKey('/')).toBeUndefined();
    expect(activeHanjaTabKey('/reading/category')).toBeUndefined();
  });
});
