/**
 * Unit tests for `ChunkedPlayer` (ISSUE-033).
 *
 * Covers:
 *   - AC1 — multiple `audio_ready` chunks land in MSE via appendBuffer.
 *   - AC3 — pause() stops audio without losing buffered state.
 *   - AC4 — replay() resets currentTime to 0 and re-arms play().
 *   - AC5 — no first chunk within timeout → status = `fallback_timeout`.
 *   - End-of-stream finalisation only after all chunks drain.
 *
 * We deliberately do NOT exercise the real browser MediaSource — jsdom
 * doesn't define it. Instead we inject `FakeMediaSource` and a synthetic
 * fetcher.
 */

import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  ChunkedPlayer,
  type ChunkFetcher,
  type PlayerStatus,
} from "@/lib/audio/chunked-player";
import { makeFakeMediaSourceFactory } from "./fake-media-source";

function makeBuffer(label: string): ArrayBuffer {
  // The test never inspects bytes — a 4-byte buffer is enough to assert
  // that `appendBuffer` received the right chunk in order.
  const enc = new TextEncoder().encode(label.padEnd(4, "x").slice(0, 4));
  return enc.buffer;
}

/**
 * Mutable shape of the test fake. We expose the writable subset
 * separately from the cast `HTMLAudioElement` because some real DOM
 * properties (like `paused`) are read-only on the spec interface.
 */
interface FakeAudio {
  src: string;
  currentTime: number;
  paused: boolean;
  play: ReturnType<typeof vi.fn>;
  pause: ReturnType<typeof vi.fn>;
}

function fakeAudioElement(): HTMLAudioElement & FakeAudio {
  // We avoid `document.createElement('audio')` because jsdom's
  // HTMLMediaElement is intentionally degraded. A plain object with the
  // properties the player touches is enough.
  const a: FakeAudio = {
    src: "",
    currentTime: 0,
    paused: true,
    play: vi.fn(() => {
      a.paused = false;
      return Promise.resolve();
    }),
    pause: vi.fn(() => {
      a.paused = true;
    }),
  };
  return a as unknown as HTMLAudioElement & FakeAudio;
}

function makeFetcher(
  map: Record<string, ArrayBuffer>,
): ChunkFetcher & { calls: string[] } {
  const calls: string[] = [];
  const fetcher = (url: string) => {
    calls.push(url);
    const buf = map[url];
    if (!buf) return Promise.reject(new Error("no fixture for " + url));
    return Promise.resolve(buf);
  };
  (fetcher as ChunkFetcher & { calls: string[] }).calls = calls;
  return fetcher as ChunkFetcher & { calls: string[] };
}

describe("ChunkedPlayer — AC1 progressive playback", () => {
  beforeEach(() => {
    vi.useRealTimers();
  });

  it("appends each audio_ready chunk into the MSE source buffer in order", async () => {
    const { factory, fake } = makeFakeMediaSourceFactory();
    const buf0 = makeBuffer("aaaa");
    const buf1 = makeBuffer("bbbb");
    const buf2 = makeBuffer("cccc");
    const fetcher = makeFetcher({
      "https://r2/chunk-0.mp3": buf0,
      "https://r2/chunk-1.mp3": buf1,
      "https://r2/chunk-2.mp3": buf2,
    });

    const statuses: PlayerStatus[] = [];
    const appended: number[] = [];
    const player = new ChunkedPlayer({
      audioElement: fakeAudioElement(),
      mediaSourceFactory: factory,
      fetcher,
      onStatusChange: (s) => statuses.push(s),
      onChunkAppended: (seq) => appended.push(seq),
    });

    // Allow the sourceopen microtask to fire so the source buffer is
    // attached before chunks land.
    await Promise.resolve();
    await Promise.resolve();

    await player.handleAudioReady({
      type: "audio_ready",
      url: "https://r2/chunk-0.mp3",
      seq: 0,
    });
    // Microtask flush for updateend.
    await Promise.resolve();
    await Promise.resolve();
    await player.handleAudioReady({
      type: "audio_ready",
      url: "https://r2/chunk-1.mp3",
      seq: 1,
    });
    await Promise.resolve();
    await Promise.resolve();
    await player.handleAudioReady({
      type: "audio_ready",
      url: "https://r2/chunk-2.mp3",
      seq: 2,
    });
    await Promise.resolve();
    await Promise.resolve();

    const sb = fake.sourceBuffers[0];
    expect(sb).toBeDefined();
    expect(sb.appended).toHaveLength(3);
    expect(sb.appended[0]).toBe(buf0);
    expect(sb.appended[1]).toBe(buf1);
    expect(sb.appended[2]).toBe(buf2);
    expect(appended).toEqual([0, 1, 2]);
    expect(statuses).toContain("playing");
    player.dispose();
  });

  it("buffers out-of-order chunks until the missing seq arrives", async () => {
    const { factory, fake } = makeFakeMediaSourceFactory();
    const buf0 = makeBuffer("0");
    const buf1 = makeBuffer("1");
    const buf2 = makeBuffer("2");
    const fetcher = makeFetcher({
      u0: buf0,
      u1: buf1,
      u2: buf2,
    });

    const player = new ChunkedPlayer({
      audioElement: fakeAudioElement(),
      mediaSourceFactory: factory,
      fetcher,
    });
    await Promise.resolve();
    await Promise.resolve();

    // Arrive 0, 2, 1. The player should hold 2 until 1 lands.
    await player.handleAudioReady({ type: "audio_ready", url: "u0", seq: 0 });
    await Promise.resolve();
    await Promise.resolve();
    await player.handleAudioReady({ type: "audio_ready", url: "u2", seq: 2 });
    await Promise.resolve();
    await Promise.resolve();
    const sb = fake.sourceBuffers[0];
    expect(sb.appended).toHaveLength(1);
    expect(sb.appended[0]).toBe(buf0);

    await player.handleAudioReady({ type: "audio_ready", url: "u1", seq: 1 });
    await Promise.resolve();
    await Promise.resolve();
    await Promise.resolve();
    await Promise.resolve();
    expect(sb.appended).toEqual([buf0, buf1, buf2]);
    player.dispose();
  });
});

