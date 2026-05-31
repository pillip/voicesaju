/**
 * Unit tests for `web/src/lib/api/billing.ts` (ISSUE-067).
 *
 * Exercises each fetcher's branches separately so the page tests can
 * trust the typed shapes and focus on UI state transitions.
 */
import { describe, expect, it, vi } from 'vitest';

import {
  BillingFetchError,
  cancelMySubscription,
  createSubscription,
  fetchMySubscription,
  fetchPaymentHistory,
} from '@/lib/api/billing';

function mkResponse(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  } as unknown as Response;
}

const SUB_ROW = {
  id: 'sub-1',
  status: 'active',
  monthly_saju_remaining: 1,
  current_period_start: '2026-05-01T00:00:00+00:00',
  current_period_end: '2026-05-31T00:00:00+00:00',
  cancel_requested_at: null,
} as const;

const PAYMENT_ROW = {
  id: 'pmt-1',
  type: 'single',
  category: null,
  amount_krw: 5900,
  status: 'paid',
  paid_at: '2026-05-01T00:00:00+00:00',
  refunded_amount_krw: 0,
} as const;

describe('fetchMySubscription', () => {
  it('returns the subscription envelope on 200 with row', async () => {
    const fetchImpl = vi.fn().mockResolvedValueOnce(mkResponse({ subscription: SUB_ROW }));

    const result = await fetchMySubscription(fetchImpl);
    expect(result.subscription).not.toBeNull();
    expect(result.subscription?.id).toBe('sub-1');
    expect(result.subscription?.status).toBe('active');
  });

  it('returns null subscription on 200 with empty envelope', async () => {
    const fetchImpl = vi.fn().mockResolvedValueOnce(mkResponse({ subscription: null }));

    const result = await fetchMySubscription(fetchImpl);
    expect(result.subscription).toBeNull();
  });

  it('throws BillingFetchError with status=401 on auth failure', async () => {
    const fetchImpl = vi.fn().mockResolvedValueOnce(mkResponse({}, 401));

    await expect(fetchMySubscription(fetchImpl)).rejects.toMatchObject({
      name: 'BillingFetchError',
      status: 401,
    });
  });

  it('throws BillingFetchError with status=null on a network failure', async () => {
    const fetchImpl = vi.fn().mockRejectedValueOnce(new Error('offline'));

    await expect(fetchMySubscription(fetchImpl)).rejects.toMatchObject({
      name: 'BillingFetchError',
      status: null,
    });
  });

  it('rejects an unexpected shape', async () => {
    const fetchImpl = vi.fn().mockResolvedValueOnce(mkResponse({ wrong: 'shape' }));

    await expect(fetchMySubscription(fetchImpl)).rejects.toBeInstanceOf(BillingFetchError);
  });
});

describe('fetchPaymentHistory', () => {
  it('returns the typed list on 200', async () => {
    const fetchImpl = vi.fn().mockResolvedValueOnce(mkResponse([PAYMENT_ROW]));

    const rows = await fetchPaymentHistory(1, fetchImpl);
    expect(rows.length).toBe(1);
    expect(rows[0].id).toBe('pmt-1');
    expect(rows[0].amount_krw).toBe(5900);
  });

  it('encodes the page query param', async () => {
    const fetchImpl = vi.fn().mockResolvedValueOnce(mkResponse([]));

    await fetchPaymentHistory(3, fetchImpl);
    expect(fetchImpl).toHaveBeenCalledWith('/api/v1/payments/history?page=3', expect.any(Object));
  });

  it('returns [] on an empty 200 response', async () => {
    const fetchImpl = vi.fn().mockResolvedValueOnce(mkResponse([]));

    const rows = await fetchPaymentHistory(1, fetchImpl);
    expect(rows).toEqual([]);
  });

  it('throws BillingFetchError on 500', async () => {
    const fetchImpl = vi.fn().mockResolvedValueOnce(mkResponse({}, 500));

    await expect(fetchPaymentHistory(1, fetchImpl)).rejects.toMatchObject({
      name: 'BillingFetchError',
      status: 500,
    });
  });
});

