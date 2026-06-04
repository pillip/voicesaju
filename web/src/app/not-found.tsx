/**
 * Global 404 — Next.js App Router `not-found.tsx` (ISSUE-075, FR-035).
 *
 * Rendered by Next.js whenever a route segment calls `notFound()` or no
 * route matches at all. The page is intentionally minimal: copy-light,
 * single CTA back to `/`. The copy follows copy_guide §35 (404 H1 =
 * "별기운이 잠시 약하네." per the error catalogue).
 *
 * Server Component (no `'use client'`) so the not-found HTML ships
 * pre-rendered for fastest paint.
 *
 * ISSUE-104: sr-only announcement migrated from the system-tone
 * "페이지를 찾을 수 없습니다." (ISSUE-075 baseline) to "길을 잘못 들었어." —
 * same informational payload as the visible h1, in 누님 voice. The
 * ISSUE-097 file-level bypass marker was removed; the file now passes
 * `pnpm copy:lint` cleanly without an exemption.
 */

import Link from 'next/link';

import { CharacterIllustration } from '@/components/ui';

export const metadata = {
  title: '페이지를 찾을 수 없어요 | 보이스사주',
};

export default function NotFound() {
  return (
    <main
      className="flex min-h-screen flex-col items-center justify-center gap-s4 bg-ink-900 px-s4 py-s8 text-cream-50"
      data-testid="not-found"
    >
      <div role="status" aria-live="polite" className="sr-only">
        길을 잘못 들었어.
      </div>
      <CharacterIllustration character="nuna" data-testid="not-found-persona" />
      <h1 className="font-display text-2xl">길을 잘못 들었네…</h1>
      <p className="max-w-sm text-center font-body text-sm text-cream-50/80">
        찾는 페이지가 없어. 홈으로 돌아가서 다시 시작해볼까?
      </p>
      <Link
        href="/"
        className="inline-flex h-[48px] min-w-[140px] items-center justify-center rounded-full bg-amber-500 px-s4 text-sm font-medium text-ink-900"
        data-testid="not-found-home"
      >
        홈으로 돌아가기
      </Link>
    </main>
  );
}
