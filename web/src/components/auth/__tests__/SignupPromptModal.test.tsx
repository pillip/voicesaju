/**
 * Unit tests for {@link SignupPromptModal} — Screen 25 of `docs/ux_spec.md`.
 *
 * AC coverage (from ISSUE-027 — the modal is the optional Screen-25 surface
 * invoked from non-member flows, not from `/auth/login` directly):
 * - Web channel renders both Kakao + Apple buttons.
 * - Toss WebView channel renders only the Toss button.
 * - The modal exposes loading + error states with the exact Korean copy
 *   from `docs/ux_spec.md` §4 Screen 25.
 *
 * Why a snapshot test PLUS targeted assertions:
 * - The issue's "Tests" section explicitly calls for "Vitest snapshot for
 *   SignupPromptModal default/loading/error states".
 * - Snapshots alone are easy to over-approve, so we pair them with assertions
 *   on the load-bearing strings + button counts so a future regression on the
 *   copy or runtime-context branching produces a meaningful failure message.
 */
import { describe, expect, it, vi } from 'vitest';
import { render, screen, fireEvent, act } from '@testing-library/react';
import { RuntimeProvider } from '@/lib/context/runtime-context';
import { SignupPromptModal } from '@/components/auth/SignupPromptModal';

// The provider's internal context is private, so we set the UA before render
// instead of mocking the context. This mirrors the runtime-context tests so
// behaviour stays end-to-end equivalent.
function setUserAgent(ua: string) {
  Object.defineProperty(window.navigator, 'userAgent', {
    value: ua,
    configurable: true,
    writable: true,
  });
}

function renderModal(ui: React.ReactElement) {
  // Wrap with RuntimeProvider so the UA-based channel detection runs.
  return render(<RuntimeProvider>{ui}</RuntimeProvider>);
}

describe('SignupPromptModal — Screen 25', () => {
  beforeEach(() => {
    // Reset to a vanilla Chrome UA so the default branch is `web`.
    setUserAgent(
      'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    );
  });

  it('renders the Screen 25 headline + body copy when open', async () => {
    await act(async () => {
      renderModal(<SignupPromptModal open onClose={() => {}} />);
    });
    expect(screen.getByText('결과 저장하려면 1초 가입')).toBeInTheDocument();
    expect(
      screen.getByText('지금 들은 풀이를 마이페이지에 영구 저장해드려요.'),
    ).toBeInTheDocument();
  });

  it('does not render anything when open=false', () => {
    renderModal(<SignupPromptModal open={false} onClose={() => {}} />);
    expect(screen.queryByRole('dialog')).toBeNull();
  });

  it('web channel renders BOTH Kakao + Apple buttons (no Toss button)', async () => {
    await act(async () => {
      renderModal(<SignupPromptModal open onClose={() => {}} />);
    });
    expect(screen.getByRole('link', { name: '카카오로 시작하기' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Apple로 시작하기' })).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: '토스로 계속하기' })).toBeNull();
  });

  it('Toss WebView channel renders ONLY the Toss button', async () => {
    setUserAgent('Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 Toss/5.180.0');
    await act(async () => {
      renderModal(<SignupPromptModal open onClose={() => {}} />);
    });
    expect(screen.getByRole('link', { name: '토스로 계속하기' })).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: '카카오로 시작하기' })).toBeNull();
    expect(screen.queryByRole('link', { name: 'Apple로 시작하기' })).toBeNull();
  });

  it('provider links point at the /api/v1/auth/{provider}/start endpoints', async () => {
    await act(async () => {
      renderModal(<SignupPromptModal open onClose={() => {}} />);
    });
    expect(screen.getByRole('link', { name: '카카오로 시작하기' })).toHaveAttribute(
      'href',
      '/api/v1/auth/kakao/start',
    );
    expect(screen.getByRole('link', { name: 'Apple로 시작하기' })).toHaveAttribute(
      'href',
      '/api/v1/auth/apple/start',
    );
  });

  it("renders the '나중에 할게' dismissal link and calls onClose when clicked", async () => {
    const onClose = vi.fn();
    await act(async () => {
      renderModal(<SignupPromptModal open onClose={onClose} />);
    });
    const later = screen.getByRole('button', { name: '나중에 할게' });
    fireEvent.click(later);
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('loading=true marks buttons as aria-busy + aria-disabled (anchors)', async () => {
    await act(async () => {
      renderModal(<SignupPromptModal open onClose={() => {}} loading />);
    });
    const kakao = screen.getByRole('link', { name: /카카오로 시작하기/ });
    // aria-busy on the anchor so screen readers announce the redirect.
    expect(kakao).toHaveAttribute('aria-busy', 'true');
    expect(kakao).toHaveAttribute('aria-disabled', 'true');
  });

  it('error=true renders the cancellation banner inside the modal', async () => {
    await act(async () => {
      renderModal(<SignupPromptModal open onClose={() => {}} error />);
    });
    // The banner must live INSIDE the dialog so the message is associated
    // with the modal context (per Screen 25 spec).
    const dialog = screen.getByRole('dialog');
    const banner = screen.getByRole('alert');
    expect(banner).toHaveTextContent('로그인이 취소됐어요');
    expect(dialog.contains(banner)).toBe(true);
  });

  it('snapshot — default state (web)', async () => {
    let html = '';
    await act(async () => {
      const { container } = renderModal(<SignupPromptModal open onClose={() => {}} />);
      html = container.innerHTML;
    });
    expect(html).toMatchSnapshot();
  });

  it('snapshot — loading state (web)', async () => {
    let html = '';
    await act(async () => {
      const { container } = renderModal(<SignupPromptModal open onClose={() => {}} loading />);
      html = container.innerHTML;
    });
    expect(html).toMatchSnapshot();
  });

  it('snapshot — error state (web)', async () => {
    let html = '';
    await act(async () => {
      const { container } = renderModal(<SignupPromptModal open onClose={() => {}} error />);
      html = container.innerHTML;
    });
    expect(html).toMatchSnapshot();
  });
});
