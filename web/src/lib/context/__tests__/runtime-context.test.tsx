import { describe, expect, it, beforeEach } from "vitest";
import { render, screen, act } from "@testing-library/react";
import {
  RuntimeProvider,
  useRuntimeContext,
} from "@/lib/context/runtime-context";

const ORIGINAL_UA = Object.getOwnPropertyDescriptor(navigator, "userAgent");

function setUserAgent(ua: string) {
  Object.defineProperty(window.navigator, "userAgent", {
    value: ua,
    configurable: true,
    writable: true,
  });
}

function restoreUserAgent() {
  if (ORIGINAL_UA) {
    Object.defineProperty(navigator, "userAgent", ORIGINAL_UA);
  }
}

function Probe() {
  const ctx = useRuntimeContext();
  return (
    <>
      <span data-testid="channel">{ctx.channel}</span>
      <span data-testid="caps-instagram">
        {String(ctx.capabilities.canShareInstagram)}
      </span>
      <span data-testid="caps-kakao">
        {String(ctx.capabilities.canShareKakao)}
      </span>
      <span data-testid="caps-save-image">
        {String(ctx.capabilities.canSaveImage)}
      </span>
    </>
  );
}

describe("RuntimeProvider + useRuntimeContext", () => {
  beforeEach(() => {
    restoreUserAgent();
  });

  it("falls back to web defaults when used outside a provider", () => {
    render(<Probe />);
    expect(screen.getByTestId("channel")).toHaveTextContent("web");
    expect(screen.getByTestId("caps-instagram")).toHaveTextContent("true");
    expect(screen.getByTestId("caps-kakao")).toHaveTextContent("true");
    expect(screen.getByTestId("caps-save-image")).toHaveTextContent("false");
  });

  it("reports channel=web for a normal Chrome user agent", async () => {
    setUserAgent(
      "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    );
    await act(async () => {
      render(
        <RuntimeProvider>
          <Probe />
        </RuntimeProvider>,
      );
    });
    expect(screen.getByTestId("channel")).toHaveTextContent("web");
    expect(screen.getByTestId("caps-instagram")).toHaveTextContent("true");
    expect(screen.getByTestId("caps-kakao")).toHaveTextContent("true");
    expect(screen.getByTestId("caps-save-image")).toHaveTextContent("false");
  });

  it("reports channel=toss_webview when UA contains Toss/", async () => {
    setUserAgent(
      "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 Toss/5.180.0",
    );
    await act(async () => {
      render(
        <RuntimeProvider>
          <Probe />
        </RuntimeProvider>,
      );
    });
    expect(screen.getByTestId("channel")).toHaveTextContent("toss_webview");
    expect(screen.getByTestId("caps-instagram")).toHaveTextContent("false");
    expect(screen.getByTestId("caps-kakao")).toHaveTextContent("false");
    expect(screen.getByTestId("caps-save-image")).toHaveTextContent("true");
  });

  it("matches Toss UA case-insensitively (regex /Toss\\//i)", async () => {
    setUserAgent("Mozilla/5.0 (iPhone) toss/4.55.0 Mobile/15E148 Safari/604.1");
    await act(async () => {
      render(
        <RuntimeProvider>
          <Probe />
        </RuntimeProvider>,
      );
    });
    expect(screen.getByTestId("channel")).toHaveTextContent("toss_webview");
  });

  it("initial pre-effect render returns the web default (SSR-safe)", () => {
    setUserAgent(
      "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 Toss/5.180.0",
    );
    // Render without awaiting effects to simulate the SSR snapshot.
    const { container } = render(
      <RuntimeProvider>
        <Probe />
      </RuntimeProvider>,
    );
    // The first paint must still report `web` so server + client markup
    // agree (no hydration mismatch).
    // After the useEffect runs (act-flush below), the value flips.
    expect(
      container.querySelector('[data-testid="channel"]')!.textContent,
    ).toBe("toss_webview");
  });
});
