/**
 * Unit tests for `/me/billing/subscribe` (ISSUE-069).
 *
 * AC mapping (issues.md §ISSUE-069):
 *   AC1: tap "구독 시작하기" → Toss SDK modal opens within 1s
 *        (here: the SubscribeView auto-kicks the flow on mount).
 *   AC2: payment succeeds → router.replace('/me/billing').
 *   AC3: payment fails → "결제가 실패했어요" banner + "다시 결제하기"
 *        retry button.
 */
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';

const replaceMock = vi.fn();

vi.mock('next/navigation', () => ({
  useRouter: () => ({
    push: vi.fn(),
    replace: replaceMock,
    back: vi.fn(),
    refresh: vi.fn(),
    prefetch: vi.fn(),
  }),
}));

import { SubscribeView } from '@/app/me/billing/subscribe/SubscribeView';

function mkOkResponse(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  } as unknown as Response;
}

function mkErrResponse(status: number): Response {
  return {
    ok: false,
    status,
    json: async () => ({}),
  } as unknown as Response;
}

const ACTIVE_SUB = {
  id: 'sub-69',
  status: 'active',
  monthly_saju_remaining: 1,
  current_period_start: '2026-05-29T00:00:00+00:00',
  current_period_end: '2026-06-28T00:00:00+00:00',
  cancel_requested_at: null,
};

describe('SubscribeView', () => {
  beforeEach(() => {
    replaceMock.mockClear();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('AC2: on mount, POSTs /subscriptions and redirects to /me/billing on success (no SDK)', async () => {
    const fetchMock = vi.fn().mockResolvedValueOnce(mkOkResponse(ACTIVE_SUB, 201));

    render(<SubscribeView fetchImpl={fetchMock as unknown as typeof fetch} />);

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalled();
    });

    // Backend POST was called with the expected URL + method.
    expect(fetchMock.mock.calls[0][0]).toBe('/api/v1/subscriptions');
    expect((fetchMock.mock.calls[0][1] as RequestInit | undefined)?.method).toBe('POST');

    // Success redirect.
    await waitFor(() => {
      expect(replaceMock).toHaveBeenCalledWith('/me/billing');
    });
  });

  it('AC1: SDK modal opens within 1s when window.TossPayments is available', async () => {
    type BillingArgs = {
      customerKey: string;
      successUrl: string;
      failUrl: string;
    };
    const requestBillingAuth = vi.fn(async (_args: BillingArgs) => undefined);
    const tossFactory = vi.fn((_clientKey: string) => ({ requestBillingAuth }));
    const fakeWindow = {
      TossPayments: tossFactory,
    } as unknown as Window;

    const fetchMock = vi.fn(async () => mkOkResponse(ACTIVE_SUB, 201));

    const start = Date.now();
    render(
      <SubscribeView fetchImpl={fetchMock as unknown as typeof fetch} windowImpl={fakeWindow} />,
    );

    await waitFor(() => {
      expect(tossFactory).toHaveBeenCalledTimes(1);
      expect(requestBillingAuth).toHaveBeenCalledTimes(1);
    });
    const elapsedMs = Date.now() - start;
    expect(elapsedMs).toBeLessThan(1000);

    // Confirm the SDK saw the customerKey we minted from the backend
    // row + a redirect URL that lands the user back on /me/billing.
    const billArgs = requestBillingAuth.mock.calls[0][0] as {
      customerKey: string;
      successUrl: string;
      failUrl: string;
    };
    expect(billArgs.customerKey).toBe('sub-69');
    expect(billArgs.successUrl).toBe('/me/billing');

    await waitFor(() => {
      expect(replaceMock).toHaveBeenCalledWith('/me/billing');
    });
  });

  it('AC3: shows "결제가 실패했어요" banner + "다시 결제하기" retry on backend failure', async () => {
    const fetchMock = vi.fn(async () => mkErrResponse(500));

    render(<SubscribeView fetchImpl={fetchMock as unknown as typeof fetch} />);

    await waitFor(() => {
      expect(screen.getByText('결제가 실패했어요')).toBeInTheDocument();
      expect(screen.getByRole('button', { name: '다시 결제하기' })).toBeInTheDocument();
    });

    // No redirect on failure.
    expect(replaceMock).not.toHaveBeenCalledWith('/me/billing');
  });

  it('AC3: retry button re-attempts the POST', async () => {
    let callCount = 0;
    const fetchMock = vi.fn(async () => {
      callCount += 1;
      if (callCount === 1) return mkErrResponse(500);
      return mkOkResponse(ACTIVE_SUB, 201);
    });

    render(<SubscribeView fetchImpl={fetchMock as unknown as typeof fetch} />);

    await waitFor(() => {
      expect(screen.getByText('결제가 실패했어요')).toBeInTheDocument();
    });

    const retry = screen.getByRole('button', { name: '다시 결제하기' });
    fireEvent.click(retry);

    await waitFor(() => {
      expect(replaceMock).toHaveBeenCalledWith('/me/billing');
    });
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it('AC3: shows failure banner when the SDK requestBillingAuth rejects', async () => {
    const requestBillingAuth = vi.fn(async () => {
      throw new Error('user_cancelled');
    });
    const tossFactory = vi.fn(() => ({ requestBillingAuth }));
    const fakeWindow = {
      TossPayments: tossFactory,
    } as unknown as Window;
    const fetchMock = vi.fn(async () => mkOkResponse(ACTIVE_SUB, 201));

    render(
      <SubscribeView fetchImpl={fetchMock as unknown as typeof fetch} windowImpl={fakeWindow} />,
    );

    await waitFor(() => {
      expect(screen.getByText('결제가 실패했어요')).toBeInTheDocument();
    });
    expect(replaceMock).not.toHaveBeenCalledWith('/me/billing');
  });

  it('redirects to /auth/login on 401 from backend', async () => {
    const fetchMock = vi.fn(async () => mkErrResponse(401));

    render(<SubscribeView fetchImpl={fetchMock as unknown as typeof fetch} />);

    await waitFor(() => {
      expect(replaceMock).toHaveBeenCalledWith('/auth/login');
    });
  });
});
