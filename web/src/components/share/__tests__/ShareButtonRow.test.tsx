/**
 * Unit tests for {@link ShareButtonRow} — Screen 11 share row used by
 * `/reading/end` (ISSUE-059).
 *
 * Channel matrix (FR-019 / FR-024):
 *   - web (default UA): 3 buttons — "인스타 스토리" (native share),
 *     "카톡" (Kakao SDK), "저장" (blob download).
 *   - toss_webview UA: 2 buttons — "저장" + "링크 복사".
 *
 * AC coverage:
 *   - AC2: tap "인스타 스토리" → `navigator.share({...})` is called with
 *     the share URL pointing at `/share/{slug}`.
 *   - AC3: tap "카톡" → `window.Kakao.Share.sendDefault({...})` is called.
 *   - AC4: tap "저장" → an anchor with `download="quote-{slug}.png"` is
 *     created and clicked. We assert the synthesised element shape.
 *   - AC6: toss_webview UA hides 인스타 / 카톡 and shows 저장 + 링크 복사
 *     instead. Tapping 링크 복사 calls `navigator.clipboard.writeText`.
 *
 * Kakao SDK is stubbed via `window.Kakao` — no real script tag, no
 * network. The test asserts the stub was called, not that Kakao loads.
 */
import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, act } from "@testing-library/react";

import { ShareButtonRow } from "@/components/share/ShareButtonRow";
import { RuntimeProvider } from "@/lib/context/runtime-context";

const slug = "abc123";
const shareUrl = `/share/${slug}`;
const ogImageUrl = `/api/og/${slug}`;
const quoteText = "그 사람은 너랑 코드가 안 맞아.";

function setUserAgent(ua: string) {
  Object.defineProperty(window.navigator, "userAgent", {
    value: ua,
    configurable: true,
    writable: true,
  });
}

function renderRow(ui: React.ReactElement) {
  return render(<RuntimeProvider>{ui}</RuntimeProvider>);
}

// Vanilla Chrome — `web` channel, all 3 buttons.
const CHROME_UA =
  "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36";
// Toss WebView UA — channel detector flips to `toss_webview`.
const TOSS_UA =
  "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 Toss/5.180.0";

describe("ShareButtonRow", () => {
  beforeEach(() => {
    setUserAgent(CHROME_UA);
  });

  afterEach(() => {
    // Scrub global mocks between tests so a stub from one case doesn't
    // bleed into another.
    delete (window as unknown as { Kakao?: unknown }).Kakao;
    vi.restoreAllMocks();
  });

  it("web channel renders all 3 share buttons", async () => {
    await act(async () => {
      renderRow(
        <ShareButtonRow
          slug={slug}
          shareUrl={shareUrl}
          ogImageUrl={ogImageUrl}
          quoteText={quoteText}
        />,
      );
    });
    expect(
      screen.getByRole("button", { name: "인스타 스토리" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "카톡" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "저장" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "링크 복사" })).toBeNull();
  });

  it('AC2: tapping "인스타 스토리" invokes navigator.share with the share URL', async () => {
    const shareSpy = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(window.navigator, "share", {
      value: shareSpy,
      configurable: true,
      writable: true,
    });

    await act(async () => {
      renderRow(
        <ShareButtonRow
          slug={slug}
          shareUrl={shareUrl}
          ogImageUrl={ogImageUrl}
          quoteText={quoteText}
        />,
      );
    });
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "인스타 스토리" }));
    });
    expect(shareSpy).toHaveBeenCalledTimes(1);
    const arg = shareSpy.mock.calls[0][0] as { url?: string; text?: string };
    expect(arg.url).toContain(shareUrl);
  });

  it('AC3: tapping "카톡" invokes window.Kakao.Share.sendDefault', async () => {
    const sendDefault = vi.fn();
    (
      window as unknown as {
        Kakao: { Share: { sendDefault: typeof sendDefault } };
      }
    ).Kakao = {
      Share: { sendDefault },
    };

    await act(async () => {
      renderRow(
        <ShareButtonRow
          slug={slug}
          shareUrl={shareUrl}
          ogImageUrl={ogImageUrl}
          quoteText={quoteText}
        />,
      );
    });
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "카톡" }));
    });
    expect(sendDefault).toHaveBeenCalledTimes(1);
    const call = sendDefault.mock.calls[0][0] as {
      content?: { imageUrl?: string; link?: { mobileWebUrl?: string } };
    };
    // Image URL must point at /api/og/{slug} (FR-019 + ISSUE-060).
    expect(call.content?.imageUrl).toContain(ogImageUrl);
    // Link must point at the share landing page (ISSUE-061).
    expect(call.content?.link?.mobileWebUrl).toContain(shareUrl);
  });

  it('AC4: tapping "저장" triggers a download with the slug in the filename', async () => {
    // Spy on createElement so we can inspect the synthesised anchor.
    const realCreate = document.createElement.bind(document);
    const anchorClicks: HTMLAnchorElement[] = [];
    const createSpy = vi
      .spyOn(document, "createElement")
      .mockImplementation((tag: string) => {
        const el = realCreate(tag) as HTMLElement;
        if (tag.toLowerCase() === "a") {
          const a = el as HTMLAnchorElement;
          // Capture the element + intercept the click() the component will fire.
          a.click = vi.fn(() => {
            anchorClicks.push(a);
          });
        }
        return el;
      });

    await act(async () => {
      renderRow(
        <ShareButtonRow
          slug={slug}
          shareUrl={shareUrl}
          ogImageUrl={ogImageUrl}
          quoteText={quoteText}
        />,
      );
    });
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "저장" }));
    });

    expect(anchorClicks.length).toBeGreaterThan(0);
    const anchor = anchorClicks[0];
    expect(anchor.getAttribute("href")).toContain(ogImageUrl);
    expect(anchor.getAttribute("download")).toContain(slug);

    createSpy.mockRestore();
  });

  it("AC6: toss_webview shows ONLY 저장 + 링크 복사 (no 인스타 / 카톡)", async () => {
    setUserAgent(TOSS_UA);
    await act(async () => {
      renderRow(
        <ShareButtonRow
          slug={slug}
          shareUrl={shareUrl}
          ogImageUrl={ogImageUrl}
          quoteText={quoteText}
        />,
      );
    });
    expect(screen.getByRole("button", { name: "저장" })).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "링크 복사" }),
    ).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "인스타 스토리" })).toBeNull();
    expect(screen.queryByRole("button", { name: "카톡" })).toBeNull();
  });

  it('AC6: tapping "링크 복사" in toss_webview calls navigator.clipboard.writeText', async () => {
    setUserAgent(TOSS_UA);
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(window.navigator, "clipboard", {
      value: { writeText },
      configurable: true,
      writable: true,
    });

    await act(async () => {
      renderRow(
        <ShareButtonRow
          slug={slug}
          shareUrl={shareUrl}
          ogImageUrl={ogImageUrl}
          quoteText={quoteText}
        />,
      );
    });
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "링크 복사" }));
    });
    expect(writeText).toHaveBeenCalledTimes(1);
    // The copied text should contain the share URL.
    expect(String(writeText.mock.calls[0][0])).toContain(shareUrl);
  });
});
