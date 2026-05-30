/**
 * Unit tests for `/onboarding/birth-time` (ISSUE-028, Screen 3, AC2, AC3).
 *
 * AC mapping:
 * - AC2: "시간은 모르겠어요" check → spinners disable + birthTimeUnknown=true.
 * - AC3: back tap → return to /onboarding/birth-date with date preserved.
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

import BirthTimePage from "@/app/onboarding/birth-time/page";

describe("/onboarding/birth-time — Screen 3 (ISSUE-028)", () => {
  beforeEach(() => {
    pushMock.mockReset();
    backMock.mockReset();
    useOnboardingStore.getState().reset();
    // Persist a birth date so AC3's back-nav contract is meaningful.
    useOnboardingStore.getState().setBirthDate("1997-03-15");
  });

  it("renders the page heading from copy_guide §3", async () => {
    await act(async () => {
      render(<BirthTimePage />);
    });
    expect(
      screen.getByRole("heading", {
        level: 1,
        name: /(태어난 시각|몇 시에 태어났어\?)/,
      }),
    ).toBeInTheDocument();
  });

  it("renders step indicator at 2/4", async () => {
    await act(async () => {
      render(<BirthTimePage />);
    });
    expect(screen.getByRole("list", { name: "2 / 4" })).toBeInTheDocument();
  });

  it('renders the hour + minute inputs and the "시간 모름" checkbox', async () => {
    await act(async () => {
      render(<BirthTimePage />);
    });
    expect(
      screen.getByLabelText("시", { selector: "input" }),
    ).toBeInTheDocument();
    expect(
      screen.getByLabelText("분", { selector: "input" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("checkbox", { name: /시간은 모르겠어요|시간 모름/ }),
    ).toBeInTheDocument();
  });

  it('AC2: checking "시간 모름" disables the hour + minute inputs and sets store flag', async () => {
    await act(async () => {
      render(<BirthTimePage />);
    });
    const unknown = screen.getByRole("checkbox", {
      name: /시간은 모르겠어요|시간 모름/,
    });
    const hour = screen.getByLabelText("시", {
      selector: "input",
    }) as HTMLInputElement;
    const minute = screen.getByLabelText("분", {
      selector: "input",
    }) as HTMLInputElement;
    expect(hour).not.toBeDisabled();
    expect(minute).not.toBeDisabled();
    await act(async () => {
      fireEvent.click(unknown);
    });
    expect(hour).toBeDisabled();
    expect(minute).toBeDisabled();
    expect(useOnboardingStore.getState().birthTimeUnknown).toBe(true);
  });

  it('AC2: checking "시간 모름" enables the 다음 button (valid empty state)', async () => {
    await act(async () => {
      render(<BirthTimePage />);
    });
    expect(screen.getByRole("button", { name: "다음" })).toBeDisabled();
    await act(async () => {
      fireEvent.click(
        screen.getByRole("checkbox", { name: /시간은 모르겠어요|시간 모름/ }),
      );
    });
    expect(screen.getByRole("button", { name: "다음" })).toBeEnabled();
  });

  it("typing both hour and minute enables the 다음 button (no checkbox)", async () => {
    await act(async () => {
      render(<BirthTimePage />);
    });
    const hour = screen.getByLabelText("시", {
      selector: "input",
    }) as HTMLInputElement;
    const minute = screen.getByLabelText("분", {
      selector: "input",
    }) as HTMLInputElement;
    await act(async () => {
      fireEvent.change(hour, { target: { value: "14" } });
      fireEvent.change(minute, { target: { value: "30" } });
    });
    expect(screen.getByRole("button", { name: "다음" })).toBeEnabled();
  });

  it("AC3: tapping back triggers router back navigation (and store still has prior date)", async () => {
    await act(async () => {
      render(<BirthTimePage />);
    });
    const back = screen.getByRole("button", { name: /뒤로/ });
    await act(async () => {
      fireEvent.click(back);
    });
    expect(backMock).toHaveBeenCalled();
    // Store still contains the date that was set in beforeEach.
    expect(useOnboardingStore.getState().birthDate).toBe("1997-03-15");
  });

  it("tapping 다음 with valid hour/minute pushes /onboarding/gender and persists the time", async () => {
    await act(async () => {
      render(<BirthTimePage />);
    });
    const hour = screen.getByLabelText("시", {
      selector: "input",
    }) as HTMLInputElement;
    const minute = screen.getByLabelText("분", {
      selector: "input",
    }) as HTMLInputElement;
    await act(async () => {
      fireEvent.change(hour, { target: { value: "14" } });
      fireEvent.change(minute, { target: { value: "30" } });
    });
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "다음" }));
    });
    expect(pushMock).toHaveBeenCalledWith("/onboarding/gender");
    expect(useOnboardingStore.getState().birthHour).toBe(14);
    expect(useOnboardingStore.getState().birthMinute).toBe(30);
  });
});
