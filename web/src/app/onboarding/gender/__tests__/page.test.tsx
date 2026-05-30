/**
 * Unit tests for `/onboarding/gender` (ISSUE-028, Screen 4).
 *
 * AC mapping (the AC list doesn't enumerate gender specifically — covers
 * ux_spec Screen 4 behaviour: tap a card → persist → auto-advance to /name).
 */
import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, act, fireEvent } from "@testing-library/react";
import { useOnboardingStore } from "@/lib/stores/onboarding-store";

const pushMock = vi.fn();
const backMock = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: pushMock, back: backMock }),
  useSearchParams: () => new URLSearchParams(),
}));

import GenderPage from "@/app/onboarding/gender/page";

describe("/onboarding/gender — Screen 4 (ISSUE-028)", () => {
  beforeEach(() => {
    pushMock.mockReset();
    backMock.mockReset();
    useOnboardingStore.getState().reset();
  });

  it("renders the page heading from copy_guide §3.5a", async () => {
    await act(async () => {
      render(<GenderPage />);
    });
    expect(
      screen.getByRole("heading", {
        level: 1,
        name: /(성별|성별이 어떻게 돼\?)/,
      }),
    ).toBeInTheDocument();
  });

  it("renders step indicator at 3/4", async () => {
    await act(async () => {
      render(<GenderPage />);
    });
    expect(screen.getByRole("list", { name: "3 / 4" })).toBeInTheDocument();
  });

  it("renders 여자 and 남자 option cards", async () => {
    await act(async () => {
      render(<GenderPage />);
    });
    expect(
      screen.getByRole("radio", { name: /(여자|여)/ }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("radio", { name: /(남자|남)/ }),
    ).toBeInTheDocument();
  });

  it("tapping 여자 persists gender=female and routes to /onboarding/name", async () => {
    await act(async () => {
      render(<GenderPage />);
    });
    await act(async () => {
      fireEvent.click(screen.getByRole("radio", { name: /(여자|여)/ }));
    });
    expect(useOnboardingStore.getState().gender).toBe("female");
    expect(pushMock).toHaveBeenCalledWith("/onboarding/name");
  });

  it("tapping 남자 persists gender=male and routes to /onboarding/name", async () => {
    await act(async () => {
      render(<GenderPage />);
    });
    await act(async () => {
      fireEvent.click(screen.getByRole("radio", { name: /(남자|남)/ }));
    });
    expect(useOnboardingStore.getState().gender).toBe("male");
    expect(pushMock).toHaveBeenCalledWith("/onboarding/name");
  });

  it("shows previously selected gender as aria-checked when revisiting", async () => {
    useOnboardingStore.getState().setGender("female");
    await act(async () => {
      render(<GenderPage />);
    });
    expect(screen.getByRole("radio", { name: /(여자|여)/ })).toHaveAttribute(
      "aria-checked",
      "true",
    );
    expect(screen.getByRole("radio", { name: /(남자|남)/ })).toHaveAttribute(
      "aria-checked",
      "false",
    );
  });

  it("renders a back button that triggers router back", async () => {
    await act(async () => {
      render(<GenderPage />);
    });
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /뒤로/ }));
    });
    expect(backMock).toHaveBeenCalled();
  });
});
