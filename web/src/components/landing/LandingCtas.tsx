"use client";

/**
 * Landing CTAs (ISSUE-086).
 *
 * Client island for the landing page so the page itself remains
 * server-renderable. Owns three side effects that can't run server-side:
 *   1. Issue a server-side device ID on first visit via
 *      ``POST /api/v1/auth/device`` (ISSUE-024). The endpoint sets the
 *      ``vs_did`` HttpOnly cookie; we keep a client-side
 *      ``vs.device_client_id`` (uuidv4) in localStorage so the same
 *      device upserts to the same server row across visits.
 *   2. Detect a returning visitor with an in-progress reading session
 *      via the ``vs.in_progress`` localStorage marker (set by the
 *      onboarding / reading flows). When present, swap the primary
 *      CTA copy to "이어서 풀이 받기" (AC2).
 *   3. Defer first-render flip so SSR + first paint match (no hydration
 *      mismatch warnings).
 *
 * Why split from the page:
 *   - Keeps the server page free of "use client" directives so the
 *     hero illustration + tagline can be statically rendered on first
 *     paint.
 *   - Hooks (useState/useEffect) are only allowed in Client components.
 *
 * Why localStorage and not the Zustand onboarding-store:
 *   - The onboarding-store is intentionally session-scoped (PII), but
 *     this returning-state hint is non-PII (a boolean flag). The flow
 *     pages flip the marker when they start; the player flow clears it
 *     when the reading completes. The marker is a lightweight signal
 *     that doesn't need the store's typed shape.
 */

import { useEffect, useState } from "react";
import { PrimaryButton } from "@/components/ui/PrimaryButton";
import { SecondaryButton } from "@/components/ui/SecondaryButton";

const DEVICE_CLIENT_ID_KEY = "vs.device_client_id";
const IN_PROGRESS_KEY = "vs.in_progress";

/** Lazy uuidv4 — avoids pulling in a runtime dep for one call site. */
function uuidv4(): string {
  // ``crypto.randomUUID`` is available in modern browsers + jsdom 22+;
  // fall back to a Math.random impl for ancient runtimes (shouldn't
  // happen in production but keeps tests deterministic).
  if (
    typeof crypto !== "undefined" &&
    typeof crypto.randomUUID === "function"
  ) {
    return crypto.randomUUID();
  }
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    const v = c === "x" ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

function safeLocalStorageGet(key: string): string | null {
  try {
    return typeof window !== "undefined"
      ? window.localStorage.getItem(key)
      : null;
  } catch {
    // Private mode / quota exceeded — treat as absent.
    return null;
  }
}

function safeLocalStorageSet(key: string, value: string): void {
  try {
    if (typeof window !== "undefined") {
      window.localStorage.setItem(key, value);
    }
  } catch {
    // No-op — losing the client ID just means we re-mint next visit.
  }
}

async function ensureDeviceId(): Promise<void> {
  // Read or mint the client-side device id, then POST it to the API.
  // The cookie + server row are set by the endpoint; we ignore the
  // response body — the only thing we care about is that the upsert
  // happened.
  let clientId = safeLocalStorageGet(DEVICE_CLIENT_ID_KEY);
  if (!clientId) {
    clientId = uuidv4();
    safeLocalStorageSet(DEVICE_CLIENT_ID_KEY, clientId);
  }
  try {
    await fetch("/api/v1/auth/device", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ device_id_client: clientId }),
      credentials: "include",
      // Don't block the UI; fire-and-forget is fine — the cookie will
      // be set by the time the user navigates anywhere that needs it.
      keepalive: true,
    });
  } catch {
    // Silently swallow — the next session retries on its own.
  }
}

export function LandingCtas() {
  // ``hasInProgress`` defaults to ``null`` so the first server render
  // matches the first client render before useEffect runs. We flip it
  // to a boolean after mount, which causes a single re-render — no
  // hydration mismatch.
  const [hasInProgress, setHasInProgress] = useState<boolean | null>(null);

  useEffect(() => {
    setHasInProgress(safeLocalStorageGet(IN_PROGRESS_KEY) === "1");
    // Fire-and-forget device upsert; do not await.
    void ensureDeviceId();
  }, []);

  // Primary CTA copy swap (AC2). Before mount we render the default
  // ("지금 풀이 받기") so server + first client paint agree.
  const primaryCopy = hasInProgress ? "이어서 풀이 받기" : "지금 풀이 받기";

  const handlePrimary = () => {
    window.location.href = "/onboarding/birth-date";
  };
  const handleSecondary = () => {
    window.location.href = "/tarot";
  };

  return (
    <section
      data-testid="landing-ctas"
      className="flex w-full max-w-md flex-col items-stretch gap-3 py-6"
    >
      <PrimaryButton
        data-testid="landing-cta-primary"
        onClick={handlePrimary}
        className="w-full"
      >
        {primaryCopy}
      </PrimaryButton>
      <SecondaryButton
        data-testid="landing-cta-secondary"
        onClick={handleSecondary}
        className="w-full"
      >
        오늘의 타로
      </SecondaryButton>
    </section>
  );
}
