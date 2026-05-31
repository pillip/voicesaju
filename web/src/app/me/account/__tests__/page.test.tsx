/**
 * /me/account vitest (ISSUE-072).
 *
 * AC1: logout → POST /api/v1/auth/logout + router.replace('/').
 * AC2: 회원 탈퇴 + confirm → POST /api/v1/users/me/delete + redirect.
 */
import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const replaceMock = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: replaceMock, back: vi.fn() }),
}));

import AccountPage from "@/app/me/account/page";

describe("/me/account", () => {
  beforeEach(() => {
    replaceMock.mockReset();
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response(null, { status: 200 })),
    );
  });

  it("renders logout + delete buttons", () => {
    render(<AccountPage />);
    expect(screen.getByTestId("logout-button")).toBeInTheDocument();
    expect(screen.getByTestId("delete-button")).toBeInTheDocument();
  });

  it("AC1: tap 로그아웃 → POST /api/v1/auth/logout + redirect to /", async () => {
    render(<AccountPage />);
    await act(async () => {
      fireEvent.click(screen.getByTestId("logout-button"));
    });
    expect(fetch).toHaveBeenCalledWith(
      "/api/v1/auth/logout",
      expect.objectContaining({ method: "POST" }),
    );
    await waitFor(() => expect(replaceMock).toHaveBeenCalledWith("/"));
  });

  it("AC2: tap 회원 탈퇴 opens confirm; confirm → POST /me/delete + redirect", async () => {
    render(<AccountPage />);
    await act(async () => {
      fireEvent.click(screen.getByTestId("delete-button"));
    });
    expect(screen.getByTestId("delete-confirm")).toBeInTheDocument();

    await act(async () => {
      fireEvent.click(screen.getByTestId("confirm-delete"));
    });
    expect(fetch).toHaveBeenCalledWith(
      "/api/v1/users/me/delete",
      expect.objectContaining({ method: "POST" }),
    );
    await waitFor(() => expect(replaceMock).toHaveBeenCalledWith("/"));
  });

  it("cancel button closes the confirm modal without firing fetch", async () => {
    render(<AccountPage />);
    await act(async () => {
      fireEvent.click(screen.getByTestId("delete-button"));
    });
    await act(async () => {
      fireEvent.click(screen.getByTestId("cancel-delete"));
    });
    expect(screen.queryByTestId("delete-confirm")).not.toBeInTheDocument();
    expect(fetch).not.toHaveBeenCalled();
  });

  it("delete failure renders the error banner", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response(null, { status: 500 })),
    );
    render(<AccountPage />);
    await act(async () => {
      fireEvent.click(screen.getByTestId("delete-button"));
    });
    await act(async () => {
      fireEvent.click(screen.getByTestId("confirm-delete"));
    });
    await waitFor(() =>
      expect(screen.getByTestId("account-error").textContent).toContain(
        "탈퇴 처리",
      ),
    );
    expect(replaceMock).not.toHaveBeenCalled();
  });
});
