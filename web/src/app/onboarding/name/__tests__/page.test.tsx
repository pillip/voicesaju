/**
 * Unit tests for `/onboarding/name` (ISSUE-028, Screen 5, AC4).
 *
 * AC mapping:
 * - AC4: name > 10 chars → inline error "이름은 10자 이내로 적어줘".
 * - Auxiliary: 건너뛰기 skips name and routes to /reading/category.
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

import NamePage from "@/app/onboarding/name/page";

describe("/onboarding/name — Screen 5 (ISSUE-028)", () => {
  beforeEach(() => {
    pushMock.mockReset();
    backMock.mockReset();
    useOnboardingStore.getState().reset();
  });

  it("renders the page heading from copy_guide §3.5b", async () => {
    await act(async () => {
      render(<NamePage />);
    });
    expect(
      screen.getByRole("heading", { level: 1, name: /(이름|이름 알려주면)/ }),
    ).toBeInTheDocument();
  });

  it("renders step indicator at 4/4", async () => {
    await act(async () => {
      render(<NamePage />);
    });
    expect(screen.getByRole("list", { name: "4 / 4" })).toBeInTheDocument();
  });

  it("renders the name input and both 완료 + 건너뛰기 buttons", async () => {
    await act(async () => {
      render(<NamePage />);
    });
    expect(screen.getByLabelText("이름 (옵셔널)")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /완료|이름 없이 계속하기/ }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "건너뛰기" }),
    ).toBeInTheDocument();
  });

  it('AC4: name > 10 chars renders inline error "이름은 10자 이내로 적어줘"', async () => {
    await act(async () => {
      render(<NamePage />);
    });
    const input = screen.getByLabelText("이름 (옵셔널)") as HTMLInputElement;
    await act(async () => {
      fireEvent.change(input, { target: { value: "가나다라마바사아자차카" } });
    });
    expect(screen.getByText("이름은 10자 이내로 적어줘")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /완료|이름 없이 계속하기/ }),
    ).toBeDisabled();
  });

  it("valid 1–10 char name enables submit and persists to store on click", async () => {
    await act(async () => {
      render(<NamePage />);
    });
    const input = screen.getByLabelText("이름 (옵셔널)") as HTMLInputElement;
    await act(async () => {
      fireEvent.change(input, { target: { value: "효주" } });
    });
    const submit = screen.getByRole("button", {
      name: /완료|이름 없이 계속하기/,
    });
    expect(submit).toBeEnabled();
    await act(async () => {
      fireEvent.click(submit);
    });
    expect(useOnboardingStore.getState().name).toBe("효주");
    expect(pushMock).toHaveBeenCalledWith("/reading/category");
  });

  it("건너뛰기 routes to /reading/category without persisting a name (empty store)", async () => {
    await act(async () => {
      render(<NamePage />);
    });
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "건너뛰기" }));
    });
    expect(useOnboardingStore.getState().name).toBe("");
    expect(pushMock).toHaveBeenCalledWith("/reading/category");
  });

  it('empty name button copy reads "이름 없이 계속하기" (Screen 5 success/empty state)', async () => {
    await act(async () => {
      render(<NamePage />);
    });
    // Empty state — the primary CTA renders as "이름 없이 계속하기".
    expect(
      screen.getByRole("button", { name: "이름 없이 계속하기" }),
    ).toBeEnabled();
  });

  it("renders a back button that triggers router back", async () => {
    await act(async () => {
      render(<NamePage />);
    });
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /뒤로/ }));
    });
    expect(backMock).toHaveBeenCalled();
  });

  it("removing all chars after typing a long invalid name clears the error", async () => {
    await act(async () => {
      render(<NamePage />);
    });
    const input = screen.getByLabelText("이름 (옵셔널)") as HTMLInputElement;
    await act(async () => {
      fireEvent.change(input, { target: { value: "가나다라마바사아자차카" } });
    });
    expect(screen.queryByText("이름은 10자 이내로 적어줘")).toBeInTheDocument();
    await act(async () => {
      fireEvent.change(input, { target: { value: "" } });
    });
    expect(screen.queryByText("이름은 10자 이내로 적어줘")).toBeNull();
  });
});
