/**
 * Minimal fake MSE implementation for unit tests (ISSUE-033).
 *
 * jsdom does NOT implement `MediaSource`/`SourceBuffer`. Rather than
 * pulling in a heavyweight polyfill we model only the slice of the API
 * `ChunkedPlayer` touches:
 *
 *   - `addEventListener('sourceopen', cb)` — we fire it synchronously
 *     in the next microtask so the player resolves `sourceOpenPromise`.
 *   - `addSourceBuffer(mime)` → returns a `FakeSourceBuffer`.
 *   - `endOfStream()` — marks `readyState = 'ended'` and records the call.
 *   - `readyState` — toggles `closed` → `open` → `ended`.
 *
 * `FakeSourceBuffer` records every `appendBuffer` call (data + order) so
 * tests can assert AC1 ("MSE appends them and playback continues
 * seamlessly") without driving the real browser MSE pipeline.
 *
 * `updateend` fires synchronously after every successful `appendBuffer`
 * so the player's drain loop can advance to the next chunk.
 */

import type {
  MediaSourceLike,
  SourceBufferLike,
} from "@/lib/audio/chunked-player";

type Listener = (event: Event) => void;
type OpenListener = () => void;

export class FakeSourceBuffer implements SourceBufferLike {
  updating = false;
  readonly appended: ArrayBuffer[] = [];
  readonly mime: string;
  private updateendListeners: Listener[] = [];
  private errorListeners: Listener[] = [];
  /**
   * Tests can flip this to `true` to make the NEXT appendBuffer throw,
   * simulating a codec/quota error.
   */
  failNextAppend = false;

  constructor(mime: string) {
    this.mime = mime;
  }

  appendBuffer(data: ArrayBuffer): void {
    if (this.failNextAppend) {
      this.failNextAppend = false;
      // The real API throws synchronously for QuotaExceededError, etc.
      throw new Error("fake appendBuffer error");
    }
    this.appended.push(data);
    this.updating = true;
    // Fire updateend synchronously in a microtask so we mirror the real
    // browser behaviour (the spec says it fires in a task; for tests
    // synchronous is good enough and keeps the assertions linear).
    queueMicrotask(() => {
      this.updating = false;
      for (const listener of this.updateendListeners) {
        listener(new Event("updateend"));
      }
    });
  }

  addEventListener(type: "updateend" | "error", listener: Listener): void {
    if (type === "updateend") this.updateendListeners.push(listener);
    else if (type === "error") this.errorListeners.push(listener);
  }

  removeEventListener(type: "updateend" | "error", listener: Listener): void {
    if (type === "updateend") {
      this.updateendListeners = this.updateendListeners.filter(
        (l) => l !== listener,
      );
    } else if (type === "error") {
      this.errorListeners = this.errorListeners.filter((l) => l !== listener);
    }
  }

  /** Manually fire an error event (test helper). */
  fireError(): void {
    for (const listener of this.errorListeners) {
      listener(new Event("error"));
    }
  }
}

export class FakeMediaSource implements MediaSourceLike {
  readyState: "closed" | "open" | "ended" = "closed";
  readonly sourceBuffers: FakeSourceBuffer[] = [];
  endOfStreamCalls = 0;
  private openListeners: OpenListener[] = [];

  addEventListener(type: "sourceopen", listener: OpenListener): void {
    if (type === "sourceopen") {
      this.openListeners.push(listener);
      // If we're already open (rare) fire immediately for the new
      // listener; otherwise transition open in a microtask so the
      // sequence mirrors the real spec.
      if (this.readyState !== "open") {
        queueMicrotask(() => {
          if (this.readyState === "closed") {
            this.readyState = "open";
          }
          listener();
        });
      } else {
        listener();
      }
    }
  }

  addSourceBuffer(mime: string): FakeSourceBuffer {
    const sb = new FakeSourceBuffer(mime);
    this.sourceBuffers.push(sb);
    return sb;
  }

  endOfStream(): void {
    this.endOfStreamCalls += 1;
    this.readyState = "ended";
  }
}

/**
 * Returns a fresh `MediaSourceFactory` + the raw fake so tests can poke
 * `appendBuffer` records, flip error flags, etc.
 */
export function makeFakeMediaSourceFactory(): {
  factory: () => { mediaSource: MediaSourceLike; objectUrl: string };
  fake: FakeMediaSource;
} {
  const fake = new FakeMediaSource();
  const factory = () => ({
    mediaSource: fake as MediaSourceLike,
    objectUrl: "blob:fake-mediasource",
  });
  return { factory, fake };
}
