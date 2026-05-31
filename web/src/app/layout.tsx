import type { Metadata } from "next";
import {
  Nanum_Brush_Script,
  Noto_Serif_KR,
  Cormorant_Garamond,
} from "next/font/google";

import "./globals.css";
import "@/styles/tokens.css";
import "@/styles/utilities.css";
import { RuntimeProvider } from "@/lib/context/runtime-context";

/**
 * ISSUE-091 — v2 typography loaders.
 *
 * - `Nanum Brush Script` — single weight variant. `display: 'swap'`
 *   because the brush font is decorative; we never want it blocking
 *   paint.
 * - `Noto Serif KR` weight 900 ONLY — the full family is multi-megabyte
 *   per weight; the v2 `--font-mincho` stack falls back to Gowun Batang
 *   for non-display copy. `preload: false` so Next does not eagerly
 *   block on the large file.
 * - `Cormorant Garamond` — Latin display serif used alongside the v1
 *   `--font-accent` token.
 *
 * Each font sets a `--next-font-*` CSS variable on <html>; the
 * v2 `--font-brush` / `--font-mincho` tokens in tokens.css still
 * declare the documented font-family stack so component CSS does not
 * need to know about next/font's hashed family names.
 */
const nanumBrush = Nanum_Brush_Script({
  weight: "400",
  subsets: ["latin"],
  display: "swap",
  variable: "--next-font-brush",
});

const notoSerifKr = Noto_Serif_KR({
  weight: ["900"],
  subsets: ["latin"],
  display: "swap",
  preload: false,
  variable: "--next-font-mincho",
});

const cormorant = Cormorant_Garamond({
  weight: ["300", "400", "500"],
  style: ["normal", "italic"],
  subsets: ["latin"],
  display: "swap",
  variable: "--next-font-accent",
});

export const metadata: Metadata = {
  title: "VoiceSaju",
  description: "AI-powered Saju reading and daily tarot service.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="ko"
      className={`${nanumBrush.variable} ${notoSerifKr.variable} ${cormorant.variable}`}
    >
      <head>
        <link
          rel="stylesheet"
          href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.min.css"
        />
      </head>
      <body className="font-sans antialiased">
        <RuntimeProvider>{children}</RuntimeProvider>
      </body>
    </html>
  );
}
