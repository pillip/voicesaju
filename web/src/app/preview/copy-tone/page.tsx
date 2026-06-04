/**
 * ISSUE-097 — /preview/copy-tone
 *
 * Visual verification surface for the copy tone system primitives. Lays
 * out every component once against a hanji background so designers
 * (and Playwright, eventually) can pin the typographic look without
 * depending on production routes.
 *
 * Kept static — no client state, no fetch — same convention as
 * `/preview/seal`, `/preview/hanja-saju`, `/preview/v2-tokens`. The
 * route lives outside the production tree so we can ship it without
 * polluting end-user navigation.
 *
 * The page intentionally exercises:
 *   - <HandwrittenPrice value="4,900원" /> (AC1)
 *   - <HandwrittenNote tilt={-1.5} /> + tilt={-3} (AC2)
 *   - <SignedMark /> (AC3)
 *   - <article><em>중요한 말</em></article> marker rule (AC4)
 *   - <Pause /> inside a paragraph (AC5)
 *
 * copy-lint: formal-ok — preview surface, exempted at the directory
 * level via SKIP_DIR_NAMES; the marker is documented for parity.
 */
import { HandwrittenNote, HandwrittenPrice, Pause, SignedMark } from '@/components/copy';

import '@/styles/tokens.css';
import '@/styles/utilities.css';
import '@/styles/copy-system.css';

const PANEL_STYLE = {
  backgroundColor: 'var(--hanji-800)',
  backgroundImage: 'var(--grain-strong)',
  color: 'var(--cream-300)',
  padding: '32px',
  borderRadius: '12px',
  marginBottom: '24px',
  fontFamily: 'var(--font-mincho)',
} as const;

const LABEL_STYLE = {
  fontFamily: 'var(--font-accent)',
  fontSize: '12px',
  letterSpacing: '0.08em',
  textTransform: 'uppercase',
  color: 'var(--cream-300)',
  opacity: 0.6,
  marginBottom: '8px',
} as const;

export default function CopyTonePreviewPage() {
  return (
    <main
      style={{
        minHeight: '100vh',
        backgroundColor: 'var(--ink-900)',
        color: 'var(--cream-300)',
        fontFamily: 'var(--font-mincho)',
        padding: '48px 24px',
      }}
    >
      <header style={{ marginBottom: '48px' }}>
        <h1 style={{ fontFamily: 'var(--font-brush)', fontSize: '48px', marginBottom: '8px' }}>
          Copy Tone System
        </h1>
        <p style={{ fontSize: '14px', opacity: 0.7 }}>
          ISSUE-097 / FR-043 — typographic primitives for the 누님 voice.
        </p>
      </header>

      {/* AC1 — HandwrittenPrice */}
      <section style={PANEL_STYLE} aria-labelledby="ac1">
        <p style={LABEL_STYLE} id="ac1">
          AC1 · HandwrittenPrice
        </p>
        <p style={{ fontFamily: 'var(--font-mincho)', fontSize: '18px' }}>
          한 잔에 <HandwrittenPrice value="4,900원" /> · 너 정도면 충분해.
        </p>
      </section>

      {/* AC2 — HandwrittenNote tilt -1.5 / -3 */}
      <section style={PANEL_STYLE} aria-labelledby="ac2">
        <p style={LABEL_STYLE} id="ac2">
          AC2 · HandwrittenNote (tilt -1.5 / -3)
        </p>
        <p style={{ fontFamily: 'var(--font-mincho)', fontSize: '18px' }}>
          이게 그 사주야. <HandwrittenNote>흠… 진심이긴 해</HandwrittenNote>
        </p>
        <p style={{ fontFamily: 'var(--font-mincho)', fontSize: '18px', marginTop: '12px' }}>
          그래도 봐줘. <HandwrittenNote tilt={-3}>(곁말)</HandwrittenNote>
        </p>
      </section>

      {/* AC3 — SignedMark */}
      <section style={PANEL_STYLE} aria-labelledby="ac3">
        <p style={LABEL_STYLE} id="ac3">
          AC3 · SignedMark
        </p>
        <p style={{ fontFamily: 'var(--font-mincho)', fontSize: '18px' }}>오늘 풀이 끝.</p>
        <div style={{ marginTop: '12px' }}>
          <SignedMark />
        </div>
      </section>

      {/* AC4 — article em marker */}
      <section style={PANEL_STYLE} aria-labelledby="ac4">
        <p style={LABEL_STYLE} id="ac4">
          AC4 · article em marker
        </p>
        <article style={{ fontFamily: 'var(--font-mincho)', fontSize: '18px', lineHeight: 1.6 }}>
          <p>
            그 사람은 <em>너랑 코드가 안 맞아</em>. 받아쳐.
          </p>
        </article>
      </section>

      {/* AC5 — Pause */}
      <section style={PANEL_STYLE} aria-labelledby="ac5">
        <p style={LABEL_STYLE} id="ac5">
          AC5 · Pause
        </p>
        <p style={{ fontFamily: 'var(--font-mincho)', fontSize: '18px' }}>
          흠.
          <Pause />
          이 시간에 사주를 본다고?
          <Pause />
          어디 보자.
        </p>
      </section>
    </main>
  );
}
