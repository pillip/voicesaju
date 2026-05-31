/**
 * ISSUE-091 — /preview/v2-tokens
 *
 * Visual + a11y verification surface for the v2 design tokens. Mounted
 * outside the production routes so designers can hit it directly while
 * the rest of M2.5 (ISSUE-092..098) is still in flight. The route MUST
 * stay free of dynamic data — its only job is to render every v2 token
 * once so axe-core (AC5) and Playwright can pin them.
 *
 * NOTE: Background image references use `var(--grain-strong)` for the
 * inline-SVG noise, NOT a static asset path. This keeps the token
 * indirection intact and is what the AC4 computed-style smoke asserts.
 */
import { V2_COLOR_TOKENS } from "@/lib/tokens";

import "@/styles/tokens.css";
import "@/styles/utilities.css";

const COLOR_ENTRIES = Object.entries(V2_COLOR_TOKENS);

export default function V2TokensPreview() {
  return (
    <main
      className="vignette-edge"
      style={{
        minHeight: "100vh",
        backgroundColor: "var(--hanji-800)",
        backgroundImage: "var(--grain-strong)",
        color: "var(--baekrim-200)",
        fontFamily: "var(--font-mincho)",
        padding: "48px 24px",
      }}
    >
      <h1
        style={{
          fontFamily: "var(--font-brush)",
          fontSize: "48px",
          marginBottom: "8px",
          color: "var(--baekrim-200)",
        }}
      >
        v2 Token Preview · 印
      </h1>
      <p
        style={{
          color: "var(--baekrim-200)",
          backgroundColor: "var(--hanji-900)",
          padding: "12px 16px",
          marginBottom: "32px",
          fontSize: "18px",
          lineHeight: 1.6,
        }}
      >
        baekrim-200 텍스트 on hanji-900 배경 — 대비 ≥ 4.5:1 (NFR-012).
      </p>

      <section aria-labelledby="v2-color-swatches">
        <h2
          id="v2-color-swatches"
          style={{
            fontSize: "24px",
            marginBottom: "16px",
            color: "var(--baekrim-200)",
          }}
        >
          Color Swatches
        </h2>
        <ul
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))",
            gap: "16px",
            listStyle: "none",
            padding: 0,
            margin: 0,
          }}
        >
          {COLOR_ENTRIES.map(([name, hex]) => (
            <li
              key={name}
              style={{
                backgroundColor: hex,
                color: name.startsWith("--baekrim")
                  ? "var(--hanji-900)"
                  : "var(--baekrim-200)",
                padding: "24px 16px",
                fontFamily: "monospace",
                fontSize: "14px",
              }}
            >
              <div>{name}</div>
              <div>{hex}</div>
            </li>
          ))}
        </ul>
      </section>

      <section aria-labelledby="v2-type-stacks" style={{ marginTop: "48px" }}>
        <h2
          id="v2-type-stacks"
          style={{
            fontSize: "24px",
            marginBottom: "16px",
            color: "var(--baekrim-200)",
          }}
        >
          Typography Stacks
        </h2>
        <p style={{ fontFamily: "var(--font-brush)", fontSize: "40px" }}>
          Nanum Brush — 손글씨 가격표
        </p>
        <p
          style={{
            fontFamily: "var(--font-mincho)",
            fontSize: "40px",
            fontWeight: 900,
          }}
        >
          Noto Serif KR — 한자 모뉴멘탈
        </p>
      </section>
    </main>
  );
}
