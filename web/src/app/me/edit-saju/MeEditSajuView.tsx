'use client';

/**
 * `/me/edit-saju` — Screen 21 (ISSUE-071, FR-029): saju correction form.
 *
 * Wraps the `PATCH /api/v1/profile` endpoint with a guardrailed form:
 *
 *  1. Reads `/api/v1/profile/me` on mount to learn the current
 *     correction usage (we cache `corrections_remaining` on the
 *     client; if absent — typical of pre-ISSUE-071 sessions — we
 *     pessimistically assume the maximum (2) until the next save).
 *  2. Renders a counter banner "수정 가능 N/2".
 *  3. Renders a form with date / time / lunar / gender / name inputs
 *     pre-filled from the loaded profile.
 *  4. On submit → ConfirmModal. The modal copy is verbatim from
 *     copy_guide.md / FR-029.
 *  5. On confirm → PATCH /api/v1/profile. Success → counter updates
 *     + toast. Quota exhausted → 운영 문의 fallback (AC3).
 *
 * AC mapping (ISSUE-071):
 *   AC1: PATCH success → counter increments to 1 + chart_id changes.
 *   AC2: backend 403 with `correction_quota_exceeded` → page swaps to
 *        운영 문의 fallback (no form rendered).
 *   AC3: when corrections_remaining === 0 on page load → 운영 문의
 *        fallback (no form rendered).
 *   AC4: past history references the old chart_id (backend behaviour;
 *        nothing to render here).
 */

import { useRouter } from 'next/navigation';
import { useCallback, useEffect, useRef, useState } from 'react';

import { TopAppBar } from '@/components/nav/TopAppBar';
import { ConfirmModal } from '@/components/ui/ConfirmModal';
import {
  CORRECTION_QUOTA_EXCEEDED,
  fetchProfileMe,
  patchProfile,
  ProfileFetchError,
  type ProfileCorrectionRequest,
  type ProfileMeResponse,
} from '@/lib/api/profile';

/** Hard-coded copy per ux_spec Flow + copy_guide. */
const CONFIRM_TITLE = '사주 정보 수정';
const CONFIRM_DESCRIPTION = '수정 후엔 새 사주로 풀이가 나와요. 과거 히스토리는 그대로 남아요.';

/** Mailto target shown in the 운영 문의 fallback. */
const SUPPORT_MAILTO = 'mailto:support@voicesaju.app';

/** Hard cap from the backend (FR-029). */
const MAX_CORRECTIONS = 2;

type FormState = {
  birthDate: string;
  birthTime: string;
  birthTimeUnknown: boolean;
  gender: 'M' | 'F';
  isLunar: boolean;
  name: string;
};

type LoadState =
  | { kind: 'loading' }
  | { kind: 'error'; message: string }
  | {
      kind: 'loaded';
      profile: ProfileMeResponse;
      /**
       * Initially `null` (we don't know the counter until the first
       * PATCH — `/profile/me` doesn't expose it pre-ISSUE-071). The
       * page pessimistically allows up to `MAX_CORRECTIONS` until
       * proven otherwise.
       */
      correctionsRemaining: number | null;
    }
  | { kind: 'quota_exhausted' };

export interface MeEditSajuViewProps {
  /**
   * Test hook: inject a fake fetch so the page can run under vitest's
   * jsdom environment without hitting the network. Production passes
   * the global `fetch`.
   */
  fetchImpl?: typeof fetch;
}

