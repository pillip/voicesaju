/**
 * Page-level state-machine tests for `/tarot/play` (ISSUE-051).
 *
 * Per the ISSUE-042 + ISSUE-053 OOM retros we keep the page test SMALL
 * and avoid mounting the real VoicePlayer / MediaSource tree. We
 * inject a stub SSE source that drives the page's runtime transitions
 * via the `onEnded` / `onPipelineError` / `onConnectionError`
 * callbacks. The VoicePlayer itself is exercised in its own component
 * test file.
 *
 * AC coverage delegated here:
 *  - AC1 — page mounts, fetches today, and creates an SSE source
 *          (smoke: factory invoked exactly once).
 *  - AC2 — audio completes → router.push('/tarot/end').
 *  - AC3 — TTS pipeline error → subtitle-only banner renders.
 *
 * A11y is covered by a tiny axe-core scan over the loading shell only,
 * so we don't drag MSE / audio nodes into jsdom.
 */
import { act, cleanup, render, screen, waitFor } from "@testing-library/react";
import { axe, toHaveNoViolations } from "jest-axe";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

expect.extend(toHaveNoViolations);

const pushMock = vi.fn();
const replaceMock = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: pushMock, replace: replaceMock }),
  useSearchParams: () => new URLSearchParams(),
}));

// Stub the VoicePlayer so we don't drag the MSE / audio tree into
// jsdom. The component test for VoicePlayer (ISSUE-033) already covers
// the player's own AC1..AC5.
vi.mock("@/components/audio", () => ({
  VoicePlayer: ({
    onEnded,
    ariaLabel,
  }: {
    onEnded?: () => void;
    ariaLabel?: string;
  }) => (
    <section
      aria-label={ariaLabel}
      data-testid="voice-player-stub"
      data-status="streaming"
    >
      <button
        type="button"
        data-testid="player-end-trigger"
        onClick={() => onEnded?.()}
      >
        end
      </button>
    </section>
  ),
}));

import TarotPlayClient from "@/app/tarot/play/PlayClient";
import type { ChunkEvent, ChunkEventSource } from "@/lib/audio/events";
import type { PipelineErrorEvent } from "@/lib/audio/sse-source";
import type { TarotTodayResponse } from "@/lib/api/tarot";

/** Build a stable, never-completing source so the page can mount. */
function neverEndingSource(): ChunkEventSource & { close: () => void } {
  let closed = false;
  return {
    [Symbol.asyncIterator]: () => ({
      next: async (): Promise<IteratorResult<ChunkEvent>> => {
        // Wait forever — the test exercises the page via callbacks, not
        // the iterator stream itself.
        await new Promise<void>((resolve) => {
          if (closed) resolve();
          // never resolves otherwise — test will close the source
          // when render unmounts.
        });
        return { value: undefined as unknown as ChunkEvent, done: true };
      },
    }),
    close: () => {
      closed = true;
    },
  };
}

function mockFetchTodayOk(
  overrides: Partial<TarotTodayResponse> = {},
): () => Promise<TarotTodayResponse> {
  return async () => ({
    card_index: 0,
    card_name: "바보",
    card_art_url: "/api/v1/tarot/cards/0/art",
    free_remaining: 1,
    requires_payment: false,
    is_subscriber: false,
    ...overrides,
  });
}

afterEach(() => {
  cleanup();
  pushMock.mockReset();
  replaceMock.mockReset();
});

beforeEach(() => {
  pushMock.mockReset();
  replaceMock.mockReset();
});

