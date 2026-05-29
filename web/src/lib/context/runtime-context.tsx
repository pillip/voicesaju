"use client";

import { createContext, useContext, useEffect, useMemo, useState } from "react";

/**
 * Runtime channel — where the web app is currently running.
 *
 * - `web`: standalone Next.js in a real browser tab. Default for SSR and
 *   any user-agent that doesn't match the Toss in-app webview signature.
 * - `toss_webview`: the Toss app's in-app browser (FR-024 / FR-019). The
 *   share / save / OS-level capabilities differ from a vanilla browser
 *   tab, so features that depend on them must consult `capabilities`.
 */
export type RuntimeChannel = "web" | "toss_webview";

export interface RuntimeCapabilities {
  /** Can the runtime open the system Instagram share sheet? */
  canShareInstagram: boolean;
  /** Can the runtime open the KakaoTalk share sheet? */
  canShareKakao: boolean;
  /** Can the runtime save images to the OS photo library? */
  canSaveImage: boolean;
}

export interface RuntimeContextValue {
  channel: RuntimeChannel;
  capabilities: RuntimeCapabilities;
}

const WEB_DEFAULT: RuntimeContextValue = {
  channel: "web",
  capabilities: {
    canShareInstagram: true,
    canShareKakao: true,
    canSaveImage: false,
  },
};

const TOSS_WEBVIEW: RuntimeContextValue = {
  channel: "toss_webview",
  capabilities: {
    canShareInstagram: false,
    canShareKakao: false,
    canSaveImage: true,
  },
};

const RuntimeContext = createContext<RuntimeContextValue>(WEB_DEFAULT);

/**
 * Provider that detects the runtime channel on mount.
 *
 * SSR semantics:
 * - The initial render uses the `web` default so the markup matches what
 *   the server emits. Detection runs in a `useEffect` after hydration,
 *   then state flips to `toss_webview` if the UA matches `/Toss\//i`.
 * - No `window`/`navigator` access happens during render — the file is
 *   safe to import from server components even though the provider
 *   itself is a client component.
 */
export function RuntimeProvider({ children }: { children: React.ReactNode }) {
  const [value, setValue] = useState<RuntimeContextValue>(WEB_DEFAULT);

  useEffect(() => {
    // navigator only exists in the browser.
    if (typeof navigator === "undefined") return;
    if (/Toss\//i.test(navigator.userAgent)) {
      setValue(TOSS_WEBVIEW);
    }
  }, []);

  // Stable reference for downstream React.memo consumers.
  const memo = useMemo(() => value, [value]);
  return (
    <RuntimeContext.Provider value={memo}>{children}</RuntimeContext.Provider>
  );
}

/**
 * Read the current runtime channel + capabilities.
 *
 * Outside a provider, returns the `web` default. This keeps unit tests
 * and isolated component renders working without explicit wiring.
 */
export function useRuntimeContext(): RuntimeContextValue {
  return useContext(RuntimeContext);
}
