/**
 * Typed fetchers for the billing surface (ISSUE-067).
 *
 *   GET  /api/v1/subscriptions/me   — caller's current subscription or null
 *   GET  /api/v1/payments/history   — paginated single-purchase history
 *   POST /api/v1/subscriptions/cancel — schedule cancel at period end
 *
 * Backend contracts (see api/voicesaju/payment/subscription_routes.py and
 * api/voicesaju/payment/history.py):
 *
 * ```
 * // GET /subscriptions/me
 * {
 *   subscription: null
 *   | {
 *       id: string,
 *       status: "active" | "cancel_at_period_end",
 *       monthly_saju_remaining: number,
 *       current_period_start: string, // ISO timestamp
 *       current_period_end: string,
 *       cancel_requested_at: string | null,
 *     }
 * }
 *
 * // GET /payments/history?page=N
 * [
 *   {
 *     id: string,
 *     type: "single" | "subscription",
 *     category: string | null,
 *     amount_krw: number,
 *     status: string,
 *     paid_at: string | null,
 *     refunded_amount_krw: number,
 *   },
 *   ...
 * ]
 *
 * // POST /subscriptions/cancel
 * { id, status: "cancel_at_period_end", current_period_end, ... }
 * ```
 *
 * Status mapping (consumed by /me/billing):
 *  - 200 → typed payload.
 *  - 401 → `BillingFetchError` (page → redirect /auth/login).
 *  - 404 (cancel) → `BillingFetchError` with `status=404` (caller had no
 *    active row — the FE shows a toast and refreshes the subscription
 *    state, no destructive action taken).
 *  - 5xx / network / parse → generic `BillingFetchError`.
 */

export interface SubscriptionRow {
  id: string;
  status: "active" | "cancel_at_period_end";
  monthly_saju_remaining: number;
  current_period_start: string;
  current_period_end: string;
  cancel_requested_at: string | null;
}

export interface MeSubscriptionResponse {
  subscription: SubscriptionRow | null;
}

export interface PaymentHistoryRow {
  id: string;
  type: "single" | "subscription";
  category: string | null;
  amount_krw: number;
  status: string;
  paid_at: string | null;
  refunded_amount_krw: number;
}

export class BillingFetchError extends Error {
  readonly status: number | null;
  constructor(message: string, status: number | null = null) {
    super(message);
    this.name = "BillingFetchError";
    this.status = status;
  }
}

async function _getJson<T>(
  url: string,
  fetchImpl: typeof fetch,
  validate: (value: unknown) => value is T,
  context: string,
): Promise<T> {
  let res: Response;
  try {
    res = await fetchImpl(url, {
      method: "GET",
      credentials: "include",
      headers: { Accept: "application/json" },
    });
  } catch (err) {
    throw new BillingFetchError(
      `network error fetching ${context}: ${err instanceof Error ? err.message : String(err)}`,
      null,
    );
  }
  if (!res.ok) {
    throw new BillingFetchError(
      `non-OK response from ${context}: HTTP ${res.status}`,
      res.status,
    );
  }
  let body: unknown;
  try {
    body = await res.json();
  } catch (err) {
    throw new BillingFetchError(
      `malformed JSON from ${context}: ${err instanceof Error ? err.message : String(err)}`,
      res.status,
    );
  }
  if (!validate(body)) {
    throw new BillingFetchError(`unexpected shape from ${context}`, res.status);
  }
  return body;
}

/**
 * Fetch the caller's current subscription (or `null` if none).
 *
 * The backend returns 200 + `{subscription: null}` for non-subscribers,
 * so a 4xx here always represents a real failure (auth / network).
 */
export async function fetchMySubscription(
  fetchImpl: typeof fetch = fetch,
): Promise<MeSubscriptionResponse> {
  return _getJson<MeSubscriptionResponse>(
    "/api/v1/subscriptions/me",
    fetchImpl,
    isMeSubscriptionResponse,
    "/subscriptions/me",
  );
}

/**
 * Fetch the caller's payment history (paginated, 20/page, newest first).
 *
 * @param page 1-indexed page number. Defaults to 1.
 */
export async function fetchPaymentHistory(
  page = 1,
  fetchImpl: typeof fetch = fetch,
): Promise<PaymentHistoryRow[]> {
  return _getJson<PaymentHistoryRow[]>(
    `/api/v1/payments/history?page=${page}`,
    fetchImpl,
    isPaymentHistoryArray,
    "/payments/history",
  );
}

/**
 * Schedule cancellation of the caller's active subscription.
 *
 * The backend flips the row to `status='cancel_at_period_end'` and
 * stamps `cancel_requested_at=now()`. Access continues until
 * `current_period_end`. We return the updated row so the FE can flip
 * the status pill copy without an extra fetch.
 */
export async function cancelMySubscription(
  fetchImpl: typeof fetch = fetch,
): Promise<SubscriptionRow> {
  let res: Response;
  try {
    res = await fetchImpl("/api/v1/subscriptions/cancel", {
      method: "POST",
      credentials: "include",
      headers: { Accept: "application/json" },
    });
  } catch (err) {
    throw new BillingFetchError(
      `network error cancelling subscription: ${err instanceof Error ? err.message : String(err)}`,
      null,
    );
  }
  if (!res.ok) {
    throw new BillingFetchError(
      `non-OK response from /subscriptions/cancel: HTTP ${res.status}`,
      res.status,
    );
  }
  let body: unknown;
  try {
    body = await res.json();
  } catch (err) {
    throw new BillingFetchError(
      `malformed JSON from /subscriptions/cancel: ${err instanceof Error ? err.message : String(err)}`,
      res.status,
    );
  }
  if (!isSubscriptionRow(body)) {
    throw new BillingFetchError(
      `unexpected shape from /subscriptions/cancel`,
      res.status,
    );
  }
  return body;
}

// ---- type guards ----------------------------------------------------------

function isSubscriptionRow(value: unknown): value is SubscriptionRow {
  if (typeof value !== "object" || value === null) return false;
  const v = value as Record<string, unknown>;
  if (typeof v.id !== "string") return false;
  if (v.status !== "active" && v.status !== "cancel_at_period_end")
    return false;
  if (typeof v.monthly_saju_remaining !== "number") return false;
  if (typeof v.current_period_start !== "string") return false;
  if (typeof v.current_period_end !== "string") return false;
  if (
    v.cancel_requested_at !== null &&
    typeof v.cancel_requested_at !== "string"
  )
    return false;
  return true;
}

function isMeSubscriptionResponse(
  value: unknown,
): value is MeSubscriptionResponse {
  if (typeof value !== "object" || value === null) return false;
  const v = value as Record<string, unknown>;
  if (v.subscription === null) return true;
  return isSubscriptionRow(v.subscription);
}

function isPaymentHistoryRow(value: unknown): value is PaymentHistoryRow {
  if (typeof value !== "object" || value === null) return false;
  const v = value as Record<string, unknown>;
  if (typeof v.id !== "string") return false;
  if (v.type !== "single" && v.type !== "subscription") return false;
  if (v.category !== null && typeof v.category !== "string") return false;
  if (typeof v.amount_krw !== "number") return false;
  if (typeof v.status !== "string") return false;
  if (v.paid_at !== null && typeof v.paid_at !== "string") return false;
  if (typeof v.refunded_amount_krw !== "number") return false;
  return true;
}

function isPaymentHistoryArray(value: unknown): value is PaymentHistoryRow[] {
  return Array.isArray(value) && value.every(isPaymentHistoryRow);
}
