'use client';

/**
 * `/auth/login` — Screen 15 of `docs/ux_spec.md`.
 *
 * AC (ISSUE-027):
 * 1. Web visitor sees "카카오로 시작하기" + "Apple로 시작하기" buttons.
 * 2. Toss WebView visitor sees only "토스로 계속하기" button.
 * 3. Tap → browser navigates to the provider start URL.
 * 4. OAuth-cancelled return (`?error=cancelled`) → banner
 *    "로그인이 취소됐어요" + buttons remain enabled so the user can retry.
 *
 * Architecture-Ref: §11.1 (`vs_sess` cookie + Redis session, post-callback).
 * PRD-Ref: FR-016 (auth), US-13 (web auth), US-02 (non-member trial).
 * Depends on: ISSUE-022 (TopAppBar — not used here, page has no chrome by
 * design), ISSUE-023 (`useRuntimeContext`), ISSUE-026 (start routes).
 *
 * Why a client component:
 * - We branch on the runtime channel from `useRuntimeContext`, which itself
 *   depends on `navigator.userAgent` and therefore requires the client
 *   tree. The SSR snapshot uses the web defaults; the channel flips on
 *   hydration if the UA matches the Toss WebView pattern.
 * - `useSearchParams` is read on the client so we can branch on
 *   `?error=cancelled` (the cancellation flow set by ISSUE-026's callback
 *   when a user backs out of the OAuth provider's consent screen).
 *
 * Why anchors (not buttons + `window.location.assign`):
 * - Real `<a href>` is the most accessible affordance: screen readers
 *   announce it as a link, middle-click opens it in a new tab, and the
 *   navigation works even if JS is broken. The ISSUE-026 backend routes
 *   currently return JSON under `AUTH_PROVIDER=mock` and will return 302
 *   under real providers (ISSUE-025) — either way, an anchor with `href`
 *   gives the right behaviour.
 */

import { Banner } from '@/components/ui/Banner';
import { useRuntimeContext } from '@/lib/context/runtime-context';
import { cn } from '@/lib/utils';
import { useSearchParams } from 'next/navigation';

export default function LoginPage() {
  const { channel } = useRuntimeContext();
  const searchParams = useSearchParams();
  const cancelled = searchParams?.get('error') === 'cancelled';
  const isToss = channel === 'toss_webview';

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-md flex-col items-center justify-center gap-s6 px-s4 py-s8 text-cream-100">
      <div className="flex w-full flex-col items-center gap-s4 text-center">
        {/*
         * Heading. The 48px display-han spec from `docs/copy_guide.md` §12
         * is not feasible here without a custom display font load — we use
         * the existing font-display token so the page reads as part of the
         * existing design system (ISSUE-021 primitives).
         */}
        <h1 className="font-display text-2xl tracking-tight text-cream-50">
          VoiceSaju에 오신 걸 환영해요
        </h1>
      </div>

      {cancelled && (
        <div className="w-full" data-testid="login-cancelled-banner">
          <Banner tone="error">로그인이 취소됐어요</Banner>
        </div>
      )}

      <section aria-label="로그인 방법" className="flex w-full flex-col gap-s3">
        {isToss ? (
          <ProviderAnchor href="/api/v1/auth/toss/start" label="토스로 계속하기" tone="primary" />
        ) : (
          <>
            <ProviderAnchor
              href="/api/v1/auth/kakao/start"
              label="카카오로 시작하기"
              tone="primary"
            />
            <ProviderAnchor
              href="/api/v1/auth/apple/start"
              label="Apple로 시작하기"
              tone="secondary"
            />
          </>
        )}
      </section>

      <p className="text-center font-body text-xs text-cream-300">
        로그인 시 이용약관 및 개인정보 처리방침에 동의합니다.
      </p>
    </main>
  );
}

interface ProviderAnchorProps {
  href: string;
  label: string;
  tone: 'primary' | 'secondary';
}

/**
 * Visual styling parallel to {@link PrimaryButton} / {@link SecondaryButton}
 * but rendered as a real `<a>` so the OAuth redirect works as a regular
 * navigation. See the module-level comment for the rationale.
 */
function ProviderAnchor({ href, label, tone }: ProviderAnchorProps) {
  const isPrimary = tone === 'primary';
  return (
    <a
      href={href}
      className={cn(
        'inline-flex w-full items-center justify-center rounded-md px-s4 py-s3 font-body text-base font-medium',
        'transition-colors',
        'focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-amber-300',
        isPrimary
          ? 'bg-amber-400 text-ink-900 hover:bg-amber-300 active:bg-amber-500'
          : 'border border-cream-300 bg-transparent text-cream-100 hover:bg-ink-700 active:bg-ink-600',
      )}
    >
      {label}
    </a>
  );
}
