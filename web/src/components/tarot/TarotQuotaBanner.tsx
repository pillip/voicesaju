"use client";

/**
 * `<TarotQuotaBanner>` — Screen 12 top banner (ISSUE-050).
 *
 * Renders one of three copy variants per `docs/copy_guide.md` §10:
 *   - default (free_remaining > 0) → "이번 주 무료 N회 남음"
 *   - 소진     (free_remaining = 0) → "이번 주 무료 다 봤음"
 *   - 구독자   (unlimited = true)   → "매일 한 장, 무제한."
 *
 * The Phase-1 backend collapses `free_remaining` to 0 or 1 today
 * (weekly free quota), but we keep the N parameter in case the spec
 * grows. The page is the single caller — we don't ship from inside
 * here so we can stay narrow.
 *
 * Styling: leans on the shared `<Banner>` primitive with the `info` tone
 * for the default + subscriber variants and the `warning` tone for the
 * 소진 state (so it stands out against the face-down hero).
 */
import { Banner } from "@/components/ui/Banner";

export interface TarotQuotaBannerProps {
  freeRemaining: number;
  unlimited: boolean;
}

export function TarotQuotaBanner({
  freeRemaining,
  unlimited,
}: TarotQuotaBannerProps) {
  if (unlimited) {
    // Subscribers — copy_guide.md §10 "Edge: 구독자".
    return <Banner tone="info">매일 한 장, 무제한.</Banner>;
  }
  if (freeRemaining <= 0) {
    // 소진 — copy_guide.md §10 "Top right banner (소진)".
    return <Banner tone="warning">이번 주 무료 다 봤음</Banner>;
  }
  // Default — copy_guide.md §10 "Top right banner (default)".
  return <Banner tone="info">{`이번 주 무료 ${freeRemaining}회 남음`}</Banner>;
}
