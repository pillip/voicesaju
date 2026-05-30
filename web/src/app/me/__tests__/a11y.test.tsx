/**
 * axe-core WCAG 2.1 AA scan for /me (ISSUE-063, NFR-012).
 *
 * One scan per page is the project convention. We scan the loaded member
 * state because that's the canonical render — loading/error states reuse
 * the same shell and are covered structurally in page.test.tsx.
 *
 * `color-contrast` is disabled because jsdom doesn't compute real CSS — the
 * design system already passes contrast at the token level.
 */
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { render, waitFor, act } from '@testing-library/react';
import { axe, toHaveNoViolations } from 'jest-axe';
import { useOnboardingStore } from '@/lib/stores/onboarding-store';

vi.mock('next/navigation', () => ({
  useRouter: () => ({
    push: vi.fn(),
    replace: vi.fn(),
    back: vi.fn(),
    refresh: vi.fn(),
    prefetch: vi.fn(),
  }),
}));

import MePage from '@/app/me/page';

expect.extend(toHaveNoViolations);

const axeRules = {
  'color-contrast': { enabled: false },
};

function mkOkResponse(body: unknown): Response {
  return {
    ok: true,
    status: 200,
    json: async () => body,
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
};

describe('/me — WCAG 2.1 AA', () => {
  beforeEach(() => {
    useOnboardingStore.getState().reset();
    useOnboardingStore.getState().setName('효주');
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => mkOkResponse(MEMBER_BODY)),
    );
  });

  it('has zero axe violations on the loaded member state', async () => {
    let container: HTMLElement | undefined;
    await act(async () => {
      ({ container } = render(<MePage />));
    });
    await waitFor(() => {
      expect(container!.querySelector('[data-testid="me-loaded"]')).not.toBeNull();
    });
    const results = await axe(container!, { rules: axeRules });
    expect(results).toHaveNoViolations();
  });
});