describe("ChunkedPlayer — AC3/AC4 controls", () => {
  it("pause() halts the audio element and surfaces `paused` status", async () => {
    const { factory } = makeFakeMediaSourceFactory();
    const audio = fakeAudioElement();
    const fetcher = makeFetcher({ u: makeBuffer("x") });
    const player = new ChunkedPlayer({
      audioElement: audio,
      mediaSourceFactory: factory,
      fetcher,
    });
    await Promise.resolve();
    await Promise.resolve();
    await player.handleAudioReady({ type: "audio_ready", url: "u", seq: 0 });
    await Promise.resolve();
    await Promise.resolve();
    // Audio element is in `playing` after first chunk; the player calls
    // play() implicitly only on resume — but our fake starts paused.
    // Drive play() explicitly so pause() has something to halt.
    audio.paused = false;
    player.pause();
    expect(audio.pause).toHaveBeenCalled();
    expect(player.getStatus()).toBe("paused");
    player.dispose();
  });

  it("replay() resets currentTime to 0 and calls play()", async () => {
    const { factory } = makeFakeMediaSourceFactory();
    const audio = fakeAudioElement();
    const fetcher = makeFetcher({ u: makeBuffer("x") });
    const player = new ChunkedPlayer({
      audioElement: audio,
      mediaSourceFactory: factory,
      fetcher,
    });
    await Promise.resolve();
    await Promise.resolve();
    audio.currentTime = 30;
    await player.replay();
    expect(audio.currentTime).toBe(0);
    expect(audio.play).toHaveBeenCalled();
    expect(player.getStatus()).toBe("playing");
    player.dispose();
  });
});

describe("ChunkedPlayer — AC5 first-chunk timeout (FR-034)", () => {
  it("transitions to `fallback_timeout` after the configured timeout when no chunk arrives", async () => {
    vi.useFakeTimers();
    const { factory } = makeFakeMediaSourceFactory();
    const fetcher = makeFetcher({});
    const statuses: PlayerStatus[] = [];
    const player = new ChunkedPlayer({
      audioElement: fakeAudioElement(),
      mediaSourceFactory: factory,
      fetcher,
      firstChunkTimeoutMs: 5000,
      onStatusChange: (s) => statuses.push(s),
    });
    // sourceopen microtask happens immediately; we are now in
    // `buffering`. Advance just shy of 5s — still buffering.
    await Promise.resolve();
    await Promise.resolve();
    vi.advanceTimersByTime(4999);
    expect(player.getStatus()).toBe("buffering");
    // Cross the threshold.
    vi.advanceTimersByTime(2);
    expect(player.getStatus()).toBe("fallback_timeout");
    expect(statuses).toContain("fallback_timeout");
    player.dispose();
    vi.useRealTimers();
  });

  it("cancels the timeout once the first chunk lands", async () => {
    vi.useFakeTimers();
    const { factory } = makeFakeMediaSourceFactory();
    const fetcher = makeFetcher({ u: makeBuffer("x") });
    const player = new ChunkedPlayer({
      audioElement: fakeAudioElement(),
      mediaSourceFactory: factory,
      fetcher,
      firstChunkTimeoutMs: 5000,
    });
    await Promise.resolve();
    await Promise.resolve();
    // Land a chunk at t=2s.
    vi.advanceTimersByTime(2000);
    await player.handleAudioReady({ type: "audio_ready", url: "u", seq: 0 });
    // Run all timers — if the timeout were still armed it would fire.
    vi.advanceTimersByTime(10000);
    expect(player.getStatus()).not.toBe("fallback_timeout");
    player.dispose();
    vi.useRealTimers();
  });
});

describe("ChunkedPlayer — end-of-stream", () => {
  it("calls endOfStream() only after all chunks have drained", async () => {
    const { factory, fake } = makeFakeMediaSourceFactory();
    const fetcher = makeFetcher({
      u0: makeBuffer("0"),
      u1: makeBuffer("1"),
    });
    const player = new ChunkedPlayer({
      audioElement: fakeAudioElement(),
      mediaSourceFactory: factory,
      fetcher,
    });
    await Promise.resolve();
    await Promise.resolve();

    // Fire-and-forget a chunk so the player has a pending fetch in flight
    // when handleEnd() arrives. We intentionally do NOT await it so the
    // chunk hasn't reached the source buffer at the moment handleEnd()
    // runs — endOfStream() must defer until the chunk drains.
    const inFlight = player.handleAudioReady({
      type: "audio_ready",
      url: "u0",
      seq: 0,
    });
    // Server signals end-of-stream while chunk-0 is mid-fetch.
    player.handleEnd();
    expect(fake.endOfStreamCalls).toBe(0);

    await inFlight;
    await Promise.resolve();
    await Promise.resolve();
    // u1 lands after end was signalled. The player still drains it
    // because end-of-stream is interpreted as "no further events" —
    // any chunk already in-flight before end was processed is honoured.
    await player.handleAudioReady({ type: "audio_ready", url: "u1", seq: 1 });
    await Promise.resolve();
    await Promise.resolve();
    await Promise.resolve();
    expect(fake.endOfStreamCalls).toBe(1);
    expect(player.getStatus()).toBe("ended");
    player.dispose();
  });
});
