'use client';

/**
 * `/upsell/subscription` — Screen 22 (ISSUE-070):
 * one-time upsell after a user's 2nd lifetime single purchase.
 *
 * Phase-1 trigger contract (from issues.md §ISSUE-070):
 *   - The caller (payment-confirm flow, ISSUE-044/045) decides when to
 *     navigate here. This page is just the renderer + dismiss flag.
 *   - We persist a once-shown flag in `localStorage["vs_upsell_shown"]`.
 *     When set, AC2/AC3 require the screen to NOT re-appear; we
 *     `router.replace('/me')` immediately on mount.
 *   - First visit → render the comparison strip + two CTAs.
 *
 * Why localStorage and not a backend flag?
 *   - For Phase-1 the upsell is purely a client concern (the trigger is
 *     a client-side router push from the payment confirm screen, not a
 *     server-rendered redirect). A backend `upsell_shown_at` column
 *     would couple this to a migration + GET endpoint, which the
 *     issue's "Phase-1: localStorage is fine for v1" note rules out.
 *   - When ISSUE-044/045 land their backend trigger, they can mirror
 *     the flag server-side; the localStorage check below is forward-
 *     compatible because it only short-circuits, never sets, on the
 *     server-driven path.
 *
 * Same Next 15 Page-export split as the rest of the /me/* tree.
 *
 * AC mapping (issues.md §ISSUE-070):
 *   AC1 → page renders the comparison strip + "구독 시작하기" CTA on
 *         first visit. Tap → /me/billing/subscribe.
 *   AC2 → "다음에 할게요" → set localStorage flag → /me.
 *   AC3 → mount + flag-already-set → immediate /me redirect.
 *
 * Pricing values are intentionally hard-coded to match the values in
 * `api/voicesaju/config.py` (`price_single_krw = 4_900`,
 * `price_subscription_krw = 9_900`) — they appear verbatim in the
 * copy_guide §3 `/upsell/subscription` block, so a `/pricing`
 * endpoint isn't needed for the v1 launch. Update both sources in
 * lockstep if pricing changes.
 *
 * References:
 *   - docs/ux_spec.md Screen 22 (683+).
 *   - docs/copy_guide.md §3 `/upsell/subscription`.
 */

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useEffect, useRef, useState } from 'react';

import { TopAppBar } from '@/components/nav/TopAppBar';

export const UPSELL_SHOWN_STORAGE_KEY = 'vs_upsell_shown';

// Pricing constants — must match api/voicesaju/config.py.
export const PRICE_SINGLE_KRW = 4_900;
export const PRICE_SUBSCRIPTION_KRW = 9_900;

const SINGLE_TWO_TIMES = PRICE_SINGLE_KRW * 2; // 9,800원

function formatKrw(amount: number): string {
  return `${amount.toLocaleString('ko-KR')}원`;
}

type Storage = Pick<globalThis.Storage, 'getItem' | 'setItem'>;

export interface UpsellSubscriptionViewProps {
  /**
   * Test hook — injected localStorage-like host so tests don't fight
   * jsdom's real `window.localStorage`. Falls back to the real
   * `window.localStorage` when unset.
   */
  storageImpl?: Storage;
}

export function UpsellSubscriptionView({ storageImpl }: UpsellSubscriptionViewProps) {
  const router = useRouter();

  // routerRef so dismiss() / mount-effect don't capture a stale router
  // (matches the routerRef pattern in /me, /me/billing, etc.).
  const routerRef = useRef(router);
  routerRef.current = router;

  const storageRef = useRef<Storage | undefined>(storageImpl);
  storageRef.current = storageImpl;

  // `dismissed` flips when the page mounts with the flag already set OR
  // when the user taps "다음에 할게요". In either case we render
  // nothing while the router.replace fires.
  const [dismissed, setDismissed] = useState(false);

  // AC3: on mount, short-circuit when the flag is already set. This
  // both blocks the screen from re-appearing and means the caller can
  // safely re-navigate here on every payment-confirm without
  // additional state-machine logic.
  useEffect(() => {
    const storage =
      storageRef.current ?? (typeof window !== 'undefined' ? window.localStorage : undefined);
    if (storage === undefined) return;
    try {
      if (storage.getItem(UPSELL_SHOWN_STORAGE_KEY) === 'true') {
        setDismissed(true);
        routerRef.current.replace('/me');
      }
    } catch {
      // localStorage can throw in private-browsing / SecurityError
      // modes. Treat as "first visit" and render the upsell — the
      // user can still dismiss it, the flag just won't persist.
    }
  }, []);

  const dismiss = () => {
    const storage =
      storageRef.current ?? (typeof window !== 'undefined' ? window.localStorage : undefined);
    try {
      storage?.setItem(UPSELL_SHOWN_STORAGE_KEY, 'true');
    } catch {
      // Same private-browsing caveat as above — the user still
      // navigates away; we just can't remember the dismissal.
    }
    setDismissed(true);
    routerRef.current.push('/me');
  };

  if (dismissed) {
    // Render nothing while the redirect fires so the user never sees
    // the upsell flash through.
    return null;
  }

  return (
    <main className="upsell-subscription">
      <TopAppBar
        title="구독 안내"
        back={
          <Link href="/me" aria-label="이전 페이지로">
            ←
          </Link>
        }
      />

      <section className="upsell-subscription__hero">
        <h1 className="upsell-subscription__headline">
          매번 결제할래,
          <br />
          <span className="upsell-subscription__headline-amber">매달 다 받을래?</span>
        </h1>
        <p className="upsell-subscription__body">
          단건 두 번 값에 매달 사주 1회 + 매일 타로가 다 돼.
        </p>
      </section>

      <section className="upsell-subscription__compare" aria-label="가격 비교">
        <div className="upsell-subscription__compare-row" data-testid="upsell-single-line">
          단건 {formatKrw(PRICE_SINGLE_KRW)} × 2 = {formatKrw(SINGLE_TWO_TIMES)}
        </div>
        <div
          className="upsell-subscription__compare-row upsell-subscription__compare-row--highlight"
          data-testid="upsell-subscription-line"
        >
          구독 {formatKrw(PRICE_SUBSCRIPTION_KRW)} / 월 — 매일 타로까지
        </div>
      </section>

      <section className="upsell-subscription__actions">
        <Link
          href="/me/billing/subscribe"
          className="upsell-subscription__cta upsell-subscription__cta--primary"
        >
          구독 시작 · ₩9,900/월
        </Link>
        <button
          type="button"
          onClick={dismiss}
          className="upsell-subscription__cta upsell-subscription__cta--ghost"
        >
          다음에
        </button>
      </section>

      <p className="upsell-subscription__footnote">언제든 해지할 수 있어.</p>
    </main>
  );
}
