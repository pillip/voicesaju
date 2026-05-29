'use client';

import { useRuntimeContext } from '@/lib/context/runtime-context';
import { Banner } from '@/components/ui/Banner';
import { BottomSheet } from '@/components/ui/BottomSheet';
import { cn } from '@/lib/utils';

export interface SignupPromptModalProps {
  /** Sheet visibility. */
  open: boolean;
  /** Called when the user dismisses (backdrop / swipe / "나중에 할게" / ESC). */
  onClose: () => void;
  /**
   * When `true`, render the cancellation banner inside the modal and keep
   * the provider buttons clickable so the user can retry (Screen 25 error
   * state). The banner copy is the same Korean string used by the
   * `/auth/login` page so the experience is consistent across surfaces.
   */
  error?: boolean;
  /**
   * When `true`, mark the provider anchors as `aria-busy` + `aria-disabled`
   * so screen readers announce the OAuth redirect in progress. We do NOT
   * remove the `href` — the anchor is still the canonical way for the
   * browser to navigate, and we want progressive-enhancement behaviour
   * (the redirect happens even if JS is slow to update local state).
   */
  loading?: boolean;
  /** Override panel className (forwarded to {@link BottomSheet}). */
  className?: string;
}

/**
 * Screen 25 — bottom-sheet signup prompt invoked from non-member flows.
 *
 * Architecture-Ref: `docs/ux_spec.md` §4 Screen 25.
 * PRD-Ref: FR-003 (1-second signup conversion), US-02 (non-member flow).
 * Depends on: ISSUE-022 (BottomSheet primitive), ISSUE-023 (runtime channel),
 * ISSUE-026 (`/api/v1/auth/{provider}/start` routes).
 *
 * Channel matrix (per ISSUE-023 / FR-024):
 * - `web`         → Kakao + Apple anchors (provider OAuth start).
 * - `toss_webview`→ single "토스로 계속하기" anchor.
 *   The Toss start endpoint (`/api/v1/auth/toss/start`) is delivered by a
 *   later issue in the same pipeline (Toss auth bridge); the anchor is
 *   already wired so the moment the route lands the modal works end-to-end
 *   without a frontend change.
 *
 * Why anchors (not buttons):
 * - Accessibility: a real `<a href>` is announced as a link and lets users
 *   middle-click / cmd-click / open-in-new-tab.
 * - Progressive enhancement: the OAuth flow is server-rendered; the page
 *   reloads on tap, so a real navigation matches the mental model.
 */
export function SignupPromptModal({
  open,
  onClose,
  error,
  loading,
  className,
}: SignupPromptModalProps) {
  const { channel } = useRuntimeContext();
  const isToss = channel === 'toss_webview';

  return (
    <BottomSheet
      open={open}
      onClose={onClose}
      title="결과 저장하려면 1초 가입"
      className={className}
    >
      <p className="mb-s4 font-body text-sm text-cream-200">
        지금 들은 풀이를 마이페이지에 영구 저장해드려요.
      </p>

      {error && (
        <div className="mb-s4">
          <Banner tone="error">로그인이 취소됐어요</Banner>
        </div>
      )}

      <div className="flex flex-col gap-s2">
        {isToss ? (
          <ProviderAnchor
            href="/api/v1/auth/toss/start"
            label="토스로 계속하기"
            loading={loading}
            tone="primary"
          />
        ) : (
          <>
            <ProviderAnchor
              href="/api/v1/auth/kakao/start"
              label="카카오로 시작하기"
              loading={loading}
              tone="primary"
            />
            <ProviderAnchor
              href="/api/v1/auth/apple/start"
              label="Apple로 시작하기"
              loading={loading}
              tone="secondary"
            />
          </>
        )}

        <button
          type="button"
          onClick={onClose}
          className={cn(
            'mt-s2 self-center font-body text-sm text-cream-300 underline decoration-cream-500 underline-offset-4 transition-colors',
            'hover:text-amber-300 hover:decoration-amber-300',
            'focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-amber-300',
          )}
        >
          나중에 할게
        </button>
      </div>
    </BottomSheet>
  );
}

interface ProviderAnchorProps {
  href: string;
  label: string;
  loading?: boolean;
  tone: 'primary' | 'secondary';
}

/**
 * Anchor styled like a primary / secondary CTA button. We hand-roll the
 * styling instead of wrapping {@link PrimaryButton} so the element stays a
 * real `<a>` (preserving link semantics + middle-click behaviour) while
 * still tracking the design-system tokens used elsewhere on Screen 25.
 */
function ProviderAnchor({ href, label, loading, tone }: ProviderAnchorProps) {
  const isPrimary = tone === 'primary';
  return (
    <a
      href={href}
      aria-busy={loading || undefined}
      aria-disabled={loading || undefined}
      className={cn(
        'inline-flex w-full items-center justify-center gap-s2 rounded-md px-s4 py-s3 font-body text-base font-medium',
        'transition-colors',
        'focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-amber-300',
        isPrimary
          ? 'bg-amber-400 text-ink-900 hover:bg-amber-300 active:bg-amber-500'
          : 'border border-cream-300 bg-transparent text-cream-100 hover:bg-ink-700 active:bg-ink-600',
        loading && 'cursor-wait opacity-70',
      )}
    >
      {loading && (
        <span
          aria-hidden="true"
          className={cn(
            'inline-block h-s3 w-s3 animate-spin rounded-pill border-2 border-t-transparent',
            isPrimary ? 'border-ink-900' : 'border-cream-100',
          )}
        />
      )}
      {label}
    </a>
  );
}
