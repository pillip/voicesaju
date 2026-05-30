/**
 * Unit tests for `/reading/category` (ISSUE-030, Screen 6).
 *
 * AC mapping:
 *   AC1: 3 cards display with category-specific colors when onboarding done.
 *   AC2: Tap card → router.push("/reading/intro/[category]").
 *   AC3: Subscriber → bottom bar "구독 중 — 이번 달 사주 X/1회 남음".
 *   AC4: Non-member → greeting uses "거기 너".
 *
 * The `useSearchParams` mock returns an explicit URLSearchParams instance so
 * each test can drive a specific entitlement state via the same channel the
 * production page does (the `?entitlement=` query param).
 */
import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, act, fireEvent } from "@testing-library/react";
import { useOnboardingStore } from "@/lib/stores/onboarding-store";

const pushMock = vi.fn();
let searchParams = new URLSearchParams();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: pushMock, back: vi.fn() }),
  useSearchParams: () => searchParams,
}));

import CategoryPage from "@/app/reading/category/page";

function setEntitlement(kind: string | null) {
  searchParams = new URLSearchParams(kind ? { entitlement: kind } : undefined);
}

describe("/reading/category — Screen 6 (ISSUE-030)", () => {
  beforeEach(() => {
    pushMock.mockReset();
    useOnboardingStore.getState().reset();
    setEntitlement(null);
  });

  it("AC1: renders all 3 saju category cards (연애/직장/금전) with token colors", async () => {
    useOnboardingStore.getState().setName("효주");
    await act(async () => {
      render(<CategoryPage />);
    });
    const love = screen.getByTestId("category-card-love");
    const work = screen.getByTestId("category-card-work");
    const money = screen.getByTestId("category-card-money");
    expect(love.className).toMatch(/bg-category-love/);
    expect(work.className).toMatch(/bg-category-work/);
    expect(money.className).toMatch(/bg-category-money/);
  });

  it("does NOT render the 타로 card on this screen (saju-only fork)", async () => {
    await act(async () => {
      render(<CategoryPage />);
    });
    expect(screen.queryByTestId("category-card-tarot")).not.toBeInTheDocument();
  });

  it("AC2: tapping the love card pushes to /reading/intro/love", async () => {
    await act(async () => {
      render(<CategoryPage />);
    });
    await act(async () => {
      fireEvent.click(screen.getByTestId("category-card-love"));
    });
    expect(pushMock).toHaveBeenCalledWith("/reading/intro/love");
  });

  it("AC2: tapping each card routes to the matching intro slug", async () => {
    await act(async () => {
      render(<CategoryPage />);
    });
    for (const key of ["love", "work", "money"] as const) {
      pushMock.mockReset();
      await act(async () => {
        fireEvent.click(screen.getByTestId(`category-card-${key}`));
      });
      expect(pushMock).toHaveBeenCalledWith(`/reading/intro/${key}`);
    }
  });

  it('AC4: non-member (no name in store) greeting addresses "거기 너"', async () => {
    // Default store state has name = "" → non-member branch.
    await act(async () => {
      render(<CategoryPage />);
    });
    expect(screen.getByTestId("greeting").textContent).toContain("거기 너");
  });

  it('AC4: empty/whitespace-only name in store still resolves to "거기 너"', async () => {
    useOnboardingStore.getState().setName("   ");
    await act(async () => {
      render(<CategoryPage />);
    });
    expect(screen.getByTestId("greeting").textContent).toContain("거기 너");
  });

  it("member greeting uses the stored name verbatim", async () => {
    useOnboardingStore.getState().setName("효주");
    await act(async () => {
      render(<CategoryPage />);
    });
    expect(screen.getByTestId("greeting").textContent).toContain("효주");
    expect(screen.getByTestId("greeting").textContent).not.toContain("거기 너");
  });

  it('renders "단건 결제 필요" entitlement banner for the non-member default', async () => {
    await act(async () => {
      render(<CategoryPage />);
    });
    expect(screen.getByTestId("entitlement-banner").textContent).toContain(
      "단건 결제 필요",
    );
  });

  it('renders "무료 토큰 1회" banner when ?entitlement=free_token', async () => {
    setEntitlement("free_token");
    await act(async () => {
      render(<CategoryPage />);
    });
    expect(screen.getByTestId("entitlement-banner").textContent).toContain(
      "무료 토큰 1회",
    );
  });

  it('renders "단건 결제 필요" banner when ?entitlement=payment', async () => {
    setEntitlement("payment");
    await act(async () => {
      render(<CategoryPage />);
    });
    expect(screen.getByTestId("entitlement-banner").textContent).toContain(
      "단건 결제 필요",
    );
  });

  it("AC3: subscriber state renders the sticky bottom bar with monthly counter", async () => {
    setEntitlement("subscription");
    await act(async () => {
      render(<CategoryPage />);
    });
    const bar = screen.getByTestId("subscriber-bottom-bar");
    expect(bar).toBeInTheDocument();
    expect(bar.textContent).toContain("구독 중 — 이번 달 사주 1/1회 남음");
  });

  it("non-subscriber states do NOT render the subscriber bottom bar", async () => {
    for (const kind of ["none", "free_token", "payment"] as const) {
      setEntitlement(kind);
      const { unmount } = render(<CategoryPage />);
      expect(
        screen.queryByTestId("subscriber-bottom-bar"),
      ).not.toBeInTheDocument();
      unmount();
    }
  });
});