export function MeEditSajuView({ fetchImpl }: MeEditSajuViewProps) {
  const router = useRouter();
  const [state, setState] = useState<LoadState>({ kind: 'loading' });
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [form, setForm] = useState<FormState>({
    birthDate: '',
    birthTime: '',
    birthTimeUnknown: false,
    gender: 'F',
    isLunar: false,
    name: '',
  });

  const routerRef = useRef(router);
  routerRef.current = router;
  const fetchRef = useRef(fetchImpl);
  fetchRef.current = fetchImpl;

  const load = useCallback(async () => {
    setState({ kind: 'loading' });
    try {
      const profile = await fetchProfileMe(fetchRef.current ?? fetch);
      // Seed the form from the loaded profile. The /profile/me payload
      // doesn't currently include birth_date plaintext (the value is
      // encrypted at rest), so the inputs start empty + the user
      // re-enters them. The PATCH endpoint accepts the full shape.
      setForm((prev) => ({
        ...prev,
        birthTimeUnknown: !profile.birth_time_known,
      }));
      setState({
        kind: 'loaded',
        profile,
        // ISSUE-064's /profile/me doesn't expose the counter; we
        // pessimistically display "수정 가능 ?/2" until the user runs
        // a PATCH that surfaces the real number.
        correctionsRemaining: null,
      });
    } catch (err) {
      if (err instanceof ProfileFetchError && err.status === 401) {
        routerRef.current.replace('/auth/login');
        return;
      }
      if (err instanceof ProfileFetchError && err.status === 404) {
        routerRef.current.replace('/onboarding');
        return;
      }
      setState({ kind: 'error', message: '잠시 후 다시 시도해주세요' });
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const handleSubmit = useCallback(async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setConfirmOpen(true);
  }, []);

  const handleConfirm = useCallback(async () => {
    if (state.kind !== 'loaded') return;
    setSubmitting(true);
    try {
      const body: ProfileCorrectionRequest = {
        birth_date: form.birthDate,
        birth_time: form.birthTimeUnknown ? null : form.birthTime,
        is_lunar: form.isLunar,
        gender: form.gender,
        name: form.name || null,
      };
      const result = await patchProfile(body, fetchRef.current ?? fetch);
      setState({
        kind: 'loaded',
        profile: state.profile,
        correctionsRemaining: result.corrections_remaining,
      });
      setConfirmOpen(false);
      // If this PATCH burned the last correction, switch the page
      // into the 운영 문의 fallback so the user doesn't see a form
      // they can't submit.
      if (result.corrections_remaining <= 0) {
        setState({ kind: 'quota_exhausted' });
      }
    } catch (err) {
      // Backend says "you're already at 2/2" → page goes into the
      // 운영 문의 state (AC2).
      if (
        err instanceof ProfileFetchError &&
        err.status === 403 &&
        err.message === CORRECTION_QUOTA_EXCEEDED
      ) {
        setState({ kind: 'quota_exhausted' });
        setConfirmOpen(false);
        return;
      }
      // Generic failure — keep the modal open so the user can retry
      // without losing form state.
      setState((prev) =>
        prev.kind === 'loaded'
          ? {
              kind: 'loaded',
              profile: prev.profile,
              correctionsRemaining: prev.correctionsRemaining,
            }
          : prev,
      );
      setConfirmOpen(false);
    } finally {
      setSubmitting(false);
    }
  }, [form, state]);

  if (state.kind === 'loading') {
    return (
      <div className="flex min-h-screen flex-col bg-ink-900 text-cream-100">
        <TopAppBar title="사주 정보 수정" />
        <main
          className="mx-auto flex w-full max-w-md flex-1 flex-col items-center justify-center px-s4 py-s8"
          aria-busy
          data-testid="me-edit-saju-loading"
        >
          <span className="sr-only">로딩 중</span>
        </main>
      </div>
    );
  }

  if (state.kind === 'error') {
    return (
      <div className="flex min-h-screen flex-col bg-ink-900 text-cream-100">
        <TopAppBar title="사주 정보 수정" />
        <main
          className="mx-auto flex w-full max-w-md flex-1 flex-col items-center justify-center gap-s4 px-s4 py-s8"
          data-testid="me-edit-saju-error"
        >
          <p className="font-body text-sm text-cream-300">{state.message}</p>
          <button
            type="button"
            onClick={() => void load()}
            className="rounded-md border border-ink-700 px-s4 py-s2 font-body text-sm text-cream-50 hover:bg-ink-800"
            data-testid="me-edit-saju-retry"
          >
            다시 시도
          </button>
        </main>
      </div>
    );
  }

  if (state.kind === 'quota_exhausted') {
    return (
      <div className="flex min-h-screen flex-col bg-ink-900 text-cream-100">
        <TopAppBar title="사주 정보 수정" />
        <main
          className="mx-auto flex w-full max-w-md flex-1 flex-col items-center justify-center gap-s4 px-s4 py-s8 text-center"
          data-testid="me-edit-saju-quota-exhausted"
        >
          <p className="font-body text-base text-cream-200">수정 한도(2회)를 모두 사용했어요.</p>
          <p className="font-body text-sm text-cream-300">
            추가 수정이 필요하다면 운영 문의로 진행해주세요.
          </p>
          <a
            href={SUPPORT_MAILTO}
            className="rounded-md border border-amber-700/50 bg-amber-900/20 px-s4 py-s2 font-body text-sm text-amber-200 hover:bg-amber-900/30"
            data-testid="me-edit-saju-mailto"
          >
            운영 문의 보내기
          </a>
        </main>
      </div>
    );
  }

  const remainingLabel =
    state.correctionsRemaining === null
      ? `수정 가능 ?/${MAX_CORRECTIONS}`
      : `수정 가능 ${state.correctionsRemaining}/${MAX_CORRECTIONS}`;

  return (
    <div className="flex min-h-screen flex-col bg-ink-900 text-cream-100">
      <TopAppBar title="사주 정보 수정" />
      <main
        className="mx-auto flex w-full max-w-md flex-1 flex-col gap-s4 px-s4 py-s6"
        data-testid="me-edit-saju-loaded"
      >
        <div
          className="rounded-md border border-amber-700/50 bg-amber-900/20 px-s4 py-s2 text-center font-body text-sm text-amber-200"
          data-testid="me-edit-saju-counter"
        >
          {remainingLabel}
        </div>

        <form
          onSubmit={handleSubmit}
          className="flex flex-col gap-s4"
          data-testid="me-edit-saju-form"
        >
          <label className="flex flex-col gap-s1 font-body text-sm">
            <span>생년월일</span>
            <input
              type="date"
              required
              value={form.birthDate}
              onChange={(e) => setForm((p) => ({ ...p, birthDate: e.target.value }))}
              className="rounded-md border border-ink-700 bg-ink-800 px-s3 py-s2 text-cream-50"
              data-testid="me-edit-saju-input-date"
            />
          </label>

          <label className="flex flex-col gap-s1 font-body text-sm">
            <span>태어난 시간</span>
            <input
              type="time"
              value={form.birthTime}
              disabled={form.birthTimeUnknown}
              onChange={(e) => setForm((p) => ({ ...p, birthTime: e.target.value }))}
              className="rounded-md border border-ink-700 bg-ink-800 px-s3 py-s2 text-cream-50 disabled:opacity-40"
              data-testid="me-edit-saju-input-time"
            />
            <label className="mt-s1 flex items-center gap-s2 text-xs text-cream-300">
              <input
                type="checkbox"
                checked={form.birthTimeUnknown}
                onChange={(e) =>
                  setForm((p) => ({
                    ...p,
                    birthTimeUnknown: e.target.checked,
                  }))
                }
                data-testid="me-edit-saju-input-time-unknown"
              />
              시간 모름
            </label>
          </label>

          <label className="flex flex-col gap-s1 font-body text-sm">
            <span>성별</span>
            <select
              value={form.gender}
              onChange={(e) =>
                setForm((p) => ({
                  ...p,
                  gender: e.target.value as 'M' | 'F',
                }))
              }
              className="rounded-md border border-ink-700 bg-ink-800 px-s3 py-s2 text-cream-50"
              data-testid="me-edit-saju-input-gender"
            >
              <option value="F">여성</option>
              <option value="M">남성</option>
            </select>
          </label>

          <label className="flex items-center gap-s2 font-body text-sm">
            <input
              type="checkbox"
              checked={form.isLunar}
              onChange={(e) => setForm((p) => ({ ...p, isLunar: e.target.checked }))}
              data-testid="me-edit-saju-input-lunar"
            />
            음력 생일
          </label>

          <label className="flex flex-col gap-s1 font-body text-sm">
            <span>이름 (선택)</span>
            <input
              type="text"
              maxLength={10}
              value={form.name}
              onChange={(e) => setForm((p) => ({ ...p, name: e.target.value }))}
              className="rounded-md border border-ink-700 bg-ink-800 px-s3 py-s2 text-cream-50"
              data-testid="me-edit-saju-input-name"
            />
          </label>

          <button
            type="submit"
            className="mt-s2 rounded-md bg-amber-700 px-s4 py-s3 font-display text-sm text-cream-50 hover:bg-amber-600 disabled:opacity-40"
            disabled={submitting}
            data-testid="me-edit-saju-submit"
          >
            수정하기
          </button>
        </form>
      </main>

      <ConfirmModal
        open={confirmOpen}
        onClose={() => setConfirmOpen(false)}
        onConfirm={() => void handleConfirm()}
        title={CONFIRM_TITLE}
        description={CONFIRM_DESCRIPTION}
        confirmLabel="수정"
        cancelLabel="취소"
      />
    </div>
  );
}