describe('cancelMySubscription', () => {
  it('returns the updated row on 200', async () => {
    const updated = {
      ...SUB_ROW,
      status: 'cancel_at_period_end',
      cancel_requested_at: '2026-05-15T00:00:00+00:00',
    };
    const fetchImpl = vi.fn().mockResolvedValueOnce(mkResponse(updated));

    const result = await cancelMySubscription(fetchImpl);
    expect(result.status).toBe('cancel_at_period_end');
    expect(result.cancel_requested_at).toBe('2026-05-15T00:00:00+00:00');
    // Verify POST + credentials.
    expect(fetchImpl).toHaveBeenCalledWith(
      '/api/v1/subscriptions/cancel',
      expect.objectContaining({ method: 'POST', credentials: 'include' }),
    );
  });

  it('throws BillingFetchError with status=404 when no active row', async () => {
    const fetchImpl = vi.fn().mockResolvedValueOnce(mkResponse({}, 404));

    await expect(cancelMySubscription(fetchImpl)).rejects.toMatchObject({
      name: 'BillingFetchError',
      status: 404,
    });
  });

  it('throws BillingFetchError on a network failure', async () => {
    const fetchImpl = vi.fn().mockRejectedValueOnce(new Error('offline'));

    await expect(cancelMySubscription(fetchImpl)).rejects.toMatchObject({
      name: 'BillingFetchError',
      status: null,
    });
  });
});

describe('createSubscription', () => {
  it('returns the active row on 201', async () => {
    const fetchImpl = vi.fn().mockResolvedValueOnce(mkResponse(SUB_ROW, 201));

    const result = await createSubscription(fetchImpl);
    expect(result.id).toBe('sub-1');
    expect(result.status).toBe('active');
    // POSTs JSON body with default method=tosspay.
    expect(fetchImpl).toHaveBeenCalledWith(
      '/api/v1/subscriptions',
      expect.objectContaining({ method: 'POST', credentials: 'include' }),
    );
    const init = fetchImpl.mock.calls[0]?.[1] as RequestInit | undefined;
    expect(init?.body).toBe(JSON.stringify({ method: 'tosspay' }));
  });

  it('returns the existing row on 200 (idempotent)', async () => {
    const fetchImpl = vi.fn().mockResolvedValueOnce(mkResponse(SUB_ROW, 200));

    const result = await createSubscription(fetchImpl);
    expect(result.id).toBe('sub-1');
  });

  it('passes the kakaopay method when requested', async () => {
    const fetchImpl = vi.fn().mockResolvedValueOnce(mkResponse(SUB_ROW, 201));
    await createSubscription(fetchImpl, 'kakaopay');
    const init = fetchImpl.mock.calls[0]?.[1] as RequestInit | undefined;
    expect(init?.body).toBe(JSON.stringify({ method: 'kakaopay' }));
  });

  it('throws BillingFetchError with status=401 on unauthenticated', async () => {
    const fetchImpl = vi.fn().mockResolvedValueOnce(mkResponse({}, 401));
    await expect(createSubscription(fetchImpl)).rejects.toMatchObject({
      name: 'BillingFetchError',
      status: 401,
    });
  });

  it('throws BillingFetchError on a network failure', async () => {
    const fetchImpl = vi.fn().mockRejectedValueOnce(new Error('offline'));
    await expect(createSubscription(fetchImpl)).rejects.toMatchObject({
      name: 'BillingFetchError',
      status: null,
    });
  });

  it('throws BillingFetchError on a malformed response shape', async () => {
    const fetchImpl = vi.fn().mockResolvedValueOnce(mkResponse({ wrong: true }));
    await expect(createSubscription(fetchImpl)).rejects.toMatchObject({
      name: 'BillingFetchError',
    });
  });
});
