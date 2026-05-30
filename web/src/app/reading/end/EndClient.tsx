'use client';

/**
 * `<EndClient>` — `/reading/end` (Screen 11, ISSUE-059).
 *
 * The page sits at the end of the saju reading flow. The user lands
 * here via `/reading/play` once the audio finishes; the play screen
 * passes `?slug=<share_slug>` so this surface can fetch the matching
 * quote-card payload.
 *
 * Behaviour:
 *   1. Pull `?slug` from the URL → call `/api/v1/quote-cards/by-slug/{slug}`.
 *      The endpoint is the same one the SSR share landing uses (ISSUE-060
 *      / ISSUE-061), so the wire shape is shared.
 *   2. Render `<QuoteCardPreview>` (skeleton → image → fallback) +
 *      `<ShareButtonRow>` (channel-aware share buttons).
 *   3. Render secondary CTAs (`또 풀이 받기` → `/reading/category`,
 *      `마이페이지로` → `/me`).
 *   4. Non-member load: open the signup modal after exactly 1 second
 *      (FR-003 1-second conversion + ux_spec Flow F).
 *
 * `?member=true` query suppresses the modal — temporary affordance
 * until the real auth-state hook lands (see ISSUE-040). Production
 * default is non-member.
 *
 * Architecture-Ref: docs/ux_spec.md Screen 11, docs/copy_guide.md §9.
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import { useSearchParams } from 'next/navigation';

import { QuoteCardPreview } from '@/components/share/QuoteCardPreview';
import { ShareButtonRow } from '@/components/share/ShareButtonRow';
import { SignupPromptModal } from '@/components/auth/SignupPromptModal';
import type { QuoteCardBySlugResponse } from '@/app/api/og/[slug]/og-helpers';

/** copy_guide §9 + supporting strings. */
const ERROR_COPY = '명대사 카드를 찾을 수 없어. 새로 풀이를 받아볼래?';
const CTA_RETRY = '또 풀이 받기';
const CTA_MY = '마이페이지로';

const HREF_CATEGORY = '/reading/category';
const HREF_ME = '/me';

const SIGNUP_DELAY_MS = 1000;

type FetchState =
  | { kind: 'idle' }
  | { kind: 'loading' }
  | { kind: 'ok'; card: QuoteCardBySlugResponse }
  | { kind: 'missing' }
  | { kind: 'error'; status: number };

export default function EndClient() {
  const searchParams = useSearchParams();
  const slug = searchParams?.get('slug') ?? null;
  const memberParam = searchParams?.get('member');
  const isMember = memberParam === 'true' || memberParam === '1';

  const [fetchState, setFetchState] = useState<FetchState>(
    slug ? { kind: 'loading' } : { kind: 'missing' },
  );
  const [signupOpen, setSignupOpen] = useState(false);
  const signupTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // -----------------------------------------------------------------
  // Fetch the quote-card payload by slug.
  // -----------------------------------------------------------------
  useEffect(() => {
    if (!slug) {
      return;
    }
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch(`/api/v1/quote-cards/by-slug/${encodeURIComponent(slug)}`, {
          method: 'GET',
          headers: { Accept: 'application/json' },
        });
        if (cancelled) return;
        if (res.status === 404) {
          setFetchState({ kind: 'missing' });
          return;
        }
        if (!res.ok) {
          setFetchState({ kind: 'error', status: res.status });
          return;
        }
        const card = (await res.json()) as QuoteCardBySlugResponse;
        if (cancelled) return;
        setFetchState({ kind: 'ok', card });
      } catch {
        if (cancelled) return;
        setFetchState({ kind: 'error', status: 0 });
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [slug]);

  // -----------------------------------------------------------------
  // Non-member signup modal — opens after 1s. Members are silent.
  // -----------------------------------------------------------------
  useEffect(() => {
    if (isMember) return;
    signupTimerRef.current = setTimeout(() => {
      setSignupOpen(true);
    }, SIGNUP_DELAY_MS);
    return () => {
      if (signupTimerRef.current) {
        clearTimeout(signupTimerRef.current);
        signupTimerRef.current = null;
      }
    };
  }, [isMember]);

  const handleCloseSignup = useCallback(() => setSignupOpen(false), []);

  // -----------------------------------------------------------------
  // Derived props for children.
  // -----------------------------------------------------------------
  const cardForPreview = fetchState.kind === 'ok' ? fetchState.card : undefined;
  // The slug is generated server-side as base62 (data_model §4.16, ≤12
  // chars), so it's URL-safe by construction. We still encode here as
  // defense-in-depth in case a future migration ever widens the alphabet.
  const encodedSlug = slug ? encodeURIComponent(slug) : '';
  const shareUrl = slug ? `/share/${encodedSlug}` : '/';
  const ogImageUrl = slug ? `/api/og/${encodedSlug}` : '';
  const quoteText = fetchState.kind === 'ok' ? fetchState.card.quote_text : '';

  const showError = fetchState.kind === 'missing' || fetchState.kind === 'error';
  const showShareRow = !showError && slug !== null;

  return (
    <main
      className="flex min-h-screen flex-col items-center justify-between bg-ink-900 px-s4 py-s8 text-cream-100"
      data-testid="reading-end-root"
    >
      {/* Hero — quote card */}
      <section
        className="flex w-full max-w-md flex-col items-center gap-s4"
        aria-label="명대사 카드"
      >
        {showError ? (
          <div
            data-testid="reading-end-error"
            role="alert"
            aria-live="polite"
            className="flex aspect-[9/16] w-full max-w-sm flex-col items-center justify-center rounded-lg bg-ink-700/40 px-s4 text-center"
          >
            <p className="font-display text-lg text-cream-100">{ERROR_COPY}</p>
          </div>
        ) : (
          <QuoteCardPreview slug={slug as string} card={cardForPreview} />
        )}
      </section>

      {/* Share row */}
      {showShareRow && (
        <section className="mt-s6 w-full" aria-label="공유">
          <ShareButtonRow
            slug={slug as string}
            shareUrl={shareUrl}
            ogImageUrl={ogImageUrl}
            quoteText={quoteText}
          />
        </section>
      )}

      {/* Secondary CTAs */}
      <section className="mt-s8 flex w-full max-w-md flex-col items-center gap-s3">
        <Link
          href={HREF_CATEGORY}
          className="inline-flex w-full max-w-xs items-center justify-center gap-s2 rounded-md border border-cream-300 bg-transparent px-s4 py-s2 font-body text-base font-medium text-cream-100 transition-colors hover:bg-ink-700 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-amber-300 active:bg-ink-600"
          data-testid="cta-retry"
        >
          {CTA_RETRY}
        </Link>
        <Link
          href={HREF_ME}
          className="inline-flex w-full max-w-xs items-center justify-center gap-s2 rounded-md bg-amber-400 px-s4 py-s2 font-body text-base font-medium text-ink-900 transition-colors hover:bg-amber-300 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-amber-300 active:bg-amber-500"
          data-testid="cta-my"
        >
          {CTA_MY}
        </Link>
      </section>

      {/* Signup modal (non-members only, 1s after load) */}
      <SignupPromptModal open={signupOpen} onClose={handleCloseSignup} />
    </main>
  );
}
