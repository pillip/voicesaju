/**
 * Unit tests for `/me/edit-saju` (ISSUE-071, Screen 21).
 *
 * AC mapping (issues.md §ISSUE-071):
 *   AC1: PATCH success → counter banner updates (corrections_remaining
 *        surfaces via the page state after submit).
 *   AC2: backend 403 `correction_quota_exceeded` → page swaps to the
 *        운영 문의 fallback (no form, mailto link visible).
 *   AC3: corrections_remaining === 0 on the response → page swaps to
 *        the 운영 문의 fallback.
 *   AC4: past history references the old chart_id (backend behaviour
 *        — covered by the integration test, not here).
 */
import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import {
  render,
  screen,
  waitFor,
  fireEvent,
  act,
} from "@testing-library/react";

const replaceMock = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: vi.fn(),
    replace: replaceMock,
    back: vi.fn(),
    refresh: vi.fn(),
    prefetch: vi.fn(),
  }),
}));

import MeEditSajuPage from "@/app/me/edit-saju/page";

const VALID_PROFILE_ME = {
  profile_id: "p-1",
  chart_id: "c-1",
  birth_time_known: true,
  chart: {
    year: { stem: "정", branch: "축", element: "금", ten_god: null },
    month: { stem: "무", branch: "신", element: "토", ten_god: null },
    day: { stem: "기", branch: "유", element: "토", ten_god: null },
    hour: { stem: "갑", branch: "자", element: "목", ten_god: null },
    engine_version: "saju.v1",
  },
};

function mkOkResponse(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  } as unknown as Response;
}

function mkErrResponse(status: number, body: unknown = {}): Response {
  return {
    ok: false,
    status,
    json: async () => body,
  } as unknown as Response;
}

