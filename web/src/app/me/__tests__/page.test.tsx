/**
 * Unit tests for `/me` (ISSUE-063, Screen 16).
 *
 * AC mapping (issues.md §ISSUE-063):
 *   AC1: logged-in → profile greeting + stats + nav list rendered.
 *   AC2: subscriber → "월 구독 중 — 다음 결제 …" pill displayed.
 *   AC3: not logged in (user_id == null) → router.replace('/auth/login').
 *   AC4: fetch failure → "잠시 후 다시 시도해주세요" + retry button.
 *
 * Strategy:
 *   - Mock next/navigation so we can observe `router.replace` (AC3).
 *   - Stub the global `fetch` per test to drive the page state machine.
 *   - One assertion per AC, plus a retry behavior test.
 */
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, act, waitFor, fireEvent } from '@testing-library/react';
import { useOnboardingStore } from '@/lib/stores/onboarding-store';

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

import MePage from '@/app/me/page';

function mkOkResponse(body: unknown): Response {
  return {
    ok: true,
    status: 200,
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

const MEMBER_BODY = {
  user_id: 'u-1',
  entitlement: {
    kind: 'none',
    token_id: null,
    subscription_id: null,
    has_anything: false,
    requires_payment: true,
  },
} as const;

const SUBSCRIBER_BODY = {
  user_id: 'u-2',
  entitlement: {
    kind: 'subscription',
    token_id: null,
    subscription_id: 'sub-1',
    has_anything: true,
    requires_payment: false,
  },
} as const;

const ANON_BODY = {
  user_id: null,
  entitlement: {
    kind: 'none',
    token_id: null,
    subscription_id: null,
    has_anything: false,
    requires_payment: true,
  },
} as const;

describe('/me — Screen 16 (ISSUE-063)', () => {
  beforeEach(() => {
    replaceMock.mockReset();
    useOnboardingStore.getState().reset();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('AC1: logged-in member sees greeting + stats + nav list', async () => {
    useOnboardingStore.getState().setName('효주');
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => mkOkResponse(MEMBER_BODY)),
    );

    await act(async () => {
      render(<MePage />);
    });
    await waitFor(() => {
      expect(screen.getByTestId('me-loaded')).toBeInTheDocument();
    });

    // Greeting (AC1).
    expect(screen.getByTestId('me-greeting').textContent).toContain('또 왔구나');
    expect(screen.getByTestId('me-greeting').textContent).toContain('효주');

    // Stats strip — 3 cells per ux_spec Screen 16.
    expect(screen.getByTestId('me-stat-readings').textContent).toContain('풀이');
    expect(screen.getByTestId('me-stat-subscription').textContent).toContain('구독 상태');
    expect(screen.getByTestId('me-stat-token').textContent).toContain('무료 토큰');

    // Nav list — 6 rows per issue Scope (In).
    const navList = screen.getByTestId('me-nav-list');
    expect(navList).toBeInTheDocument();
    expect(navList.querySelectorAll('li').length).toBe(6);
    // Sanity-check a couple of the target hrefs.
    expect(screen.getByTestId('me-nav--me-saju')).toHaveAttribute('href', '/me/saju');
    expect(screen.getByTestId('me-nav--me-history')).toHaveAttribute('href', '/me/history');
    expect(screen.getByTestId('me-nav--me-billing')).toHaveAttribute('href', '/me/billing');
    expect(screen.getByTestId('me-nav--legal')).toHaveAttribute('href', '/legal');
  });

  it("AC1: non-onboarded member greeting falls back to '또 왔구나' without a name", async () => {
    // No name in the onboarding store.
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => mkOkResponse(MEMBER_BODY)),
    );
    await act(async () => {
      render(<MePage />);
    });
    await waitFor(() => {
      expect(screen.getByTestId('me-loaded')).toBeInTheDocument();
    });
    const text = screen.getByTestId('me-greeting').textContent ?? '';
    expect(text).toContain('또 왔구나');
    // No comma-name suffix.
    expect(text.endsWith('또 왔구나')).toBe(true);
  });

  it('AC2: subscriber sees the "월 구독 중 — 다음 결제 ..." status pill', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => mkOkResponse(SUBSCRIBER_BODY)),
    );

    await act(async () => {
      render(<MePage />);
    });
    await waitFor(() => {
      expect(screen.getByTestId('me-loaded')).toBeInTheDocument();
    });

    const pill = screen.getByTestId('me-subscription-pill');
    expect(pill).toBeInTheDocument();
    expect(pill.textContent).toContain('월 구독 중');
    expect(pill.textContent).toContain('다음 결제');

    // Subscription stat cell reflects the subscriber state.
    expect(screen.getByTestId('me-stat-subscription').textContent).toContain('구독 중');
  });

  it('non-subscriber state does NOT render the subscription pill', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => mkOkResponse(MEMBER_BODY)),
    );

    await act(async () => {
      render(<MePage />);
    });
    await waitFor(() => {
      expect(screen.getByTestId('me-loaded')).toBeInTheDocument();
    });

    expect(screen.queryByTestId('me-subscription-pill')).not.toBeInTheDocument();
    expect(screen.getByTestId('me-stat-subscription').textContent).toContain('무료');
  });

  it('AC3: anonymous payload (user_id == null) triggers router.replace("/auth/login")', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => mkOkResponse(ANON_BODY)),
    );

    await act(async () => {
      render(<MePage />);
    });

    await waitFor(() => {
      expect(replaceMock).toHaveBeenCalledWith('/auth/login');
    });
  });

  it('AC4: fetch failure (network) renders error state + retry button', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => {
        throw new Error('boom');
      }),
    );

    await act(async () => {
      render(<MePage />);
    });
    await waitFor(() => {
      expect(screen.getByTestId('me-error')).toBeInTheDocument();
    });
    expect(screen.getByTestId('me-error').textContent).toContain('잠시 후 다시 시도해주세요');
    expect(screen.getByTestId('me-retry')).toBeInTheDocument();
  });

  it('AC4: fetch failure (5xx) also renders the same error state', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => mkErrResponse(503)),
    );

    await act(async () => {
      render(<MePage />);
    });
    await waitFor(() => {
      expect(screen.getByTestId('me-error')).toBeInTheDocument();
    });
    expect(screen.getByTestId('me-retry')).toBeInTheDocument();
  });

  it('AC4: tapping retry re-runs the fetch and recovers on success', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(mkErrResponse(503))
      .mockResolvedValueOnce(mkOkResponse(MEMBER_BODY));
    vi.stubGlobal('fetch', fetchMock);

    await act(async () => {
      render(<MePage />);
    });
    await waitFor(() => {
      expect(screen.getByTestId('me-error')).toBeInTheDocument();
    });

    await act(async () => {
      fireEvent.click(screen.getByTestId('me-retry'));
    });
    await waitFor(() => {
      expect(screen.getByTestId('me-loaded')).toBeInTheDocument();
    });
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });
});
