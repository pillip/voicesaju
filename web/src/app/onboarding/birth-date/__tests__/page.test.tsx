/**
 * Unit tests for `/onboarding/birth-date` (ISSUE-028, Screen 2, AC1, AC5).
 *
 * AC mapping:
 * - AC1: valid solar date + tap 다음 → routed to /onboarding/birth-time, date persisted in store.
 * - AC5: keyboard nav order — date input → toggle → 다음 button.
 *
 * Mock next/navigation router because jsdom has no App Router runtime.
 */
import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, act, fireEvent } from "@testing-library/react";
import { useOnboardingStore } from "@/lib/stores/onboarding-store";

const pushMock = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: pushMock, back: vi.fn() }),
  useSearchParams: () => new URLSearchParams(),
}));

import BirthDatePage from "@/app/onboarding/birth-date/page";

describe("/onboarding/birth-date — Screen 2 (ISSUE-028)", () => {
  beforeEach(() => {
    pushMock.mockReset();
    useOnboardingStore.getState().reset();
  });

  it("renders the page heading from copy_guide §2", async () => {
    await act(async () => {
      render(<BirthDatePage />);
    });
    // copy_guide §2 H1 = "생년월일"; ux_spec Screen 2 title alt = "언제 태어났어?"
    expect(
      screen.getByRole("heading", {
        level: 1,
        name: /(생년월일|언제 태어났어\?)/,
      }),
    ).toBeInTheDocument();
  });

  it("renders the step indicator with 1/4 progress", async () => {
    await act(async () => {
      render(<BirthDatePage />);
    });
    // StepIndicator renders <ol aria-label="1 / 4">.
    expect(screen.getByRole("list", { name: "1 / 4" })).toBeInTheDocument();
  });

  it("renders solar (양력) and lunar (음력) toggle options", async () => {
    await act(async () => {
      render(<BirthDatePage />);
    });
    expect(screen.getByRole("radio", { name: "양력" })).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: "음력" })).toBeInTheDocument();
  });

  it("disables the 다음 button when no date is entered (empty state)", async () => {
    await act(async () => {
      render(<BirthDatePage />);
    });
    expect(screen.getByRole("button", { name: "다음" })).toBeDisabled();
  });

  it("AC1: valid solar date + tap 다음 → router pushes /onboarding/birth-time + store persists date", async () => {
    await act(async () => {
      render(<BirthDatePage />);
    });
    const input = screen.getByLabelText(
      /생년월일|YYYY-MM-DD/,
    ) as HTMLInputElement;
    await act(async () => {
      fireEvent.change(input, { target: { value: "1997-03-15" } });
    });
    const next = screen.getByRole("button", { name: "다음" });
    expect(next).toBeEnabled();
    await act(async () => {
      fireEvent.click(next);
    });
    expect(pushMock).toHaveBeenCalledWith("/onboarding/birth-time");
    expect(useOnboardingStore.getState().birthDate).toBe("1997-03-15");
    expect(useOnboardingStore.getState().calendarSystem).toBe("solar");
  });

  it('shows inline error for a future date (per Implementation Notes — "no future dates")', async () => {
    await act(async () => {
      render(<BirthDatePage />);
    });
    const input = screen.getByLabelText(
      /생년월일|YYYY-MM-DD/,
    ) as HTMLInputElement;
    await act(async () => {
      fireEvent.change(input, { target: { value: "2099-01-01" } });
    });
    // Error text rendered, 다음 stays disabled.
    expect(screen.getByText(/아직 태어나지 않았네\./)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "다음" })).toBeDisabled();
  });

  it("shows inline error for a date before 1900 (too-old) and keeps button disabled", async () => {
    // We exercise the "too-old" path here because native `<input type="date">`
    // in jsdom silently rejects calendar-impossible strings like "1997-02-30"
    // before the change event reaches React. The validator unit test in
    // `src/lib/validators/__tests__/onboarding.test.ts` covers Feb 30 directly.
    await act(async () => {
      render(<BirthDatePage />);
    });
    const input = screen.getByLabelText(/생년월일/) as HTMLInputElement;
    await act(async () => {
      fireEvent.change(input, { target: { value: "1850-06-01" } });
    });
    expect(screen.getByText(/너무 옛날인데\./)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "다음" })).toBeDisabled();
  });

  it("switching to 음력 persists the calendar system to the store", async () => {
    await act(async () => {
      render(<BirthDatePage />);
    });
    const lunar = screen.getByRole("radio", { name: "음력" });
    await act(async () => {
      fireEvent.click(lunar);
    });
    expect(useOnboardingStore.getState().calendarSystem).toBe("lunar");
  });

  it("AC5 — keyboard order: date input → toggle radio → 다음 button (logical tab order)", async () => {
    await act(async () => {
      render(<BirthDatePage />);
    });
    const focusables = screen
      .getAllByRole("button")
      .concat(screen.getAllByRole("radio"));
    // Ensure that the date input precedes the toggle radios in the DOM, and
    // the 다음 button comes last.
    const input = screen.getByLabelText(/생년월일|YYYY-MM-DD/);
    const solarRadio = screen.getByRole("radio", { name: "양력" });
    const next = screen.getByRole("button", { name: "다음" });
    expect(
      input.compareDocumentPosition(solarRadio) &
        Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
    expect(
      solarRadio.compareDocumentPosition(next) &
        Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
    expect(focusables.length).toBeGreaterThan(0);
  });

  it("pre-populates the date input from the store on remount (AC3 contract — back nav preserves)", async () => {
    useOnboardingStore.getState().setBirthDate("1990-12-01");
    await act(async () => {
      render(<BirthDatePage />);
    });
    const input = screen.getByLabelText(
      /생년월일|YYYY-MM-DD/,
    ) as HTMLInputElement;
    expect(input.value).toBe("1990-12-01");
  });
});
