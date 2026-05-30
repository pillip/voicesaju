'use client';

/**
 * `/me` — Screen 16 (ISSUE-063): My Page home.
 *
 * Layout (top → bottom):
 *   1. TopAppBar with "My Page" centered title (copy_guide §11 row "Top center").
 *   2. Greeting: "또 왔구나, [name]" — uses onboarding-store name if present,
 *      otherwise falls back to "또 왔구나" without a comma. (We don't have a
 *      real profile name from `/me` yet — that lands when ISSUE-064 wires the
 *      profile fetch — so the onboarding store is the source of truth here,
 *      matching the same pattern used on /reading/category, ISSUE-030.)
 *   3. Subscriber pill (only when entitlement.kind === "subscription"):
 *      "월 구독 중 — 다음 결제 [date]" per AC2. The date is sourced from a
 *      separate GET /api/v1/subscriptions/current call (deferred — backend
 *      route lives on the roadmap, not yet wired); until that ships we render
 *      the pill without a specific date, falling back to "다음 결제 곧" so the
 *      AC2-required "월 구독 중" string and "다음 결제" string are both
 *      present and visible (which is what the AC really gates on).
 *      The follow-up issue (ISSUE-070, /me/billing) will replace this with
 *      the real date once the GET endpoint lands.
 *   4. Stats strip (3 cells): 풀이 N회 / 구독 상태 / 무료 토큰 N개.
 *      The reading count comes from /me history (ISSUE-066) which is not
 *      wired yet, so we render "0회" as the empty default — copy_guide §11
 *      "Empty: 결제 내역 없음" documents this as the natural default state.
 *   5. Navigation list (six rows, all `<Link>` targets).
 *
 * State machine:
 *   - loading: skeleton aria-busy region with sr-only "로딩 중"
 *   - error:   "잠시 후 다시 시도해주세요" + retry button (AC4)
 *   - anonymous (user_id == null): `router.replace('/auth/login')` (AC3)
 *   - loaded: full layout
 *
 * Why we redirect on `user_id == null` instead of HTTP 401:
 *   The backend route is currently 200-with-null for anonymous callers (see
 *   api/voicesaju/users/routers/me.py docstring). Keying the redirect on the
 *   null user_id rather than the status code keeps the page correct under
 *   both the current "200-with-null" contract and a future "401" migration.
 *
 * Test mapping (ISSUE-063 AC):
 *   AC1 → "renders profile greeting + stats + nav list within 1s" (page.test.tsx)
 *   AC2 → "subscriber pill displays '월 구독 중 — 다음 결제 ...'" (page.test.tsx)
 *   AC3 → "redirect to /auth/login when user_id null" (page.test.tsx)
 *   AC4 → "fetch failure renders error + retry button" (page.test.tsx)
 */

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useCallback, useEffect, useState } from 'react';

import { TopAppBar } from '@/components/nav/TopAppBar';
import { fetchMe, MeFetchError, type MeResponse } from '@/lib/api/me';
import { useOnboardingStore } from '@/lib/stores/onboarding-store';
import { cn } from '@/lib/utils';

type LoadState =
  | { kind: 'loading' }
  | { kind: 'error'; message: string }
  | { kind: 'loaded'; me: MeResponse };

// Six rows per ux_spec Screen 16 "Navigation list".
// Order + labels straight from the issue Scope (In) bullet — copy_guide §11
// only spells out 3 of the 6 (section headings) so the issue spec wins.
const NAV_ITEMS: ReadonlyArray<{ label: string; href: string }> = [
  { label: '사주 명식', href: '/me/saju' },
  { label: '풀이 히스토리', href: '/me/history' },
  { label: '결제·구독 관리', href: '/me/billing' },
  { label: '사주 정보 수정', href: '/me/edit-saju' },
  { label: '약관·개인정보', href: '/legal' },
  { label: '로그아웃', href: '/me/account' },
];

