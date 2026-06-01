/**
 * ISSUE-092 — /preview/seal
 *
 * Visual verification surface for the `<Seal>` (印) component. Renders
 * every size / tilt / category combination once on a hanji-themed
 * background so designers (and Playwright, eventually) can pin the
 * stamp's look without depending on production routes.
 *
 * Kept static — no client state, no fetch — for the same reasons as
 * `/preview/v2-tokens`. The route lives outside the production tree so
 * we can ship it without polluting end-user navigation.
 */
import { Seal, SEAL_CATEGORY_HANJA, type SealCategory, type SealSize } from '@/components/seal';

import '@/styles/tokens.css';
import '@/styles/utilities.css';

const SIZES: SealSize[] = ['sm', 'md', 'lg'];
const CATEGORIES = Object.keys(SEAL_CATEGORY_HANJA) as SealCategory[];

export default function SealPreviewPage() {
  return (
    <main
      style={{
        minHeight: '100vh',
        backgroundColor: 'var(--hanji-800)',
        backgroundImage: 'var(--grain-strong)',
        color: 'var(--baekrim-200)',
        fontFamily: 'var(--font-mincho)',
        padding: '48px 24px',
      }}
    >
      <header style={{ marginBottom: '48px' }}>
        <h1
          style={{
            fontFamily: 'var(--font-brush)',
            fontSize: '48px',
            marginBottom: '8px',
          }}
        >
          印 · Seal preview
        </h1>
        <p style={{ opacity: 0.7, maxWidth: '60ch' }}>
          ISSUE-092 / FR-038. Vermilion stamp signature in three sizes and both tilt directions. The
          default render is decorative (<code>aria-hidden</code>); the last row shows the labelled
          signature variant.
        </p>
      </header>

      <section aria-labelledby="seal-sizes" style={{ marginBottom: '48px' }}>
        <h2 id="seal-sizes" style={{ marginBottom: '16px', fontSize: '20px' }}>
          Sizes (sm / md / lg)
        </h2>
        <div style={{ display: 'flex', alignItems: 'center', gap: '24px' }}>
          {SIZES.map((size) => (
            <div key={size} style={{ textAlign: 'center' }}>
              <Seal hanja="戀" size={size} />
              <div style={{ marginTop: '8px', fontSize: '12px', opacity: 0.6 }}>{size}</div>
            </div>
          ))}
        </div>
      </section>

      <section aria-labelledby="seal-tilts" style={{ marginBottom: '48px' }}>
        <h2 id="seal-tilts" style={{ marginBottom: '16px', fontSize: '20px' }}>
          Tilt (left / right)
        </h2>
        <div style={{ display: 'flex', alignItems: 'center', gap: '24px' }}>
          <div style={{ textAlign: 'center' }}>
            <Seal hanja="月" tilt="left" />
            <div style={{ marginTop: '8px', fontSize: '12px', opacity: 0.6 }}>tilt=left</div>
          </div>
          <div style={{ textAlign: 'center' }}>
            <Seal hanja="月" tilt="right" />
            <div style={{ marginTop: '8px', fontSize: '12px', opacity: 0.6 }}>tilt=right</div>
          </div>
        </div>
      </section>

      <section aria-labelledby="seal-categories" style={{ marginBottom: '48px' }}>
        <h2 id="seal-categories" style={{ marginBottom: '16px', fontSize: '20px' }}>
          Category lookup
        </h2>
        <div style={{ display: 'flex', alignItems: 'center', gap: '24px', flexWrap: 'wrap' }}>
          {CATEGORIES.map((category) => (
            <div key={category} style={{ textAlign: 'center' }}>
              <Seal category={category} />
              <div style={{ marginTop: '8px', fontSize: '12px', opacity: 0.6 }}>
                {category} → {SEAL_CATEGORY_HANJA[category]}
              </div>
            </div>
          ))}
        </div>
      </section>

      <section aria-labelledby="seal-labelled">
        <h2 id="seal-labelled" style={{ marginBottom: '16px', fontSize: '20px' }}>
          Labelled signature (aria-label removes aria-hidden)
        </h2>
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <Seal hanja="戀" aria-label="누님이 서명함" />
          <code style={{ opacity: 0.7 }}>aria-label=&quot;누님이 서명함&quot;</code>
        </div>
      </section>
    </main>
  );
}