describe("MeEditSajuPage", () => {
  beforeEach(() => {
    replaceMock.mockReset();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders the form + counter banner after a successful profile load", async () => {
    const fetchImpl = vi
      .fn()
      .mockResolvedValueOnce(mkOkResponse(VALID_PROFILE_ME));

    render(<MeEditSajuPage fetchImpl={fetchImpl} />);

    await waitFor(() => {
      expect(screen.getByTestId("me-edit-saju-loaded")).toBeInTheDocument();
    });
    expect(screen.getByTestId("me-edit-saju-counter").textContent).toContain(
      "?/2",
    );
    expect(screen.getByTestId("me-edit-saju-form")).toBeInTheDocument();
    expect(screen.getByTestId("me-edit-saju-input-date")).toBeInTheDocument();
    expect(screen.getByTestId("me-edit-saju-input-gender")).toBeInTheDocument();
  });

  it("AC1: submit → confirm → PATCH success → counter banner updates", async () => {
    const patchOk = {
      profile_id: "p-1",
      chart_id: "c-2", // new chart
      chart: VALID_PROFILE_ME.chart,
      corrections_remaining: 1,
    };
    const fetchImpl = vi
      .fn()
      .mockResolvedValueOnce(mkOkResponse(VALID_PROFILE_ME))
      .mockResolvedValueOnce(mkOkResponse(patchOk));

    render(<MeEditSajuPage fetchImpl={fetchImpl} />);
    await waitFor(() =>
      expect(screen.getByTestId("me-edit-saju-loaded")).toBeInTheDocument(),
    );

    // Fill the form (date required).
    fireEvent.change(screen.getByTestId("me-edit-saju-input-date"), {
      target: { value: "1998-09-14" },
    });
    fireEvent.change(screen.getByTestId("me-edit-saju-input-time"), {
      target: { value: "09:45" },
    });

    // Submit → open ConfirmModal.
    fireEvent.click(screen.getByTestId("me-edit-saju-submit"));
    await waitFor(() => {
      expect(
        screen.getByText(
          "수정 후엔 새 사주로 풀이가 나와요. 과거 히스토리는 그대로 남아요.",
        ),
      ).toBeInTheDocument();
    });

    // Confirm.
    await act(async () => {
      fireEvent.click(screen.getByText("수정"));
    });

    // Counter banner now reads "1/2".
    await waitFor(() => {
      expect(screen.getByTestId("me-edit-saju-counter").textContent).toContain(
        "1/2",
      );
    });

    // Second fetch call was a PATCH.
    expect(fetchImpl).toHaveBeenCalledTimes(2);
    expect(fetchImpl.mock.calls[1][0]).toBe("/api/v1/profile");
    expect(fetchImpl.mock.calls[1][1]?.method).toBe("PATCH");
  });

  it("AC2: backend 403 quota_exceeded → swap to 운영 문의 fallback", async () => {
    const fetchImpl = vi
      .fn()
      .mockResolvedValueOnce(mkOkResponse(VALID_PROFILE_ME))
      .mockResolvedValueOnce(
        mkErrResponse(403, {
          detail: {
            error: {
              code: "correction_quota_exceeded",
              message: "수정 한도(2회)를 모두 사용했어요.",
              corrections_remaining: 0,
            },
          },
        }),
      );

    render(<MeEditSajuPage fetchImpl={fetchImpl} />);
    await waitFor(() =>
      expect(screen.getByTestId("me-edit-saju-loaded")).toBeInTheDocument(),
    );

    fireEvent.change(screen.getByTestId("me-edit-saju-input-date"), {
      target: { value: "1998-09-14" },
    });
    fireEvent.click(screen.getByTestId("me-edit-saju-submit"));
    await waitFor(() => {
      expect(
        screen.getByText(
          "수정 후엔 새 사주로 풀이가 나와요. 과거 히스토리는 그대로 남아요.",
        ),
      ).toBeInTheDocument();
    });

    await act(async () => {
      fireEvent.click(screen.getByText("수정"));
    });

    await waitFor(() => {
      expect(
        screen.getByTestId("me-edit-saju-quota-exhausted"),
      ).toBeInTheDocument();
    });
    expect(screen.queryByTestId("me-edit-saju-form")).not.toBeInTheDocument();
    expect(screen.getByTestId("me-edit-saju-mailto")).toHaveAttribute(
      "href",
      expect.stringContaining("mailto:"),
    );
  });

  it("AC3: corrections_remaining === 0 on response → quota fallback", async () => {
    const patchOk = {
      profile_id: "p-1",
      chart_id: "c-2",
      chart: VALID_PROFILE_ME.chart,
      corrections_remaining: 0,
    };
    const fetchImpl = vi
      .fn()
      .mockResolvedValueOnce(mkOkResponse(VALID_PROFILE_ME))
      .mockResolvedValueOnce(mkOkResponse(patchOk));

    render(<MeEditSajuPage fetchImpl={fetchImpl} />);
    await waitFor(() =>
      expect(screen.getByTestId("me-edit-saju-loaded")).toBeInTheDocument(),
    );

    fireEvent.change(screen.getByTestId("me-edit-saju-input-date"), {
      target: { value: "1998-09-14" },
    });
    fireEvent.click(screen.getByTestId("me-edit-saju-submit"));
    await waitFor(() => expect(screen.getByText("수정")).toBeInTheDocument());

    await act(async () => {
      fireEvent.click(screen.getByText("수정"));
    });

    await waitFor(() => {
      expect(
        screen.getByTestId("me-edit-saju-quota-exhausted"),
      ).toBeInTheDocument();
    });
  });

  it("401 on initial load → router.replace('/auth/login')", async () => {
    const fetchImpl = vi.fn().mockResolvedValueOnce(mkErrResponse(401));

    render(<MeEditSajuPage fetchImpl={fetchImpl} />);

    await waitFor(() => {
      expect(replaceMock).toHaveBeenCalledWith("/auth/login");
    });
  });

  it("404 on initial load → router.replace('/onboarding')", async () => {
    const fetchImpl = vi.fn().mockResolvedValueOnce(mkErrResponse(404));

    render(<MeEditSajuPage fetchImpl={fetchImpl} />);

    await waitFor(() => {
      expect(replaceMock).toHaveBeenCalledWith("/onboarding");
    });
  });

  it("network error → 'error' state with retry that re-triggers fetch", async () => {
    const fetchImpl = vi
      .fn()
      .mockRejectedValueOnce(new Error("offline"))
      .mockResolvedValueOnce(mkOkResponse(VALID_PROFILE_ME));

    render(<MeEditSajuPage fetchImpl={fetchImpl} />);

    await waitFor(() => {
      expect(screen.getByTestId("me-edit-saju-error")).toBeInTheDocument();
    });
    fireEvent.click(screen.getByTestId("me-edit-saju-retry"));
    await waitFor(() => {
      expect(screen.getByTestId("me-edit-saju-loaded")).toBeInTheDocument();
    });
  });

  it("time-unknown checkbox disables the time input", async () => {
    const fetchImpl = vi
      .fn()
      .mockResolvedValueOnce(mkOkResponse(VALID_PROFILE_ME));

    render(<MeEditSajuPage fetchImpl={fetchImpl} />);
    await waitFor(() =>
      expect(screen.getByTestId("me-edit-saju-loaded")).toBeInTheDocument(),
    );

    const timeInput = screen.getByTestId(
      "me-edit-saju-input-time",
    ) as HTMLInputElement;
    expect(timeInput.disabled).toBe(false);

    fireEvent.click(screen.getByTestId("me-edit-saju-input-time-unknown"));
    expect(timeInput.disabled).toBe(true);
  });
});
