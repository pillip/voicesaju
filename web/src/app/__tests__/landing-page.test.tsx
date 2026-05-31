/**
 * Unit tests for the landing `/` page (ISSUE-086).
 *
 * AC mapping:
 *   - AC1: new visitor → primary CTA reads "지금 풀이 받기", secondary
 *     reads "오늘의 타로". Both are above-the-fold (rendered eagerly).
 *   - AC2: returning visitor with `vs.in_progress=1` in localStorage →
 *     primary CTA copy swaps to "이어서 풀이 받기".
 *   - AC3: trust strip silently absent when the counter fetch fails.
 *
 * What we do NOT test here (out of scope):
 *   - The actual ``POST /api/v1/auth/device`` call — covered by the
 *     LandingCtas component test below + the existing ISSUE-024
 *     integration tests on the API side.
 *   - The hero illustration's visual fidelity — placeholder only.
 */
import { describe, expect, it, beforeEach, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";

import LandingPage from "@/app/page";

function clearLocalStorage() {
  try {
    window.localStorage.clear();
  } catch {
    // jsdom always exposes localStorage; the catch is defensive.
  }
}

describe("LandingPage", () => {
  beforeEach(() => {
    clearLocalStorage();
    // Stub global fetch so the device upsert + trust-strip stub don't
    // hit a real network. The trust strip stub is in-process so it
    // doesn't actually call fetch — but a stray call from the device
    // upsert would otherwise log warnings.
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ device_id: "srv-0" }),
        } as unknown as Response),
      ),
    );
  });

  it("AC1: new visitor sees both CTAs with the default copy", async () => {
    render(<LandingPage />);
    expect(screen.getByTestId("landing")).toBeTruthy();
    expect(screen.getByTestId("hero-illustration")).toBeTruthy();

    // Primary CTA — default copy for a fresh visitor.
    const primary = screen.getByTestId("landing-cta-primary");
    expect(primary.textContent).toContain("지금 풀이 받기");

    // Secondary CTA — "오늘의 타로".
    const secondary = screen.getByTestId("landing-cta-secondary");
    expect(secondary.textContent).toContain("오늘의 타로");
  });

  it('AC2: returning visitor with in-progress flag sees "이어서 풀이 받기"', async () => {
    window.localStorage.setItem("vs.in_progress", "1");

    render(<LandingPage />);

    // The flip happens in a useEffect, so wait for it.
    await waitFor(() => {
      const primary = screen.getByTestId("landing-cta-primary");
      expect(primary.textContent).toContain("이어서 풀이 받기");
    });
  });

  it("AC3: trust strip renders the count when the stub resolves", async () => {
    render(<LandingPage />);
    // The stub resolves synchronously inside an effect — after a tick
    // the strip should be present.
    await waitFor(() => {
      expect(screen.queryByTestId("trust-strip")).not.toBeNull();
    });
    const strip = screen.getByTestId("trust-strip");
    expect(strip.textContent).toMatch(/오늘 .+ 명이 풀이를 받았어요|오늘 \d/);
  });
});