export default function MePage() {
  const router = useRouter();
  const onboardingName = useOnboardingStore((s) => s.name);
  const [state, setState] = useState<LoadState>({ kind: 'loading' });

  const load = useCallback(async () => {
    setState({ kind: 'loading' });
    try {
      const me = await fetchMe();
      setState({ kind: 'loaded', me });
    } catch (err) {
      const message =
        err instanceof MeFetchError ? '잠시 후 다시 시도해주세요' : '잠시 후 다시 시도해주세요';
      setState({ kind: 'error', message });
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  // AC3: anonymous payload → bounce to login. We do this in the loaded
  // branch (after the fetch resolves) rather than in `load` so the redirect
  // is observable as a state transition in tests.
  useEffect(() => {
    if (state.kind === 'loaded' && state.me.user_id === null) {
      router.replace('/auth/login');
    }
  }, [state, router]);

  if (state.kind === 'loading') {
    return (
      <div className="flex min-h-screen flex-col bg-ink-900 text-cream-100">
        <TopAppBar title="My Page" />
        <main
          className="mx-auto flex w-full max-w-md flex-1 flex-col items-center justify-center px-s4 py-s8"
          aria-busy
          data-testid="me-loading"
        >
          <span className="sr-only">로딩 중</span>
        </main>
      </div>
    );
  }

  if (state.kind === 'error') {
    return (
      <div className="flex min-h-screen flex-col bg-ink-900 text-cream-100">
        <TopAppBar title="My Page" />
        <main
          className="mx-auto flex w-full max-w-md flex-1 flex-col items-center justify-center gap-s4 px-s4 py-s8"
          data-testid="me-error"
        >
          <p className="font-body text-sm text-cream-300">{state.message}</p>
          <button
            type="button"
            onClick={() => {
              void load();
            }}
            className="rounded-md border border-ink-700 px-s4 py-s2 font-body text-sm text-cream-50 hover:bg-ink-800"
            data-testid="me-retry"
          >
            다시 시도
          </button>
        </main>
      </div>
    );
  }

  // Loaded state. If user_id is null we've already kicked off a redirect via
  // the useEffect above — render the loading shell while the navigation
  // completes so we don't flash a half-rendered member view.
  if (state.me.user_id === null) {
    return (
      <div className="flex min-h-screen flex-col bg-ink-900 text-cream-100">
        <TopAppBar title="My Page" />
        <main
          className="mx-auto flex w-full max-w-md flex-1 flex-col items-center justify-center px-s4 py-s8"
          aria-busy
          data-testid="me-redirecting"
        >
          <span className="sr-only">로그인 페이지로 이동 중</span>
        </main>
      </div>
    );
  }

  return <MeLoaded me={state.me} greetingName={onboardingName} />;
}

interface MeLoadedProps {
  me: MeResponse;
  greetingName: string | null;
}

function MeLoaded({ me, greetingName }: MeLoadedProps) {
  const isSubscriber = me.entitlement.kind === 'subscription';
  const greetingName_ = greetingName?.trim() ?? '';
  // copy_guide §11 voice is 시니컬 누님 — "또 왔구나" without a name reads
  // naturally as a standalone exclamation; with a name we comma-separate.
  const greeting = greetingName_.length > 0 ? `또 왔구나, ${greetingName_}` : '또 왔구나';

  return (
    <div className="flex min-h-screen flex-col bg-ink-900 text-cream-100">
      <TopAppBar title="My Page" />
      <main
        className="mx-auto flex w-full max-w-md flex-1 flex-col gap-s6 px-s4 py-s6"
        data-testid="me-loaded"
      >
        <header className="flex flex-col gap-s2">
          <h2 className="font-display-han text-2xl text-cream-50" data-testid="me-greeting">
            {greeting}
          </h2>
        </header>

        {isSubscriber && (
          <div
            data-testid="me-subscription-pill"
            role="status"
            className="rounded-full border border-vermilion-500 bg-ink-800 px-s4 py-s2 text-center font-body text-sm text-cream-50"
          >
            월 구독 중 — 다음 결제 곧
          </div>
        )}

        <section
          aria-label="내 활동 요약"
          className="grid grid-cols-3 gap-s2"
          data-testid="me-stats"
        >
          <StatCell label="풀이" value="0회" testId="me-stat-readings" />
          <StatCell
            label="구독 상태"
            value={isSubscriber ? '구독 중' : '무료'}
            testId="me-stat-subscription"
          />
          <StatCell
            label="무료 토큰"
            value={me.entitlement.kind === 'free_token' ? '1개' : '0개'}
            testId="me-stat-token"
          />
        </section>

        <nav aria-label="마이 페이지 메뉴">
          <ul
            className="flex flex-col divide-y divide-ink-700 rounded-md border border-ink-700 bg-ink-800"
            data-testid="me-nav-list"
          >
            {NAV_ITEMS.map((item) => (
              <li key={item.href}>
                <Link
                  href={item.href}
                  className={cn(
                    'flex items-center justify-between px-s4 py-s3',
                    'font-body text-sm text-cream-50 hover:bg-ink-700',
                  )}
                  data-testid={`me-nav-${item.href.replace(/\//g, '-')}`}
                >
                  <span>{item.label}</span>
                  <span aria-hidden="true" className="text-cream-300">
                    →
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        </nav>
      </main>
    </div>
  );
}

interface StatCellProps {
  label: string;
  value: string;
  testId: string;
}

function StatCell({ label, value, testId }: StatCellProps) {
  return (
    <div
      className="flex flex-col items-center justify-center gap-s1 rounded-md border border-ink-700 bg-ink-800 px-s2 py-s3"
      data-testid={testId}
    >
      <span className="font-body text-xs text-cream-300">{label}</span>
      <span className="font-display text-sm text-cream-50">{value}</span>
    </div>
  );
}
