"use client";

/**
 * `/me/billing` — Screen 20 (ISSUE-067): subscription + payment history.
 *
 * Sits behind a Page-module wrapper at `./page.tsx` for the Next 15
 * named-export rule (see /me/history + /me/edit-saju for the pattern).
 *
 * Layout (top → bottom):
 *   1. TopAppBar with "결제 / 구독" title (copy_guide §13).
 *   2. Current plan card:
 *      - Subscriber (status='active')         → 월 구독 · 9,900원 / 다음 결제 [date] / "구독 해지" button
 *      - Cancel-at-period-end                 → "해지 예정 — [date]까지 이용 가능" pill (AC4)
 *      - Non-subscriber                        → 무료 회원 + "구독 시작하기" CTA → /me/billing/subscribe
 *   3. Payment history section:
 *      - Empty (no rows AND no subscription)   → "결제 내역이 없어요" + start-CTA (AC2)
 *      - Non-empty                              → list of `<PaymentReceiptRow>` items.
 *
 * Side effects:
 *   - Fetches `GET /api/v1/subscriptions/me` + `GET /api/v1/payments/history`
 *     in parallel on mount. Both must resolve before we show content;
 *     either failing flips the page into the error shell with a retry.
 *   - "구독 해지" tap → `ConfirmModal` with the next-billing date in the
 *     description (AC3). Confirm → POST `/subscriptions/cancel`. Success
 *     → flip the in-memory subscription state to
 *     status='cancel_at_period_end' (AC4) without re-fetching.
 *
 * Why not refetch after cancel?
 *   - The cancel endpoint returns the canonical updated row, so we
 *     have the same shape we'd get from another GET. Avoiding the
 *     extra round-trip keeps the post-confirm UI snappy.
 *
 * AC mapping (ISSUE-067):
 *   AC1 → subscriber → tier + next billing + amount + 구독 해지 button.
 *   AC2 → non-subscriber + no purchases → empty + 구독 시작하기 CTA.
 *   AC3 → tap 구독 해지 → ConfirmModal carries next-billing date.
 *   AC4 → confirm → API success → "해지 예정 — [date]까지 이용 가능" pill.
 */

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

import { TopAppBar } from "@/components/nav/TopAppBar";
import { ConfirmModal } from "@/components/ui/ConfirmModal";
import {
  BillingFetchError,
  cancelMySubscription,
  fetchMySubscription,
  fetchPaymentHistory,
  type PaymentHistoryRow,
  type SubscriptionRow,
} from "@/lib/api/billing";

type LoadState =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | {
      kind: "loaded";
      subscription: SubscriptionRow | null;
      payments: PaymentHistoryRow[];
    };

export interface BillingViewProps {
  /** Test hook — injected fake fetch. Production uses global `fetch`. */
  fetchImpl?: typeof fetch;
}

// Monthly subscription price per copy_guide §13 "Plan: subscriber".
// Hard-coded because the backend doesn't yet expose a /pricing endpoint
// (lands with ISSUE-043). The amount also appears in the cancel modal
// body for transparency.
const MONTHLY_PRICE_KRW = 9900;

/**
 * Format an ISO timestamp as `YYYY-MM-DD` for display in the pill
 * copy. We crop the prefix rather than parsing through `Date` so the
 * rendered day doesn't shift across timezones.
 */
function formatYmd(iso: string | null): string {
  if (iso === null) return "";
  const m = /^(\d{4}-\d{2}-\d{2})/.exec(iso);
  return m?.[1] ?? "";
}

function formatKrw(amount: number): string {
  return `${amount.toLocaleString("ko-KR")}원`;
}