describe("/tarot/play page — Screen 13", () => {
  it("AC1 — mounts, fetches today, and creates an SSE source", async () => {
    const sseFactory = vi.fn(() => neverEndingSource());

    await act(async () => {
      render(
        <TarotPlayClient
          fetchToday={mockFetchTodayOk()}
          sseSourceFactory={sseFactory}
        />,
      );
    });

    // Card metadata flows into the side panel.
    await waitFor(() => {
      expect(screen.getByTestId("card-name")).toHaveTextContent("바보");
    });
    // The SSE factory is invoked exactly once on the streaming
    // transition — page never re-creates the source on re-render.
    expect(sseFactory).toHaveBeenCalledTimes(1);
    // Player column is mounted with our stub.
    expect(screen.getByTestId("voice-player-stub")).toBeInTheDocument();
  });

  it("AC2 — audio completion routes to /tarot/end", async () => {
    const sseFactory = vi.fn(() => neverEndingSource());

    await act(async () => {
      render(
        <TarotPlayClient
          fetchToday={mockFetchTodayOk()}
          sseSourceFactory={sseFactory}
        />,
      );
    });
    await waitFor(() => {
      expect(screen.getByTestId("voice-player-stub")).toBeInTheDocument();
    });

    // Simulate the VoicePlayer's onEnded firing.
    await act(async () => {
      screen.getByTestId("player-end-trigger").click();
    });

    expect(pushMock).toHaveBeenCalledWith("/tarot/end");
  });

  it("AC3 — pipeline error surfaces the FR-034 banner", async () => {
    // Capture the onPipelineError callback so we can fire it ourselves.
    let capturedOnError: ((err: PipelineErrorEvent) => void) | null = null;
    const sseFactory = vi.fn(
      (opts: {
        onPipelineError: (err: PipelineErrorEvent) => void;
        onConnectionError: () => void;
      }) => {
        capturedOnError = opts.onPipelineError;
        return neverEndingSource();
      },
    );

    await act(async () => {
      render(
        <TarotPlayClient
          fetchToday={mockFetchTodayOk()}
          sseSourceFactory={sseFactory}
        />,
      );
    });
    await waitFor(() => {
      expect(screen.getByTestId("voice-player-stub")).toBeInTheDocument();
    });

    // Fire a TTS failure event into the page's onPipelineError callback.
    expect(capturedOnError).not.toBeNull();
    await act(async () => {
      capturedOnError!({
        type: "pipeline_error",
        reason: "tts_failure",
      });
    });

    // Banner copy mirrors ux_spec Screen 13's TTS-fail caption (which
    // overrides FR-034 with a tarot-specific message).
    expect(screen.getByTestId("pipeline-err-banner")).toHaveTextContent(
      "노인 도사의 풀이가 잠시 없어. 카드 의미만 봐.",
    );
  });

  it("redirects to /tarot/paywall when GET /today returns requires_payment", async () => {
    const sseFactory = vi.fn(() => neverEndingSource());

    await act(async () => {
      render(
        <TarotPlayClient
          fetchToday={mockFetchTodayOk({
            requires_payment: true,
            free_remaining: 0,
          })}
          sseSourceFactory={sseFactory}
        />,
      );
    });

    await waitFor(() => {
      expect(replaceMock).toHaveBeenCalledWith("/tarot/paywall");
    });
    // The SSE source should never have been created — we bounced out
    // before the streaming transition.
    expect(sseFactory).not.toHaveBeenCalled();
  });

  it("renders the network-error shell when fetchToday throws", async () => {
    const sseFactory = vi.fn(() => neverEndingSource());
    const failingFetch = async () => {
      throw new Error("offline");
    };

    await act(async () => {
      render(
        <TarotPlayClient
          fetchToday={failingFetch}
          sseSourceFactory={sseFactory}
        />,
      );
    });

    await waitFor(() => {
      expect(
        screen.getByTestId("tarot-play-network-error"),
      ).toBeInTheDocument();
    });
    expect(sseFactory).not.toHaveBeenCalled();
  });

  it("loading shell has no axe violations", async () => {
    // Render the page but never resolve the fetch — the loading shell
    // is what's on screen. Limits jsdom MSE risk per the ISSUE-042 OOM
    // lesson.
    const pending: Promise<TarotTodayResponse> = new Promise(() => {});
    const { container } = render(
      <TarotPlayClient
        fetchToday={() => pending}
        sseSourceFactory={() => neverEndingSource()}
      />,
    );

    expect(screen.getByTestId("tarot-play-loading")).toBeInTheDocument();
    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });
});
