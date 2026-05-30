/**
 * `/share/[slug]` 404 surface (ISSUE-061, ux_spec Screen 23 error state).
 *
 * Rendered when `SharePage` calls `notFound()` (slug missing or backend
 * 5xx). The copy is from copy_guide § Error Screens + ux_spec Screen 23:
 *
 *   "이 풀이의 명대사는 만료됐어요"
 *
 * CTA routes to the onboarding flow so a user who lands here from a
 * stale social share still has a one-tap path into the funnel.
 *
 * Architecture-Ref: §6.6 (share endpoints — error state).
 */

import Link from 'next/link';

const ERROR_HEADLINE = '이 풀이의 명대사는 만료됐어요';
const ERROR_BODY = '새로 풀이를 받아볼래?';
const CTA_PRIMARY = '내 풀이 받으러 가기';
const ONBOARDING_HREF = '/onboarding/birth-date';

export default function ShareNotFound() {
  return (
    <main
      className="flex min-h-screen flex-col items-center justify-center bg-ink-900 px-s4 py-s8 text-center text-cream-100"
      data-testid="share-not-found"
    >
      <div className="flex max-w-md flex-col items-center gap-s4">
        <h1 className="font-display text-2xl font-bold tracking-tight text-cream-50">
          {ERROR_HEADLINE}
        </h1>
        <p className="font-body text-base text-cream-200">{ERROR_BODY}</p>
        <Link
          href={ONBOARDING_HREF}
          className="mt-s2 inline-flex items-center justify-center gap-s2 rounded-md bg-amber-400 px-s5 py-s3 font-body text-base font-medium text-ink-900 transition-colors hover:bg-amber-300 active:bg-amber-500 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-amber-300"
          data-testid="share-not-found-cta"
        >
          {CTA_PRIMARY}
        </Link>
      </div>
    </main>
  );
}