export function BillingView({ fetchImpl }: BillingViewProps) {
  const router = useRouter();
  const [state, setState] = useState<LoadState>({ kind: "loading" });
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [cancelError, setCancelError] = useState<string | null>(null);
  const [cancelBusy, setCancelBusy] = useState(false);

  // Same routerRef + fetchRef pattern as /me/saju + /me/history:
  // vitest mocks useRouter() per render, so referencing `router`
  // directly from a callback forces unnecessary effect re-runs.
  const routerRef = useRef(router);
  routerRef.current = router;

  const fetchRef = useRef(fetchImpl);
  fetchRef.current = fetchImpl;

  const load = useCallback(async () => {
    setState({ kind: "loading" });
    setCancelError(null);
    const f = fetchRef.current ?? fetch;
    try {
      // Parallel fetch — both endpoints are independent.
      const [subResult, paymentsResult] = await Promise.allSettled([
        fetchMySubscription(f),
        fetchPaymentHistory(1, f),
      ]);

      // Auth failure on either side → bounce to login.
      const sub401 =
        subResult.status === "rejected" &&
        subResult.reason instanceof BillingFetchError &&
        subResult.reason.status === 401;
      const pmt401 =
        paymentsResult.status === "rejected" &&
        paymentsResult.reason instanceof BillingFetchError &&
        paymentsResult.reason.status === 401;
      if (sub401 || pmt401) {
        routerRef.current.replace("/auth/login");
        return;
      }

      if (
        subResult.status !== "fulfilled" ||
        paymentsResult.status !== "fulfilled"
      ) {
        setState({ kind: "error", message: "잠시 후 다시 시도해주세요" });
        return;
      }

      setState({
        kind: "loaded",
        subscription: subResult.value.subscription,
        payments: paymentsResult.value,
      });
    } catch {
      setState({ kind: "error", message: "잠시 후 다시 시도해주세요" });
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const handleCancelConfirm = useCallback(async () => {
    setCancelBusy(true);
    setCancelError(null);
    try {
      const updated = await cancelMySubscription(fetchRef.current ?? fetch);
      // Mutate the loaded state in place so the page reflects the
      // new pill copy immediately (AC4) without a refetch.
      setState((prev) =>
        prev.kind === "loaded" ? { ...prev, subscription: updated } : prev,
      );
    } catch (err) {
      const msg =
        err instanceof BillingFetchError && err.status === 401
          ? "로그인이 필요해요"
          : "해지에 실패했어요. 잠시 후 다시 시도해주세요";
      setCancelError(msg);
    } finally {
      setCancelBusy(false);
      setConfirmOpen(false);
    }
  }, []);

  if (state.kind === "loading") {
    return (
      <div className="flex min-h-screen flex-col bg-ink-900 text-cream-100">
        <TopAppBar title="결제 / 구독" />
        <main
          className="mx-auto flex w-full max-w-md flex-1 flex-col items-center justify-center px-s4 py-s8"
          aria-busy
          data-testid="me-billing-loading"
        >
          <span className="sr-only">로딩 중</span>
        </main>
      </div>
    );
  }

  if (state.kind === "error") {
    return (
      <div className="flex min-h-screen flex-col bg-ink-900 text-cream-100">
        <TopAppBar title="결제 / 구독" />
        <main
          className="mx-auto flex w-full max-w-md flex-1 flex-col items-center justify-center gap-s4 px-s4 py-s8"
          data-testid="me-billing-error"
        >
          <p className="font-body text-sm text-cream-300">{state.message}</p>
          <button
            type="button"
            onClick={() => {
              void load();
            }}
            className="rounded-md border border-ink-700 px-s4 py-s2 font-body text-sm text-cream-50 hover:bg-ink-800"
            data-testid="me-billing-retry"
          >
            다시 시도
          </button>
        </main>
      </div>
    );
  }

  const { subscription, payments } = state;
  const isSubscriber = subscription !== null;
  const isCancelPending =
    subscription !== null && subscription.status === "cancel_at_period_end";
  const nextBillingYmd = subscription
    ? formatYmd(subscription.current_period_end)
    : "";
  const isEmpty = !isSubscriber && payments.length === 0;

  return (
    <div className="flex min-h-screen flex-col bg-ink-900 text-cream-100">
      <TopAppBar title="결제 / 구독" />
      <main
        className="mx-auto flex w-full max-w-md flex-1 flex-col gap-s6 px-s4 py-s6"
        data-testid="me-billing-loaded"
      >
        {/* Current plan card */}
        <section
          aria-label="현재 플랜"
          className="flex flex-col gap-s2 rounded-md border border-ink-700 bg-ink-800 px-s4 py-s4"
          data-testid="me-billing-plan-card"
        >
          <span className="font-body text-xs text-cream-300">현재 플랜</span>
          {isSubscriber ? (
            <>
              <h2
                className="font-display-han text-xl text-cream-50"
                data-testid="me-billing-plan-tier"
              >
                월 구독 · {formatKrw(MONTHLY_PRICE_KRW)}
              </h2>
              {isCancelPending ? (
                <div
                  role="status"
                  className="rounded-full border border-amber-700 bg-amber-900/30 px-s4 py-s1 text-center font-body text-xs text-amber-200"
                  data-testid="me-billing-cancel-pending-pill"
                >
                  해지 예정 — {nextBillingYmd}까지 이용 가능
                </div>
              ) : (
                <p
                  className="font-body text-sm text-cream-200"
                  data-testid="me-billing-next-billing"
                >
                  다음 결제: {nextBillingYmd}
                </p>
              )}
              {!isCancelPending && (
                <button
                  type="button"
                  onClick={() => {
                    setConfirmOpen(true);
                  }}
                  className="self-start rounded-md border border-rose-400 px-s4 py-s2 font-body text-sm text-rose-300 hover:bg-rose-950"
                  data-testid="me-billing-cancel-button"
                >
                  구독 해지
                </button>
              )}
              {cancelError && (
                <p
                  role="alert"
                  className="font-body text-xs text-rose-400"
                  data-testid="me-billing-cancel-error"
                >
                  {cancelError}
                </p>
              )}
            </>
          ) : (
            <>
              <h2
                className="font-display-han text-xl text-cream-50"
                data-testid="me-billing-plan-tier"
              >
                무료
              </h2>
              <Link
                href="/me/billing/subscribe"
                className="self-start rounded-md bg-amber-400 px-s4 py-s2 font-body text-sm font-medium text-ink-900 hover:bg-amber-300"
                data-testid="me-billing-start-cta"
              >
                구독 시작하기
              </Link>
            </>
          )}
        </section>

        {/* Payment history section */}
        <section
          aria-label="결제 내역"
          className="flex flex-col gap-s2"
          data-testid="me-billing-history-section"
        >
          <h3 className="font-display text-sm text-cream-300">결제 내역</h3>
          {isEmpty ? (
            <div
              className="rounded-md border border-ink-700 bg-ink-800 px-s4 py-s6 text-center font-body text-sm text-cream-300"
              data-testid="me-billing-history-empty"
            >
              결제 내역이 없어요
            </div>
          ) : payments.length === 0 ? (
            // Subscriber whose ledger hasn't refreshed (sub was just
            // created, no payment row yet). Show a friendly note rather
            // than the empty-state CTA so we don't suggest they restart.
            <div
              className="rounded-md border border-ink-700 bg-ink-800 px-s4 py-s4 text-center font-body text-xs text-cream-400"
              data-testid="me-billing-history-pending"
            >
              결제 내역이 곧 표시돼요.
            </div>
          ) : (
            <ul
              className="flex flex-col divide-y divide-ink-700 rounded-md border border-ink-700 bg-ink-800"
              aria-label="결제 내역 목록"
              data-testid="me-billing-history-list"
            >
              {payments.map((p) => (
                <li key={p.id}>
                  <PaymentReceiptRow row={p} />
                </li>
              ))}
            </ul>
          )}
        </section>
      </main>

      {subscription && (
        <ConfirmModal
          open={confirmOpen}
          onClose={() => setConfirmOpen(false)}
          onConfirm={() => {
            void handleCancelConfirm();
          }}
          title="정말 해지할 거야?"
          description={`해지하면 ${nextBillingYmd}까지는 그대로 쓸 수 있어. 다음 달부터 안 돼.`}
          confirmLabel={cancelBusy ? "처리 중..." : "그래도 해지"}
          cancelLabel="유지할게"
        />
      )}
    </div>
  );
}

interface PaymentReceiptRowProps {
  row: PaymentHistoryRow;
}

/** One row in the payment history list. */
function PaymentReceiptRow({ row }: PaymentReceiptRowProps) {
  const dateStr = formatYmd(row.paid_at);
  // Refunds get a slightly different label so the user knows the
  // amount didn't actually leave their account.
  const isRefunded =
    row.refunded_amount_krw > 0 && row.refunded_amount_krw >= row.amount_krw;
  const statusLabel = isRefunded
    ? "환불됨"
    : row.status === "paid"
      ? "결제 완료"
      : row.status;

  return (
    <div
      className="flex items-center justify-between gap-s2 px-s4 py-s3 font-body text-sm text-cream-50"
      data-testid={`me-billing-history-row-${row.id}`}
    >
      <div className="flex min-w-0 flex-1 flex-col gap-s1">
        <span
          className="font-display text-xs text-cream-300"
          data-testid={`me-billing-history-row-date-${row.id}`}
        >
          {dateStr || "날짜 미상"}
        </span>
        <span data-testid={`me-billing-history-row-amount-${row.id}`}>
          {formatKrw(row.amount_krw)}
        </span>
      </div>
      <span
        className="rounded-full border border-ink-600 bg-ink-700 px-s2 py-px font-display text-xs text-cream-200"
        data-testid={`me-billing-history-row-status-${row.id}`}
      >
        {statusLabel}
      </span>
    </div>
  );
}
