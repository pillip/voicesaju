"use client";

/**
 * `<TarotQuotaBanner>` — Screen 12 top banner (ISSUE-050, ISSUE-052).
 *
 * Renders one of three copy variants per `docs/copy_guide.md` §10:
 *   - default (free_remaining > 0) → "이번 주 무료 N회 남음"
 *   - 소진     (free_remaining = 0) → "이번 주 무료 다 봤음"
 *   - 구독자   (isSubscriber=true)  → "매일 한 장, 무제한."
 *
 * The Phase-1 backend collapses `free_remaining` to 0 or 1 today
 * (weekly free quota), but we keep the N parameter in case the spec
 * grows. The page is the single caller — we don't ship from inside
 * here so we can stay narrow.
 *
 * ISSUE-052 evolution: the subscriber path now uses an explicit
 * `isSubscriber` prop (driven by the backend `is_subscriber` flag from
 * `GET /api/v1/tarot/today`). The legacy `unlimited` prop is retained
 * as an alias so existing call-sites (ISSUE-050's `/tarot` page before
 * this update) keep compiling — either flag toggles the subscriber
 * variant. When `isSubscriber` is true the page passes
 * `freeRemaining: null` so we treat it as "subscriber regardless of
 * quota" without forcing the caller to invent a placeholder number.
 *
 * Styling: leans on the shared `<Banner>` primitive with the `info` tone
 * for the default + subscriber variants and the `warning` tone for the
 * 소진 state (so it stands out against the face-down hero).
 */
import { Banner } from "@/components/ui/Banner";

export interface TarotQuotaBannerProps {
  /**
   * Weekly free draws left. `null` is allowed — it means the caller is
   * a subscriber and the counter is N/A. Otherwise pass an integer.
   */
  freeRemaining: number | null;
  /**
   * ISSUE-052 — true when an active subscription grants the unlimited
   * tarot bypass (FR-022). Wins over `freeRemaining` and `unlimited`.
   */
  isSubscriber?: boolean;
  /**
   * Legacy alias for `isSubscriber`, kept for backward compatibility
   * with ISSUE-050 callers that hadn't migrated yet. New call-sites
   * should prefer `isSubscriber`.
   */
  unlimited?: boolean;
}

export function TarotQuotaBanner({
  freeRemaining,
  isSubscriber,
  unlimited,
}: TarotQuotaBannerProps) {
  // Either flag promotes the caller to the subscriber variant. We
  // collapse them here so call-sites don't have to know which lever the
  // backend wired up first.
  if (isSubscriber || unlimited) {
    // Subscribers — copy_guide.md §10 "Edge: 구독자".
    return <Banner tone="info">매일 한 장, 무제한.</Banner>;
  }
  // For non-subscribers we expect a numeric counter. `null` here is a
  // misuse (the caller forgot to set `isSubscriber`) — coerce to 0 so
  // the user still sees a sane "다 봤음" message instead of a runtime
  // error.
  const remaining = freeRemaining ?? 0;
  if (remaining <= 0) {
    // 소진 — copy_guide.md §10 "Top right banner (소진)".
    return <Banner tone="warning">이번 주 무료 다 봤음</Banner>;
  }
  // Default — copy_guide.md §10 "Top right banner (default)".
  return <Banner tone="info">{`이번 주 무료 ${remaining}회 남음`}</Banner>;
}
