/**
 * Unit tests for `/upsell/subscription` (ISSUE-070, Screen 22).
 *
 * AC mapping (issues.md §ISSUE-070):
 *   AC1: page renders the comparison strip + "구독 시작하기" CTA on
 *        first visit; primary tap → /me/billing/subscribe.
 *   AC2: "다음에 할게요" sets the localStorage flag and routes to /me.
 *   AC3: mount with the flag already set → immediate /me redirect,
 *        page never renders the upsell content.
 */
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';

const pushMock = vi.fn();
const replaceMock = vi.fn();

vi.mock('next/navigation', () => ({
  useRouter: () => ({
    push: pushMock,
    replace: replaceMock,
    back: vi.fn(),
    refresh: vi.fn(),
    prefetch: vi.fn(),
  }),
}));

import {
  UpsellSubscriptionView,
  UPSELL_SHOWN_STORAGE_KEY,
} from '@/app/upsell/subscription/UpsellSubscriptionView';

function makeStorage(initial: Record<string, string> = {}): {
  store: Record<string, string>;
  getItem: ReturnType<typeof vi.fn>;
  setItem: ReturnType<typeof vi.fn>;
} {
  const store: Record<string, string> = { ...initial };
  const getItem = vi.fn((key: string) => (key in store ? store[key] : null));
  const setItem = vi.fn((key: string, value: string) => {
    store[key] = value;
  });
  return { store, getItem, setItem };
}

describe('UpsellSubscriptionView', () => {
  beforeEach(() => {
    pushMock.mockClear();
    replaceMock.mockClear();
  });

  it('AC1: renders the headline, comparison strip, and both CTAs on first visit', () => {
    const storage = makeStorage();

    render(<UpsellSubscriptionView storageImpl={storage} />);

    // Headline (copy_guide §3 verbatim split across two lines).
    expect(screen.getByText('매번 결제할래,')).toBeInTheDocument();
    expect(screen.getByText('매달 다 받을래?')).toBeInTheDocument();

    // Comparison strip — both single price × 2 and subscription price.
    expect(screen.getByTestId('upsell-single-line')).toHaveTextContent(
      '단건 4,900원 × 2 = 9,800원',
    );
    expect(screen.getByTestId('upsell-subscription-line')).toHaveTextContent('구독 9,900원');
    expect(screen.getByTestId('upsell-subscription-line')).toHaveTextContent('매일 타로까지');

    // Both CTAs visible.
    expect(screen.getByRole('link', { name: /구독 시작/ })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '다음에' })).toBeInTheDocument();

    // Did NOT redirect — first visit.
    expect(replaceMock).not.toHaveBeenCalled();
  });

  it('AC1: primary CTA points at /me/billing/subscribe', () => {
    const storage = makeStorage();

    render(<UpsellSubscriptionView storageImpl={storage} />);

    const primary = screen.getByRole('link', { name: /구독 시작/ });
    expect(primary).toHaveAttribute('href', '/me/billing/subscribe');
  });

  it('AC2: tap "다음에" → setItem(vs_upsell_shown,true) + router.push("/me")', () => {
    const storage = makeStorage();

    render(<UpsellSubscriptionView storageImpl={storage} />);

    fireEvent.click(screen.getByRole('button', { name: '다음에' }));

    expect(storage.setItem).toHaveBeenCalledWith(UPSELL_SHOWN_STORAGE_KEY, 'true');
    expect(storage.store[UPSELL_SHOWN_STORAGE_KEY]).toBe('true');
    expect(pushMock).toHaveBeenCalledWith('/me');
  });

  it('AC3: when localStorage flag is already "true" → immediate replace(/me); upsell content never rendered', async () => {
    const storage = makeStorage({ [UPSELL_SHOWN_STORAGE_KEY]: 'true' });

    const { container } = render(<UpsellSubscriptionView storageImpl={storage} />);

    await waitFor(() => {
      expect(replaceMock).toHaveBeenCalledWith('/me');
    });

    // The upsell headline is NOT visible because the component
    // short-circuits to `return null` while the redirect fires.
    expect(screen.queryByText('매번 결제할래,')).not.toBeInTheDocument();
    expect(container.firstChild).toBeNull();
  });

  it('does not crash when storage throws (private-browsing fallback)', () => {
    const throwStorage = {
      getItem: vi.fn(() => {
        throw new Error('SecurityError');
      }),
      setItem: vi.fn(() => {
        throw new Error('SecurityError');
      }),
    };

    // Mount should still render the upsell (flag couldn't be read).
    render(<UpsellSubscriptionView storageImpl={throwStorage} />);
    expect(screen.getByText('매번 결제할래,')).toBeInTheDocument();

    // Dismiss should still navigate even when setItem throws.
    fireEvent.click(screen.getByRole('button', { name: '다음에' }));
    expect(pushMock).toHaveBeenCalledWith('/me');
  });

  it('renders the footnote "언제든 해지할 수 있어." per copy_guide §3', () => {
    const storage = makeStorage();
    render(<UpsellSubscriptionView storageImpl={storage} />);
    expect(screen.getByText('언제든 해지할 수 있어.')).toBeInTheDocument();
  });
});
