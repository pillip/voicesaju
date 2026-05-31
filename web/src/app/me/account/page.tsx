'use client';

/**
 * /me/account — Screen 19/20 (ISSUE-072 NFR-005).
 *
 * Two destructive actions:
 * - "로그아웃" → POST /api/v1/auth/logout, then router.replace('/').
 * - "회원 탈퇴" → confirm modal → POST /api/v1/users/me/delete →
 *   router.replace('/').
 *
 * The frontend trusts the backend to clear the vs_sess cookie; we
 * still redirect to '/' so a stale tab state can't keep the user on
 * an authenticated page.
 */

import { useRouter } from 'next/navigation';
import { useState } from 'react';

export default function AccountPage() {
  const router = useRouter();
  const [showConfirm, setShowConfirm] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function handleLogout() {
    setBusy(true);
    setErr(null);
    try {
      await fetch('/api/v1/auth/logout', { method: 'POST', credentials: 'include' });
      router.replace('/');
    } catch {
      setErr('잠시 후 다시 시도해주세요.');
    } finally {
      setBusy(false);
    }
  }

  async function handleDelete() {
    setBusy(true);
    setErr(null);
    try {
      const resp = await fetch('/api/v1/users/me/delete', {
        method: 'POST',
        credentials: 'include',
      });
      if (!resp.ok) {
        setErr('탈퇴 처리에 실패했어요. 잠시 후 다시 시도해주세요.');
        return;
      }
      router.replace('/');
    } catch {
      setErr('잠시 후 다시 시도해주세요.');
    } finally {
      setBusy(false);
      setShowConfirm(false);
    }
  }

  return (
    <main className="mx-auto max-w-md px-4 py-8" data-testid="account-page">
      <h1 className="mb-6 font-display text-2xl">계정 설정</h1>

      <button
        type="button"
        onClick={handleLogout}
        disabled={busy}
        data-testid="logout-button"
        className="mb-4 w-full rounded-md border border-cream-300 px-4 py-3 text-base"
      >
        로그아웃
      </button>

      <button
        type="button"
        onClick={() => setShowConfirm(true)}
        disabled={busy}
        data-testid="delete-button"
        className="w-full rounded-md border border-rose-400 px-4 py-3 text-base text-rose-500"
      >
        회원 탈퇴
      </button>

      {err && (
        <p role="alert" data-testid="account-error" className="mt-4 text-sm text-rose-400">
          {err}
        </p>
      )}

      {showConfirm && (
        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby="confirm-title"
          data-testid="delete-confirm"
          className="fixed inset-0 z-50 flex items-center justify-center bg-ink-900/70 px-4"
        >
          <div className="w-full max-w-sm rounded-lg bg-cream-50 p-6 text-ink-900">
            <h2 id="confirm-title" className="mb-2 font-display text-lg">
              정말 탈퇴할까?
            </h2>
            <p className="mb-6 text-sm">
              30일 안에 같은 계정으로 다시 로그인하면 복구할 수 있어.
            </p>
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => setShowConfirm(false)}
                disabled={busy}
                data-testid="cancel-delete"
                className="flex-1 rounded-md border border-ink-300 px-4 py-2"
              >
                취소
              </button>
              <button
                type="button"
                onClick={handleDelete}
                disabled={busy}
                data-testid="confirm-delete"
                className="flex-1 rounded-md bg-rose-500 px-4 py-2 text-cream-50"
              >
                탈퇴
              </button>
            </div>
          </div>
        </div>
      )}
    </main>
  );
}
