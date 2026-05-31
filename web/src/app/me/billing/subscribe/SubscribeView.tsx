'use client';

/**
 * `/me/billing/subscribe` — Subscription checkout flow (ISSUE-069, Screen 20 → checkout).
 *
 * Phase-1 strategy: the real Toss Payments JS SDK is a manual DEP-XX
 * setup (merchant credentials + production domain allowlisting), so the
 * UI feature-detects `window.TossPayments` and falls back gracefully:
 *
 *   - If `window.TossPayments` exists → call it (test stubs inject it).
 *   - If it does NOT exist → directly call `POST /api/v1/subscriptions`
 *     via the existing API client (the backend mock provider in
 *     PAYMENT_PROVIDER=mock will treat this as success), then route to
 *     `/me/billing`. This keeps the user-facing flow demonstrable
 *     end-to-end before the merchant credentials land.
 *
 * Same Next 15 Page-export split as the rest of the /me/* tree: this
 * file is the named-export view, `./page.tsx` is the thin default-
 * export wrapper.
 *
 * AC mapping (issues.md §ISSUE-069):
 *   AC1: tap "구독 시작하기" → routed here → Toss SDK modal opens
 *        within 1s (or mock equivalent).
 *   AC2: payment succeeds → routed back to `/me/billing` (the billing
 *        page itself renders "구독 중" via ISSUE-067).
 *   AC3: payment fails → "결제가 실패했어요" banner + "다시 결제하기"
 *        retry button.
 *
 * References:
 *   - docs/ux_spec.md Flow D / Flow E.
 *   - docs/copy_guide.md §3 "Payment failed" + §13 plan rows.
 *   - api/voicesaju/payment/subscription_routes.py — backend contract.
 */

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useCallback, useEffect, useRef, useState } from 'react';

import { TopAppBar } from '@/components/nav/TopAppBar';
import { BillingFetchError, createSubscription, type SubscriptionRow } from '@/lib/api/billing';

/**
 * Minimal shape of the optional global Toss SDK object.
 *
 * We only call `requestBillingAuth` (recurring billing) here. Real Toss
 * exposes a richer surface that's documented in the manual DEP-XX
 * setup; for Phase-1 testing we accept any shape with this single
 * method, so tests can inject a tiny stub.
 *
 * The callback contract mirrors the Toss Payments JS SDK promise
 * resolution: on success we receive the billing handle params
 * (currently unused — they round-trip through the backend POST), on
 * failure we get an Error-like with a message.
 */
interface TossPaymentsRecurring {
  requestBillingAuth: (options: {
    customerKey: string;
    successUrl: string;
    failUrl: string;
  }) => Promise<void>;
}

type TossPaymentsFactory = (clientKey: string) => TossPaymentsRecurring;

declare global {
  interface Window {
    TossPayments?: TossPaymentsFactory;
  }
}

type CheckoutState =
  | { kind: 'idle' }
  | { kind: 'submitting' }
  | { kind: 'success' }
  | { kind: 'failed'; message: string };

export interface SubscribeViewProps {
  /** Test hook — injected fake fetch. Production uses global `fetch`. */
  fetchImpl?: typeof fetch;
  /**
   * Test hook — injected window-like host so the test can stub
   * `TossPayments` without touching jsdom's real `window`. Falls back
   * to the real `window` when unset.
   */
  windowImpl?: Window;
}

const FAILURE_COPY = '결제가 실패했어요';
const RETRY_COPY = '다시 결제하기';

export function SubscribeView({ fetchImpl, windowImpl }: SubscribeViewProps) {
  const router = useRouter();
  const [state, setState] = useState<CheckoutState>({ kind: 'idle' });

  // routerRef so the start() callback doesn't re-create on every
  // render (matches the /me/billing pattern).
  const routerRef = useRef(router);
  routerRef.current = router;

  const fetchRef = useRef(fetchImpl);
  fetchRef.current = fetchImpl;

  const windowRef = useRef<Window | undefined>(windowImpl);
  windowRef.current = windowImpl;

  const start = useCallback(async () => {
    setState({ kind: 'submitting' });
    const f = fetchRef.current ?? fetch;
    const w = windowRef.current ?? (typeof window !== 'undefined' ? window : undefined);

    try {
      // ── 1. Open the backend billing handle ──────────────────────
      //    This is the same call the real Toss success callback would
      //    make under DEP-XX, so we can run it eagerly in Phase-1 and
      //    let the backend mock provider settle the success path.
      const sub: SubscriptionRow = await createSubscription(f);

      // ── 2. Try the real SDK if present ──────────────────────────
      //    A test (or a future DEP-XX manual config) can attach
      //    `window.TossPayments`. We call it but treat its failure as
      //    the checkout-fail path; its success drops back through to
      //    the redirect below.
      if (w !== undefined && typeof w.TossPayments === 'function') {
        try {
          const toss = w.TossPayments('test_ck_placeholder');
          await toss.requestBillingAuth({
            customerKey: sub.id,
            successUrl: '/me/billing',
            failUrl: '/me/billing/subscribe',
          });
        } catch (err) {
          setState({
            kind: 'failed',
            message: err instanceof Error ? err.message : 'unknown',
          });
          return;
        }
      }

      // ── 3. Success → route to /me/billing ───────────────────────
      //    The billing page (ISSUE-067) re-fetches the subscription
      //    and renders "구독 중" automatically because the backend
      //    row is now status='active'.
      setState({ kind: 'success' });
      routerRef.current.replace('/me/billing');
    } catch (err) {
      // The fetcher distinguishes 401 (auth) from generic failures so
      // we bounce to login when the session is gone — otherwise show
      // the AC3 failure banner.
      if (err instanceof BillingFetchError && err.status === 401) {
        routerRef.current.replace('/auth/login');
        return;
      }
      setState({
        kind: 'failed',
        message: err instanceof Error ? err.message : 'unknown',
      });
    }
  }, []);

  // AC1: auto-kick the flow on mount so the SDK modal (or mock
  // equivalent) opens within 1s of arrival. Users who land here via
  // the "구독 시작하기" CTA shouldn't have to tap a second time.
  useEffect(() => {
    void start();
  }, [start]);

  return (
    <main className="me-billing-subscribe">
      <TopAppBar
        title="구독 결제"
        back={
          <Link href="/me/billing" aria-label="이전 페이지로">
            ←
          </Link>
        }
      />

      {state.kind === 'submitting' && (
        <section aria-busy="true" aria-live="polite" className="me-billing-subscribe__pending">
          <p>결제 창을 여는 중…</p>
        </section>
      )}

      {state.kind === 'success' && (
        <section aria-live="polite" className="me-billing-subscribe__success">
          <p>구독 결제를 처리했어. 잠시만 기다려.</p>
        </section>
      )}

      {state.kind === 'failed' && (
        <section role="alert" aria-live="assertive" className="me-billing-subscribe__error">
          <p className="me-billing-subscribe__error-headline">{FAILURE_COPY}</p>
          <p className="me-billing-subscribe__error-help">카드 확인하고 다시 시도해줘.</p>
          <button
            type="button"
            onClick={() => {
              void start();
            }}
          >
            {RETRY_COPY}
          </button>
        </section>
      )}

      {state.kind === 'idle' && (
        <section className="me-billing-subscribe__idle">
          <p>결제 준비 중…</p>
        </section>
      )}
    </main>
  );
}
