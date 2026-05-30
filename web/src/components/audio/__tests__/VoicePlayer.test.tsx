/**
 * Component tests for `<VoicePlayer>` (ISSUE-033).
 *
 * Covers all five ACs end-to-end at the React component layer:
 *   AC1 — `audio_ready` chunks flow into MSE via the player.
 *   AC2 — subtitle band updates within 500ms of audio offset.
 *   AC3 — pause button stops audio and freezes subtitle.
 *   AC4 — replay button resets the player + subtitle sync to 0.
 *   AC5 — no first chunk within 5s → FR-034 banner + subtitle-only mode.
 *
 * jsdom doesn't implement MSE so we inject `FakeMediaSource` via the
 * `mediaSourceFactory` prop. We also inject a synthetic `fetcher` to
 * avoid hitting the network.
 */

import { describe, expect, it, vi } from "vitest";
import { act, fireEvent, render, screen } from "@testing-library/react";
import { useMemo } from "react";
import {
  FR_034_BANNER_TEXT,
  VoicePlayer,
} from "@/components/audio/VoicePlayer";
import type {
  AudioReadyEvent,
  ChunkEvent,
  SubtitleEvent,
} from "@/lib/audio/events";
import { makeFakeMediaSourceFactory } from "@/lib/audio/__tests__/fake-media-source";

/**
 * A controllable async iterable. Tests push events via `emit()` and
 * close the stream via `end()`. The component's `for await` loop sees
 * each event in order.
 */
function makeControlledSource(): {
  source: AsyncIterable<ChunkEvent>;
  emit: (ev: ChunkEvent) => void;
  end: () => void;
} {
  const queue: ChunkEvent[] = [];
  let resolveWaiter: (() => void) | null = null;
  let closed = false;
  const wait = () => {
    return new Promise<void>((resolve) => {
      if (queue.length > 0 || closed) {
        resolve();
        return;
      }
      resolveWaiter = resolve;
    });
  };
  const source: AsyncIterable<ChunkEvent> = {
    [Symbol.asyncIterator]: () => ({
      next: async () => {
        while (queue.length === 0 && !closed) {
          await wait();
        }
        if (queue.length > 0) {
          return { value: queue.shift()!, done: false };
        }
        return { value: undefined, done: true };
      },
    }),
  };
  const emit = (ev: ChunkEvent) => {
    queue.push(ev);
    const r = resolveWaiter;
    resolveWaiter = null;
    if (r) r();
  };
  const end = () => {
    closed = true;
    const r = resolveWaiter;
    resolveWaiter = null;
    if (r) r();
  };
  return { source, emit, end };
}

function audioReady(seq: number, url: string): AudioReadyEvent {
  return { type: "audio_ready", url, seq };
}
function subtitle(
  seq: number,
  text: string,
  audio_offset_ms: number,
): SubtitleEvent {
  return { type: "subtitle", seq, text, audio_offset_ms };
}

function syntheticBuffer(label: string): ArrayBuffer {
  return new TextEncoder().encode(label).buffer;
}

/**
 * Wrapper that stabilises the `source` so the component's mount-once
 * effect doesn't see a new identity on each render.
 */
function Harness(props: {
  source: AsyncIterable<ChunkEvent>;
  mediaSourceFactory: ReturnType<typeof makeFakeMediaSourceFactory>["factory"];
  fetcher: (url: string) => Promise<ArrayBuffer>;
  firstChunkTimeoutMs?: number;
  onLagMeasured?: (info: {
    seq: number;
    text: string;
    offset_ms: number;
    measured_lag_ms: number;
  }) => void;
}) {
  const memoSource = useMemo(() => props.source, [props.source]);
  return (
    <VoicePlayer
      source={memoSource}
      mediaSourceFactory={props.mediaSourceFactory}
      fetcher={props.fetcher}
      firstChunkTimeoutMs={props.firstChunkTimeoutMs}
      onLagMeasured={props.onLagMeasured}
    />
  );
}

