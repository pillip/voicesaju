/**
 * Unit tests for `/auth/login` page (ISSUE-027, Screen 15).
 *
 * AC coverage:
 * - Web user sees BOTH 카카오로 시작하기 + Apple로 시작하기 buttons.
 * - Toss WebView user sees ONLY 토스로 계속하기 button.
 * - Kakao tap → href is `/api/v1/auth/kakao/start` (per ISSUE-026 routes).
 *   We assert the anchor href rather than `window.location.assign` because
 *   the page uses real anchors for accessibility and progressive enhancement;
 *   the Playwright spec in `tests/e2e/auth-login.spec.ts` covers actual browser
 *   navigation once Playwright lands.
 * - Page renders the cancellation banner when ?error=cancelled is in the URL.
 *
 * Why mock next/navigation:
 * - `useSearchParams` requires the App Router runtime which is not present in
 *   jsdom. We provide a thin module-level mock and flip it per test.
 */
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { render, screen, act } from '@testing-library/react';
import { RuntimeProvider } from '@/lib/context/runtime-context';

// next/navigation mock — pluggable per-test via the exported setter.
let currentSearchParams = new URLSearchParams();
vi.mock('next/navigation', () => ({
  useSearchParams: () => currentSearchParams,
}));

import LoginPage from '@/app/auth/login/page';

function setUserAgent(ua: string) {
  Object.defineProperty(window.navigator, 'userAgent', {
    value: ua,
    configurable: true,
    writable: true,
  });
}

function renderPage() {
  return render(
    <RuntimeProvider>
      <LoginPage />
    </RuntimeProvider>,
  );
}

describe('/auth/login page — Screen 15', () => {
  beforeEach(() => {
    currentSearchParams = new URLSearchParams();
    setUserAgent(
      'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    );
  });

  it('renders the Screen 15 page title', async () => {
    await act(async () => {
      renderPage();
    });
    expect(
      screen.getByRole('heading', { name: 'VoiceSaju에 오신 걸 환영해요' }),
    ).toBeInTheDocument();
  });

  it('web channel renders BOTH Kakao + Apple buttons', async () => {
    await act(async () => {
      renderPage();
    });
    expect(screen.getByRole('link', { name: '카카오로 시작하기' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Apple로 시작하기' })).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: '토스로 계속하기' })).toBeNull();
  });

  it('Toss WebView channel renders ONLY the Toss button', async () => {
    setUserAgent('Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 Toss/5.180.0');
    await act(async () => {
      renderPage();
    });
    expect(screen.getByRole('link', { name: '토스로 계속하기' })).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: '카카오로 시작하기' })).toBeNull();
    expect(screen.queryByRole('link', { name: 'Apple로 시작하기' })).toBeNull();
  });

  it('Kakao button href points at the ISSUE-026 start route', async () => {
    await act(async () => {
      renderPage();
    });
    expect(screen.getByRole('link', { name: '카카오로 시작하기' })).toHaveAttribute(
      'href',
      '/api/v1/auth/kakao/start',
    );
  });

  it('Apple button href points at the ISSUE-026 start route', async () => {
    await act(async () => {
      renderPage();
    });
    expect(screen.getByRole('link', { name: 'Apple로 시작하기' })).toHaveAttribute(
      'href',
      '/api/v1/auth/apple/start',
    );
  });

  it('does not render the cancellation banner by default', async () => {
    await act(async () => {
      renderPage();
    });
    expect(screen.queryByRole('alert')).toBeNull();
  });

  it('renders 로그인이 취소됐어요 banner when ?error=cancelled is present', async () => {
    currentSearchParams = new URLSearchParams('error=cancelled');
    await act(async () => {
      renderPage();
    });
    const banner = screen.getByRole('alert');
    expect(banner).toHaveTextContent('로그인이 취소됐어요');
  });

  it('buttons remain enabled (clickable) when the cancellation banner is shown — re-enable AC', async () => {
    currentSearchParams = new URLSearchParams('error=cancelled');
    await act(async () => {
      renderPage();
    });
    const kakao = screen.getByRole('link', { name: '카카오로 시작하기' });
    // aria-disabled should NOT be set so the user can retry login (AC4).
    expect(kakao).not.toHaveAttribute('aria-disabled', 'true');
  });

  it('renders the legal footer copy from Screen 15', async () => {
    await act(async () => {
      renderPage();
    });
    expect(screen.getByText(/로그인 시 이용약관 및 개인정보 처리방침에 동의/)).toBeInTheDocument();
  });
});
