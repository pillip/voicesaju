/**
 * ISSUE-098 — /preview/utilities
 *
 * Visual + a11y verification surface for the canonical v2 utility
 * classes shipped in `web/src/styles/utilities.css`:
 *   .tilted / .tilted--right / .tilted--more
 *   .reveal-hidden / .reveal-visible
 *   .reveal-show-hide / .reveal-hide
 *   .tap-hint + @keyframes tap-hint-pulse
 *
 * Each utility has its own `data-testid` probe so the Playwright doc
 * spec at `web/tests/e2e/utilities-reveal.spec.ts` can pin computed
 * styles per AC1..AC5 without depending on production wiring.
 *
 * Client component because the reveal/footer toggles run from
 * `useState`. The route still builds statically — Next.js prerenders
 * the initial state and hydrates the toggle handlers on mount.
 */
'use client';

import { useCallback, useState } from 'react';

import '@/styles/tokens.css';
import '@/styles/utilities.css';

const PAGE_STYLE = {
  minHeight: '100vh',
  backgroundColor: 'var(--hanji-800)',
  color: 'var(--baekrim-200)',
  fontFamily: 'var(--font-mincho)',
  padding: '48px 24px',
} as const;

const H2_STYLE = {
  fontSize: '24px',
  marginTop: '48px',
  marginBottom: '16px',
  color: 'var(--baekrim-200)',
} as const;

const CARD_BASE_STYLE = {
  backgroundColor: 'var(--hanji-900)',
  color: 'var(--baekrim-200)',
  padding: '24px 20px',
  width: '200px',
  display: 'inline-block',
  fontFamily: 'var(--font-mincho)',
} as const;

const BUTTON_STYLE = {
  backgroundColor: 'var(--vermilion-500)',
  color: 'var(--baekrim-200)',
  border: 'none',
  padding: '12px 20px',
  fontFamily: 'var(--font-mincho)',
  fontSize: '16px',
  cursor: 'pointer',
  marginRight: '12px',
  minHeight: '44px',
} as const;

export default function UtilitiesPreview() {
  const [revealed, setRevealed] = useState(false);
  const [footerHidden, setFooterHidden] = useState(false);

  const toggleReveal = useCallback(() => setRevealed((v) => !v), []);
  const toggleFooter = useCallback(() => setFooterHidden((v) => !v), []);

  return (
    <main data-testid="utilities-preview" className="vignette-edge" style={PAGE_STYLE}>
      <h1
        style={{
          fontFamily: 'var(--font-brush)',
          fontSize: '48px',
          marginBottom: '8px',
        }}
      >
        v2 Utilities · 印
      </h1>
      <p style={{ marginBottom: '16px', lineHeight: 1.6 }}>
        Canonical `.tilted` / `.reveal-*` / `.tap-hint` utility probes for ISSUE-098. Each card
        carries a `data-testid` so the Playwright doc spec can pin computed styles.
      </p>

      {/* ── AC1 — Tilted family ──────────────────────────────────── */}
      <section aria-labelledby="utilities-tilted">
        <h2 id="utilities-tilted" style={H2_STYLE}>
          .tilted / .tilted--right / .tilted--more
        </h2>
        <div
          style={{
            display: 'flex',
            gap: '32px',
            flexWrap: 'wrap',
            alignItems: 'center',
          }}
        >
          <div data-testid="probe-tilted" className="tilted" style={CARD_BASE_STYLE}>
            .tilted (-1.5°)
          </div>
          <div data-testid="probe-tilted-right" className="tilted--right" style={CARD_BASE_STYLE}>
            .tilted--right (+1.5°)
          </div>
          <div data-testid="probe-tilted-more" className="tilted--more" style={CARD_BASE_STYLE}>
            .tilted--more (-3°)
          </div>
        </div>
      </section>

      {/* ── AC2 — Reveal section fade-in ─────────────────────────── */}
      <section aria-labelledby="utilities-reveal">
        <h2 id="utilities-reveal" style={H2_STYLE}>
          .reveal-hidden ↔ .reveal-visible
        </h2>
        <button
          data-testid="probe-reveal-toggle"
          onClick={toggleReveal}
          style={BUTTON_STYLE}
          aria-pressed={revealed}
          aria-label={revealed ? '숨기기' : '보이기'}
        >
          {revealed ? '숨기기' : '보이기'}
        </button>
        <div
          data-testid="probe-reveal"
          className={revealed ? 'reveal-visible' : 'reveal-hidden'}
          style={{
            ...CARD_BASE_STYLE,
            marginTop: '16px',
            width: '260px',
          }}
        >
          fade-in 400ms · visibility flips instantly on enter
        </div>
      </section>

      {/* ── AC3 — Tap hint pulse ─────────────────────────────────── */}
      <section aria-labelledby="utilities-tap-hint">
        <h2 id="utilities-tap-hint" style={H2_STYLE}>
          .tap-hint (tap-hint-pulse 1.6s ease-in-out infinite)
        </h2>
        <button
          data-testid="probe-tap-hint"
          className="tap-hint"
          style={{
            ...BUTTON_STYLE,
            minWidth: '120px',
            transformOrigin: 'center',
          }}
          aria-label="여기를 탭하세요"
        >
          tap me
        </button>
      </section>

      {/* ── AC5 — Footer hide without CLS ────────────────────────── */}
      <section aria-labelledby="utilities-footer">
        <h2 id="utilities-footer" style={H2_STYLE}>
          .reveal-show-hide ↔ .reveal-hide (footer · no layout shift)
        </h2>
        <button
          data-testid="probe-footer-toggle"
          onClick={toggleFooter}
          style={BUTTON_STYLE}
          aria-pressed={footerHidden}
          aria-label={footerHidden ? '푸터 보이기' : '푸터 숨기기'}
        >
          {footerHidden ? '푸터 보이기' : '푸터 숨기기'}
        </button>
        <footer
          data-testid="probe-footer"
          className={footerHidden ? 'reveal-hide' : 'reveal-show-hide'}
          style={{
            marginTop: '16px',
            padding: '20px',
            backgroundColor: 'var(--hanji-900)',
            color: 'var(--baekrim-200)',
            height: '64px',
          }}
        >
          footer · CLS-safe (visibility:hidden)
        </footer>
      </section>
    </main>
  );
}
