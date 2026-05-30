/**
 * Unit tests for `<TarotQuotaBanner>` (ISSUE-050, Screen 12 top slot).
 *
 * Copy source: `docs/copy_guide.md` §10:
 *   - default → "이번 주 무료 1회 남음" (free_remaining > 0, not subscriber)
 *   - 소진    → "이번 주 무료 다 봤음" (free_remaining = 0, not subscriber)
 *   - 구독자  → "매일 한 장, 무제한." (banner hidden in spec, but the
 *               component still renders the subscriber caption when the
 *               page passes `unlimited=true` so it works as a stand-in
 *               for the subscription badge slot).
 *
 * We test only the visible string for each variant — the styling is
 * delegated to the shared `<Banner>` primitive (covered by its own tests).
 */
import { describe, expect, it, afterEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import { TarotQuotaBanner } from "@/components/tarot/TarotQuotaBanner";

afterEach(() => {
  cleanup();
});

describe("<TarotQuotaBanner>", () => {
  it("renders the default 1회 남음 copy when quota remains", () => {
    render(<TarotQuotaBanner freeRemaining={1} unlimited={false} />);
    expect(screen.getByText("이번 주 무료 1회 남음")).toBeInTheDocument();
  });

  it("renders the 다 봤음 copy when free_remaining is 0", () => {
    render(<TarotQuotaBanner freeRemaining={0} unlimited={false} />);
    expect(screen.getByText("이번 주 무료 다 봤음")).toBeInTheDocument();
  });

  it("renders the subscriber caption when unlimited is true", () => {
    render(<TarotQuotaBanner freeRemaining={1} unlimited />);
    expect(screen.getByText("매일 한 장, 무제한.")).toBeInTheDocument();
  });

  // ISSUE-052 — the new prop name. Backend now emits `is_subscriber`
  // so the page passes `isSubscriber` instead of inferring it from a
  // ``unlimited`` boolean.
  it("renders the subscriber caption when isSubscriber is true", () => {
    render(<TarotQuotaBanner freeRemaining={null} isSubscriber />);
    expect(screen.getByText("매일 한 장, 무제한.")).toBeInTheDocument();
  });

  it("isSubscriber wins over freeRemaining number (ISSUE-052)", () => {
    // Even when an integer counter is passed, the subscriber flag
    // forces the subscriber variant. This guards against accidental
    // leakage of the integer from a stale cache during the bypass.
    render(<TarotQuotaBanner freeRemaining={0} isSubscriber />);
    expect(screen.getByText("매일 한 장, 무제한.")).toBeInTheDocument();
    expect(screen.queryByText("이번 주 무료 다 봤음")).not.toBeInTheDocument();
  });
});
