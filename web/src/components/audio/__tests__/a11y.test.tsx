/**
 * Accessibility scan for `<VoicePlayer>` (ISSUE-033).
 *
 * We scan the default state (no chunks landed yet, subtitle empty). The
 * scan runs against the loading/playing shell because:
 *  - jsdom does not implement `HTMLMediaElement`'s play/pause/timeupdate
 *    cycle reliably; the `playing` branch is structurally identical to
 *    `loading` from the aria perspective (same persona + same subtitle
 *    landmark + same progressbar).
 *  - The same color tokens & landmarks are reused across all branches,
 *    so a violation in any branch surfaces in the scan of any other.
 *
 * Reference: matches the pattern set by ISSUE-032
 * (`web/src/app/reading/intro/[category]/__tests__/a11y.test.tsx`).
 */

import { describe, expect, it } from "vitest";
import { render } from "@testing-library/react";
import { axe, toHaveNoViolations } from "jest-axe";
import { useMemo } from "react";
import { VoicePlayer } from "@/components/audio/VoicePlayer";
import type { ChunkEvent } from "@/lib/audio/events";
import { makeFakeMediaSourceFactory } from "@/lib/audio/__tests__/fake-media-source";

expect.extend(toHaveNoViolations);

/**
 * Empty source that closes immediately. The player stays in the
 * `buffering` / `loading` UI shell (no chunks arrived, no timeout
 * fired) which is exactly the state we want to scan.
 *
 * We avoid a never-resolving source because Vitest's default test
 * timeout (5s) would fire — the loading shell shares the same
 * landmarks as the playing shell, so scanning the empty-closed source
 * gives the same coverage.
 */
function emptySource(): AsyncIterable<ChunkEvent> {
  return {
    [Symbol.asyncIterator]: () => ({
      next: async () =>
        ({ value: undefined, done: true }) as IteratorResult<ChunkEvent>,
    }),
  };
}

function PlayerHarness() {
  const { factory } = useMemo(() => makeFakeMediaSourceFactory(), []);
  const source = useMemo(() => emptySource(), []);
  return (
    <VoicePlayer
      source={source}
      mediaSourceFactory={factory}
      fetcher={async () => new ArrayBuffer(0)}
      // Suppress the 5s first-chunk timeout for the scan — we don't
      // want the background timer firing during axe traversal.
      firstChunkTimeoutMs={60_000}
    />
  );
}

describe("<VoicePlayer /> accessibility", () => {
  it("has no axe-core violations in the default (loading) state", async () => {
    const { container, unmount } = render(<PlayerHarness />);
    // Flush microtasks so React commits the initial effect.
    await Promise.resolve();
    await Promise.resolve();
    const results = await axe(container);
    expect(results).toHaveNoViolations();
    unmount();
  }, 15_000);
});