describe("<VoicePlayer /> — AC1 chunked playback", () => {
  it("appends each audio_ready chunk into the fake MSE source buffer", async () => {
    const { factory, fake } = makeFakeMediaSourceFactory();
    const fetcher = vi.fn(async (url: string) => syntheticBuffer(url));
    const { source, emit, end } = makeControlledSource();

    render(
      <Harness
        source={source}
        mediaSourceFactory={factory}
        fetcher={fetcher}
      />,
    );

    // Wait for sourceopen + initial render.
    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });

    await act(async () => {
      emit(audioReady(0, "chunk-0"));
      await Promise.resolve();
      await Promise.resolve();
      await Promise.resolve();
      emit(audioReady(1, "chunk-1"));
      await Promise.resolve();
      await Promise.resolve();
      await Promise.resolve();
      emit(audioReady(2, "chunk-2"));
      await Promise.resolve();
      await Promise.resolve();
      await Promise.resolve();
      end();
      await Promise.resolve();
    });

    expect(fetcher).toHaveBeenCalledTimes(3);
    const sb = fake.sourceBuffers[0];
    expect(sb).toBeDefined();
    expect(sb.appended).toHaveLength(3);
    // Player should be in `playing` after the first chunk, before end.
    const player = screen.getByTestId("voice-player");
    expect(["playing", "ended"]).toContain(player.getAttribute("data-status"));
  });
});

describe("<VoicePlayer /> — AC2 subtitle sync (NFR-015)", () => {
  it("renders the active subtitle within 500ms of the audio offset", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: false });
    const { factory } = makeFakeMediaSourceFactory();
    const fetcher = vi.fn(async (url: string) => syntheticBuffer(url));
    const { source, emit } = makeControlledSource();

    const lagSamples: number[] = [];
    render(
      <Harness
        source={source}
        mediaSourceFactory={factory}
        fetcher={fetcher}
        onLagMeasured={(info) => lagSamples.push(info.measured_lag_ms)}
      />,
    );

    // Subtitle stream arrives ahead of the playhead.
    await act(async () => {
      emit(subtitle(0, "안녕하세요", 0));
      emit(subtitle(1, "오늘은 무엇이 궁금해", 1000));
      emit(subtitle(2, "들려드릴게요", 3000));
      await vi.advanceTimersByTimeAsync(50);
    });

    // Start: line 0 should be on screen.
    expect(screen.getByTestId("subtitle-band")).toHaveTextContent("안녕하세요");

    // Pump audio_ready so the player transitions to `playing` and the
    // sync engine starts polling.
    await act(async () => {
      emit(audioReady(0, "chunk-0"));
      await vi.advanceTimersByTimeAsync(50);
    });

    // The sync engine's clock comes from the audio element's
    // `currentTime`. We can't drive that directly inside jsdom, so we
    // fake it by manually advancing `currentTime` and the polling tick.
    const audioEl = screen.getByTestId(
      "player-audio",
    ) as unknown as HTMLAudioElement;
    Object.defineProperty(audioEl, "currentTime", {
      configurable: true,
      value: 1,
    });
    // Tick once (100ms cadence).
    await act(async () => {
      await vi.advanceTimersByTimeAsync(100);
    });
    expect(screen.getByTestId("subtitle-band")).toHaveTextContent(
      "오늘은 무엇이 궁금해",
    );

    Object.defineProperty(audioEl, "currentTime", {
      configurable: true,
      value: 3,
    });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(100);
    });
    expect(screen.getByTestId("subtitle-band")).toHaveTextContent(
      "들려드릴게요",
    );

    // NFR-015 lag budget assertion: every observed lag is ≤ 500ms.
    for (const lag of lagSamples) {
      expect(lag).toBeLessThanOrEqual(500);
    }
    vi.useRealTimers();
  });
});

