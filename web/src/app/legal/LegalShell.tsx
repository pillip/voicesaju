"use client";

/**
 * Shared shell for the three legal pages (ISSUE-074, FR-036).
 *
 * The /legal/terms, /legal/privacy, /legal/refund routes all share the
 * same chrome (TopAppBar + scrolling article + back-to-home link). The
 * only thing that varies between them is the title and the article body.
 *
 * We keep the article body as `children` rather than passing rendered
 * Markdown so each page module remains the single source of truth for
 * its own copy — the copy review pass (NFR-005) only ever needs to look
 * at the three page.tsx files, not at a shared content module.
 *
 * Layout (top → bottom):
 *   1. TopAppBar with back affordance and centered title.
 *   2. `<main>` wrapping a constrained-width `<article>` that contains
 *      the legal text. The article uses semantic headings (h2/h3) so
 *      assistive tech can navigate by section.
 *   3. Footer link back to "/".
 *
 * Accessibility:
 *   - `<main>` carries an `aria-labelledby` pointing at the article's
 *     visible h1-equivalent title (rendered via TopAppBar).
 *   - All section headings are real `<h2>` so axe's landmark + heading
 *     order rules stay green.
 */

import Link from "next/link";

import { TopAppBar } from "@/components/nav/TopAppBar";

interface LegalShellProps {
  title: string;
  /** Stable id for the visible heading — used for aria-labelledby. */
  headingId: string;
  /** Last-updated date string, displayed under the title. */
  updatedAt: string;
  /** Article body. */
  children: React.ReactNode;
}

export function LegalShell({
  title,
  headingId,
  updatedAt,
  children,
}: LegalShellProps) {
  return (
    <div className="min-h-screen bg-ink-900 text-cream-50">
      <TopAppBar
        back={
          <Link
            href="/"
            aria-label="홈으로 돌아가기 (상단)"
            className="inline-flex h-[44px] min-w-[44px] items-center justify-start px-s2 text-sm text-cream-50"
          >
            ← 홈
          </Link>
        }
        title={
          <h1
            id={headingId}
            className="truncate font-display text-base text-cream-50"
          >
            {title}
          </h1>
        }
      />
      <main aria-labelledby={headingId} className="px-s4 pb-s8 pt-s4">
        <article className="mx-auto max-w-prose space-y-s4 text-sm leading-7 text-cream-50/90">
          <p
            className="text-xs text-cream-50/60"
            data-testid="legal-updated-at"
          >
            마지막 업데이트: {updatedAt}
          </p>
          {children}
        </article>
        <div className="mx-auto mt-s8 max-w-prose">
          <Link
            href="/"
            className="inline-flex h-[44px] items-center text-sm underline underline-offset-4"
          >
            홈으로 돌아가기
          </Link>
        </div>
      </main>
    </div>
  );
}
