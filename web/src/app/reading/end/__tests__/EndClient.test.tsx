/**
 * Unit tests for `<EndClient>` — `/reading/end` Screen 11 (ISSUE-059).
 *
 * The page is a client component because it uses `useSearchParams`,
 * `useEffect` (for the 1-second signup modal timer), and the
 * `navigator.share` / `window.Kakao` / clipboard capability detection.
 *
 * To keep the Vitest worker light (ISSUE-042 OOM lesson) we mock the
 * heavy presentational children — `<QuoteCardPreview>` and
 * `<ShareButtonRow>` — so the page test only verifies the orchestration
 * (fetch by slug, signup modal timer, CTA wiring). The children get
 * their own tests in `src/components/share/__tests__/`.
 */
import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { render, screen, act } from "@testing-library/react";

import { RuntimeProvider } from "@/lib/context/runtime-context";
import type { QuoteCardBySlugResponse } from "@/app/api/og/[slug]/og-helpers";

// Mock the share children so the page test stays light.
vi.mock("@/components/share/QuoteCardPreview", () => ({
  QuoteCardPreview: ({
    slug,
    card,
  }: {
    slug: string;
    card?: QuoteCardBySlugResponse;
  }) => (
    <div
      data-testid="mock-quote-card-preview"
      data-slug={slug}
      data-status={card?.og_status ?? "loading"}
    />
  ),
}));
vi.mock("@/components/share/ShareButtonRow", () => ({
  ShareButtonRow: ({ slug }: { slug: string }) => (
    <div data-testid="mock-share-button-row" data-slug={slug} />
  ),
}));

// Search-params mock — overridden per-test.
const searchParamsState: { slug: string | null; member: string | null } = {
  slug: null,
  member: null,
};
vi.mock("next/navigation", async () => {
  const actual =
    await vi.importActual<typeof import("next/navigation")>("next/navigation");
  return {
    ...actual,
    useSearchParams: () => ({
      get: (key: string) => {
        if (key === "slug") return searchParamsState.slug;
        if (key === "member") return searchParamsState.member;
        return null;
      },
    }),
    useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  };
});

import EndClient from "../EndClient";

const sampleCard: QuoteCardBySlugResponse = {
  quote_card_id: "qc-1",
  category: "love",
  character_key: "nuna",
  quote_text: "그 사람은 너랑 코드가 안 맞아.",
  og_status: "baked",
  og_r2_key: "og/qc-1.png",
};

function renderEnd(ui: React.ReactElement) {
  return render(<RuntimeProvider>{ui}</RuntimeProvider>);
}

describe("EndClient — `/reading/end` Screen 11", () => {
  beforeEach(() => {
    searchParamsState.slug = "abc123";
    searchParamsState.member = null;
    // Vanilla browser UA.
    Object.defineProperty(window.navigator, "userAgent", {
      value:
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
      configurable: true,
      writable: true,
    });
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it("AC1: fetches the card and renders QuoteCardPreview + ShareButtonRow", async () => {
    const fetchSpy = vi.spyOn(global, "fetch").mockResolvedValueOnce(
      new Response(JSON.stringify(sampleCard), {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
    );

    await act(async () => {
      renderEnd(<EndClient />);
    });
    // Let the fetch microtask resolve.
    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(fetchSpy).toHaveBeenCalledTimes(1);
    expect(String(fetchSpy.mock.calls[0][0])).toContain(
      "/api/v1/quote-cards/by-slug/abc123",
    );

    const preview = screen.getByTestId("mock-quote-card-preview");
    expect(preview.getAttribute("data-slug")).toBe("abc123");
    expect(preview.getAttribute("data-status")).toBe("baked");

    expect(screen.getByTestId("mock-share-button-row")).toBeInTheDocument();
  });

  it('renders the secondary CTAs ("또 풀이 받기" + "마이페이지로")', async () => {
    vi.spyOn(global, "fetch").mockResolvedValueOnce(
      new Response(JSON.stringify(sampleCard), { status: 200 }),
    );
    await act(async () => {
      renderEnd(<EndClient />);
    });
    await act(async () => {
      await Promise.resolve();
    });
    expect(screen.getByRole("link", { name: "또 풀이 받기" })).toHaveAttribute(
      "href",
      "/reading/category",
    );
    expect(screen.getByRole("link", { name: "마이페이지로" })).toHaveAttribute(
      "href",
      "/me",
    );
  });

  it("AC5: opens the signup modal exactly 1 second after load for non-members", async () => {
    vi.spyOn(global, "fetch").mockResolvedValueOnce(
      new Response(JSON.stringify(sampleCard), { status: 200 }),
    );
    await act(async () => {
      renderEnd(<EndClient />);
    });

    // Modal must NOT be open immediately.
    expect(screen.queryByText("결과 저장하려면 1초 가입")).toBeNull();

    // Advance time by 999ms — still closed.
    await act(async () => {
      vi.advanceTimersByTime(999);
    });
    expect(screen.queryByText("결과 저장하려면 1초 가입")).toBeNull();

    // Cross 1000ms → modal opens.
    await act(async () => {
      vi.advanceTimersByTime(2);
    });
    expect(screen.getByText("결과 저장하려면 1초 가입")).toBeInTheDocument();
  });

  it("does NOT open the signup modal for members (?member=true)", async () => {
    searchParamsState.member = "true";
    vi.spyOn(global, "fetch").mockResolvedValueOnce(
      new Response(JSON.stringify(sampleCard), { status: 200 }),
    );
    await act(async () => {
      renderEnd(<EndClient />);
    });
    await act(async () => {
      vi.advanceTimersByTime(5000);
    });
    expect(screen.queryByText("결과 저장하려면 1초 가입")).toBeNull();
  });

  it("handles missing slug by rendering an error state (no fetch made)", async () => {
    searchParamsState.slug = null;
    const fetchSpy = vi.spyOn(global, "fetch");
    await act(async () => {
      renderEnd(<EndClient />);
    });
    expect(fetchSpy).not.toHaveBeenCalled();
    expect(screen.getByTestId("reading-end-error")).toBeInTheDocument();
  });

  it("handles backend 404 by rendering the failed-status preview", async () => {
    vi.spyOn(global, "fetch").mockResolvedValueOnce(
      new Response("{}", { status: 404 }),
    );
    await act(async () => {
      renderEnd(<EndClient />);
    });
    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });
    expect(screen.getByTestId("reading-end-error")).toBeInTheDocument();
  });
});