describe("<VoicePlayer /> — AC3 pause / AC4 replay controls", () => {
  it("pause button stops audio and freezes the subtitle", async () => {
    const { factory } = makeFakeMediaSourceFactory();
    const fetcher = vi.fn(async (url: string) => syntheticBuffer(url));
    const { source, emit } = makeControlledSource();
    render(
      <Harness
        source={source}
        mediaSourceFactory={factory}
        fetcher={fetcher}
      />,
    );

    await act(async () => {
      emit(subtitle(0, "프리즈", 0));
      emit(audioReady(0, "chunk-0"));
      await Promise.resolve();
      await Promise.resolve();
      await Promise.resolve();
    });
    expect(screen.getByTestId("subtitle-band")).toHaveTextContent("프리즈");

    const pauseBtn = screen.getByTestId("pause-button");
    await act(async () => {
      fireEvent.click(pauseBtn);
      await Promise.resolve();
    });

    // After pause: status flips to `paused` (data attribute), play
    // button appears, subtitle text is preserved.
    const player = screen.getByTestId("voice-player");
    expect(player.getAttribute("data-status")).toBe("paused");
    expect(screen.getByTestId("subtitle-band")).toHaveTextContent("프리즈");
    expect(screen.getByTestId("play-button")).toBeInTheDocument();
  });

  it("replay button resets the subtitle to offset 0 and returns to playing state (AC4)", async () => {
    const { factory } = makeFakeMediaSourceFactory();
    const fetcher = vi.fn(async (url: string) => syntheticBuffer(url));
    const { source, emit } = makeControlledSource();
    render(
      <Harness
        source={source}
        mediaSourceFactory={factory}
        fetcher={fetcher}
      />,
    );

    await act(async () => {
      emit(audioReady(0, "chunk-0"));
      emit(subtitle(0, "처음", 0));
      emit(subtitle(1, "끝", 5000));
      await Promise.resolve();
      await Promise.resolve();
      await Promise.resolve();
    });

    // Simulate the playhead crossing line 1's offset. We use a
    // configurable+writable data descriptor so the player's own
    // `currentTime = 0` reset (in replay()) is still valid.
    const audioEl = screen.getByTestId(
      "player-audio",
    ) as unknown as HTMLAudioElement;
    Object.defineProperty(audioEl, "currentTime", {
      configurable: true,
      writable: true,
      value: 6,
    });
    // Wait for the next tick of the sync engine (100ms cadence).
    await new Promise((r) => setTimeout(r, 150));
    expect(screen.getByTestId("subtitle-band")).toHaveTextContent("끝");

    await act(async () => {
      fireEvent.click(screen.getByTestId("replay-button"));
      await Promise.resolve();
    });

    // Subtitle resets to the offset=0 line (AC4: "subtitle resets").
    expect(screen.getByTestId("subtitle-band")).toHaveTextContent("처음");
    // Player returns to the `playing` UI state (AC4: "audio restarts").
    const player = screen.getByTestId("voice-player");
    expect(player.getAttribute("data-status")).toBe("playing");
  });
});

describe("<VoicePlayer /> — AC5 first-chunk timeout (FR-034)", () => {
  it("shows the FR-034 banner and switches to subtitle-only mode after the timeout", async () => {
    vi.useFakeTimers();
    const { factory } = makeFakeMediaSourceFactory();
    const fetcher = vi.fn(async (url: string) => syntheticBuffer(url));
    const { source, emit } = makeControlledSource();
    render(
      <Harness
        source={source}
        mediaSourceFactory={factory}
        fetcher={fetcher}
        firstChunkTimeoutMs={5000}
      />,
    );

    // Subtitle arrives but audio never does.
    await act(async () => {
      emit(subtitle(0, "음성 없이도 풀이를 드릴게요", 0));
      await vi.advanceTimersByTimeAsync(50);
    });

    // Before timeout: banner is not visible.
    expect(screen.queryByTestId("fallback-banner")).not.toBeInTheDocument();

    // Advance past 5s.
    await act(async () => {
      await vi.advanceTimersByTimeAsync(5100);
    });

    expect(screen.getByTestId("fallback-banner")).toHaveTextContent(
      FR_034_BANNER_TEXT,
    );
    const player = screen.getByTestId("voice-player");
    expect(player.getAttribute("data-status")).toBe("subtitle_only");
    // Controls hidden in fallback (pause/play/replay all gone — there's
    // no audio to control).
    expect(screen.queryByTestId("pause-button")).not.toBeInTheDocument();
    expect(screen.queryByTestId("play-button")).not.toBeInTheDocument();
    expect(screen.queryByTestId("replay-button")).not.toBeInTheDocument();
    // Subtitle still rendered (NFR-015 + FR-034: text fallback = value).
    expect(screen.getByTestId("subtitle-band")).toHaveTextContent(
      "음성 없이도 풀이를 드릴게요",
    );
    vi.useRealTimers();
  });
});
