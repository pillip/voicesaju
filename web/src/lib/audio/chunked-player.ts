/**
 * MSE-based chunked audio player (ISSUE-033).
 *
 * Consumes `AudioReadyEvent` chunks from the SSE pipeline (ISSUE-039) and
 * appends them into a single `MediaSource` `SourceBuffer` so the browser
 * can play one continuous audio track. The pipeline produces mp3 chunks
 * (architecture §8.2) so we open the SourceBuffer with `audio/mpeg`.
 *
 * Why MSE and not just `<audio src=playlist.m3u8>`?
 *  - HLS-on-audio is desktop-Safari-only by default; we need iOS Safari +
 *    Chrome + Toss WebView coverage with a single code path.
 *  - The pipeline issues presigned URLs per sentence — there is no master
 *    manifest to point an `<audio>` at.
 *  - MSE lets us start playback the moment the first chunk lands without
 *    waiting for the rest, which is the NFR-002 budget (first audible
 *    byte ≤ 1.5s).
 *
 * What this module does NOT do:
 *  - Subtitle sync — see `subtitle-sync.ts`.
 *  - SSE subscription — that's ISSUE-039's adapter; we accept any
 *    `ChunkEventSource` (async iterable).
 *  - Refund / circuit-breaker logic — the React component owns UX policy
 *    around fallback; this module only emits the timeout signal.
 *
 * Testability:
 *  - jsdom does NOT implement `MediaSource`/`SourceBuffer`/`HTMLMediaElement`
 *    properly. The component wires this module up via the
 *    `createMediaSource` factory so tests can inject a `FakeMediaSource`
 *    that records `appendBuffer` calls + simulates `currentTime`.
 */

import type { AudioReadyEvent } from "./events";

/**
 * Default MIME used when the server omits it. mp3 over MSE is the
 * baseline path per architecture §8.2.
 */
export const DEFAULT_CHUNK_MIME = "audio/mpeg";

/**
 * Default timeout for the first chunk. FR-034 specifies 5s; once this
 * elapses the React component switches to subtitle-only mode.
 */
export const FIRST_CHUNK_TIMEOUT_MS = 5000;

/**
 * Minimal SourceBuffer surface we use. Captured as an interface so tests
 * can provide a fake without pulling DOM types into the test bundle.
 */
export interface SourceBufferLike {
  appendBuffer(data: ArrayBuffer): void;
  readonly updating: boolean;
  addEventListener(
    type: "updateend" | "error",
    listener: (event: Event) => void,
  ): void;
  removeEventListener(
    type: "updateend" | "error",
    listener: (event: Event) => void,
  ): void;
}

/**
 * Minimal MediaSource surface. We deliberately don't extend `MediaSource`
 * because jsdom doesn't define the global.
 */
export interface MediaSourceLike {
  readonly readyState: "closed" | "open" | "ended";
  addSourceBuffer(mime: string): SourceBufferLike;
  endOfStream(): void;
  addEventListener(type: "sourceopen", listener: () => void): void;
}

/**
 * Factory for constructing a `MediaSource`. Production wires this to the
 * browser's `new MediaSource()`; tests pass a fake. Returning a
 * `{ mediaSource, objectUrl }` tuple keeps the URL lifecycle owned by
 * the factory — production calls `URL.createObjectURL`, tests return a
 * stable sentinel string.
 */
export type MediaSourceFactory = () => {
  mediaSource: MediaSourceLike;
  objectUrl: string;
};

/**
 * Browser MediaSource factory. Used in production. Tests substitute their
 * own factory.
 *
 * Note: `MediaSource` is `undefined` in jsdom — calling this in a unit
 * test will throw. That's intentional; tests must inject a fake factory.
 */
export const createBrowserMediaSource: MediaSourceFactory = () => {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const ms = new (globalThis as any).MediaSource() as MediaSourceLike;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const objectUrl = (globalThis as any).URL.createObjectURL(ms) as string;
  return { mediaSource: ms, objectUrl };
};

/**
 * Fetcher signature for resolving a presigned URL into chunk bytes. We
 * accept a custom fetcher so the React component can swap in `fetch`
 * with credentials, retries, or an alt transport for the Toss WebView
 * context. Tests inject a fetcher that resolves with synthetic
 * `ArrayBuffer`s without going through the global `fetch`.
 */
export type ChunkFetcher = (url: string) => Promise<ArrayBuffer>;

/**
 * Default fetcher uses the platform `fetch`. Wrapped here so we can
 * centralise error semantics: anything non-2xx → throw.
 */
export const defaultChunkFetcher: ChunkFetcher = async (url) => {
  const res = await fetch(url);
  if (!res.ok) {
    throw new Error(`chunk fetch failed: ${res.status}`);
  }
  return res.arrayBuffer();
};

/**
 * Observable status the React component reads to decide which UX branch
 * to render.
 *
 * `idle`              — player constructed but no chunks have arrived.
 * `buffering`         — first chunk pending; FR-034 timer is running.
 * `playing`           — at least one chunk has been appended.
 * `paused`            — user-initiated pause.
 * `ended`             — server sent the `end` event AND all buffered
 *                       audio has played out.
 * `fallback_timeout`  — first chunk did not arrive within
 *                       `FIRST_CHUNK_TIMEOUT_MS`; AC5 + FR-034 fires.
 * `error`             — MSE source error or chunk fetch failure that
 *                       can't be skipped; component switches to
 *                       subtitle-only.
 */
export type PlayerStatus =
  | "idle"
  | "buffering"
  | "playing"
  | "paused"
  | "ended"
  | "fallback_timeout"
  | "error";

export interface ChunkedPlayerOptions {
  /** The HTMLAudioElement the player drives. */
  audioElement: HTMLAudioElement;
  /** MSE factory — defaults to `createBrowserMediaSource`. */
  mediaSourceFactory?: MediaSourceFactory;
  /** Chunk fetcher — defaults to `defaultChunkFetcher`. */
  fetcher?: ChunkFetcher;
  /** First-chunk timeout in ms — defaults to `FIRST_CHUNK_TIMEOUT_MS`. */
  firstChunkTimeoutMs?: number;
  /** Status observer called on every state transition. */
  onStatusChange?: (status: PlayerStatus) => void;
  /**
   * Called whenever a chunk has been successfully `appendBuffer`'d. Used
   * by tests + the subtitle scheduler to assert ordering.
   */
  onChunkAppended?: (seq: number) => void;
  /**
   * Inject a custom `setTimeout` (e.g. `vi.useFakeTimers()` already
   * patches the global, so this is rarely needed; included for tests
   * that want explicit control without faking the global).
   */
  setTimeoutFn?: (cb: () => void, ms: number) => unknown;
  /** Companion to `setTimeoutFn` for cancellation. */
  clearTimeoutFn?: (handle: unknown) => void;
}

/**
 * Construct a chunked player bound to an `<audio>` element. The caller is
 * responsible for calling `feedEvents()` with the SSE event stream and
 * `dispose()` when unmounting.
 */
export class ChunkedPlayer {
  private status: PlayerStatus = "idle";
  private statusObserver?: (status: PlayerStatus) => void;
  private onChunkAppended?: (seq: number) => void;
  private audio: HTMLAudioElement;
  private mediaSource: MediaSourceLike | null = null;
  private sourceBuffer: SourceBufferLike | null = null;
  private pendingChunks: { seq: number; data: ArrayBuffer }[] = [];
  private appendInFlight = false;
  private firstChunkTimer: unknown = null;
  private firstChunkTimeoutMs: number;
  private mediaSourceFactory: MediaSourceFactory;
  private fetcher: ChunkFetcher;
  private setTimeoutFn: (cb: () => void, ms: number) => unknown;
  private clearTimeoutFn: (handle: unknown) => void;
  private disposed = false;
  private sourceOpenPromise: Promise<void>;
  private resolveSourceOpen!: () => void;
  private endRequested = false;
  private highestSeqAppended = -1;
  private nextExpectedSeq = 0;
  /**
   * Count of `handleAudioReady` calls currently awaiting their fetcher
   * promise (i.e. NOT yet visible in `pendingChunks`). We use this so
   * `handleEnd()` can correctly defer `endOfStream()` when chunks are
   * still being fetched.
   */
  private fetchesInFlight = 0;

  constructor(options: ChunkedPlayerOptions) {
    this.audio = options.audioElement;
    this.mediaSourceFactory =
      options.mediaSourceFactory ?? createBrowserMediaSource;
    this.fetcher = options.fetcher ?? defaultChunkFetcher;
    this.statusObserver = options.onStatusChange;
    this.onChunkAppended = options.onChunkAppended;
    this.firstChunkTimeoutMs =
      options.firstChunkTimeoutMs ?? FIRST_CHUNK_TIMEOUT_MS;
    // Default to platform setTimeout but accept overrides. We bind the
    // global to avoid `this` leaks in some browsers.
    this.setTimeoutFn =
      options.setTimeoutFn ??
      ((cb, ms) => globalThis.setTimeout(cb, ms) as unknown);
    this.clearTimeoutFn =
      options.clearTimeoutFn ??
      ((handle) =>
        globalThis.clearTimeout(handle as ReturnType<typeof setTimeout>));

    this.sourceOpenPromise = new Promise((resolve) => {
      this.resolveSourceOpen = resolve;
    });
    this.attachMediaSource();
    this.startFirstChunkTimer();
  }

  /** Current status snapshot. */
  getStatus(): PlayerStatus {
    return this.status;
  }

  /**
   * Pause playback (AC3). Subtitle freezing is the subtitle scheduler's
   * responsibility — it observes `audio.paused`.
   */
  pause(): void {
    if (this.disposed) return;
    // We don't early-return on `this.audio.paused` because jsdom's
    // HTMLMediaElement always reports `paused === true` (there's no
    // real playback). The DOM `pause()` is idempotent so calling it
    // even when already paused is safe.
    this.audio.pause();
    this.transitionTo("paused");
  }

  /**
   * Resume playback after a pause. The audio element retains the last
   * `currentTime` so playback continues from the pause point.
   */
  play(): Promise<void> {
    if (this.disposed) return Promise.resolve();
    const result = this.audio.play();
    this.transitionTo("playing");
    // play() returns a Promise in modern browsers; cast for older
    // typings that returned void.
    return result instanceof Promise ? result : Promise.resolve();
  }

  /**
   * Restart playback from offset 0 (AC4). Subtitle reset is the subtitle
   * scheduler's job — it observes `currentTime` resets.
   */
  replay(): Promise<void> {
    if (this.disposed) return Promise.resolve();
    this.audio.currentTime = 0;
    const result = this.audio.play();
    this.transitionTo("playing");
    return result instanceof Promise ? result : Promise.resolve();
  }

  /**
   * Consume an entire `ChunkEventSource` until completion. The component
   * fires this once on mount; cancellation happens via `dispose()`.
   */
  async feedEvents(source: AsyncIterable<{ type: string }>): Promise<void> {
    for await (const ev of source) {
      if (this.disposed) return;
      if (ev.type === "audio_ready") {
        await this.handleAudioReady(ev as unknown as AudioReadyEvent);
      } else if (ev.type === "end") {
        this.handleEnd();
      }
      // `subtitle` events are handled by the subtitle scheduler — the
      // player only needs `audio_ready` + `end`.
    }
  }

  /**
   * Push a single audio chunk into the buffer. Public so tests can drive
   * directly without an async iterable.
   */
  async handleAudioReady(ev: AudioReadyEvent): Promise<void> {
    if (this.disposed) return;
    this.fetchesInFlight += 1;
    try {
      const data = await this.fetcher(ev.url);
      this.pendingChunks.push({ seq: ev.seq, data });
      // Sort by seq so out-of-order arrival lands in order.
      this.pendingChunks.sort((a, b) => a.seq - b.seq);
      // Cancel the timeout the moment the first chunk lands.
      if (this.firstChunkTimer !== null) {
        this.clearTimeoutFn(this.firstChunkTimer);
        this.firstChunkTimer = null;
      }
      await this.drainPending();
    } catch (err) {
      // Per-chunk failure: surface error status, but do not throw —
      // the React component decides whether to fall back fully or skip
      // this one chunk. M2 policy is "fall back".
      this.transitionTo("error");
      // eslint-disable-next-line no-console
      console.warn("[chunked-player] chunk fetch failed", ev.seq, err);
    } finally {
      this.fetchesInFlight -= 1;
      // If end was requested while this fetch was in flight, give the
      // drainer another chance now that pendingChunks may be populated.
      if (this.endRequested) {
        void this.drainPending();
      }
    }
  }

  /**
   * Server signalled end-of-stream. We close the MediaSource only after
   * all buffered chunks have drained, otherwise the tail of audio gets
   * truncated.
   */
  handleEnd(): void {
    this.endRequested = true;
    // Defer if any chunk is mid-fetch, mid-append, or queued. The
    // drainer + the fetcher's `finally` block will re-call into the
    // finalize path the moment the last chunk lands.
    if (
      this.pendingChunks.length === 0 &&
      !this.appendInFlight &&
      this.fetchesInFlight === 0
    ) {
      this.finalize();
    }
  }

  /**
   * Cleanup: stop timers, release the object URL, detach listeners.
   * Idempotent.
   */
  dispose(): void {
    if (this.disposed) return;
    this.disposed = true;
    if (this.firstChunkTimer !== null) {
      this.clearTimeoutFn(this.firstChunkTimer);
      this.firstChunkTimer = null;
    }
    // We don't aggressively endOfStream here — the React component owns
    // the lifecycle (unmounting the <audio> is sufficient).
  }

  // --- internal ---------------------------------------------------------

  private attachMediaSource(): void {
    try {
      const { mediaSource, objectUrl } = this.mediaSourceFactory();
      this.mediaSource = mediaSource;
      this.audio.src = objectUrl;
      mediaSource.addEventListener("sourceopen", () => {
        try {
          this.sourceBuffer = mediaSource.addSourceBuffer(DEFAULT_CHUNK_MIME);
          this.sourceBuffer.addEventListener("updateend", () => {
            this.appendInFlight = false;
            void this.drainPending();
          });
          this.sourceBuffer.addEventListener("error", () => {
            this.transitionTo("error");
          });
          this.resolveSourceOpen();
        } catch (err) {
          this.transitionTo("error");
          // eslint-disable-next-line no-console
          console.warn("[chunked-player] addSourceBuffer failed", err);
        }
      });
    } catch (err) {
      // jsdom or unsupported browser: fall straight to error so the
      // React component renders the subtitle-only branch.
      this.transitionTo("error");
      // eslint-disable-next-line no-console
      console.warn("[chunked-player] MediaSource init failed", err);
    }
  }

  private startFirstChunkTimer(): void {
    this.transitionTo("buffering");
    this.firstChunkTimer = this.setTimeoutFn(() => {
      // If we reached this point the first chunk never landed; AC5.
      if (
        this.status === "buffering" ||
        this.status === "idle" ||
        this.status === "error"
      ) {
        this.transitionTo("fallback_timeout");
      }
    }, this.firstChunkTimeoutMs);
  }

  private async drainPending(): Promise<void> {
    if (this.appendInFlight) return;
    if (!this.sourceBuffer) {
      // Wait for sourceopen to fire.
      await this.sourceOpenPromise;
      if (this.disposed) return;
      if (!this.sourceBuffer) return;
    }
    while (this.pendingChunks.length > 0) {
      const head = this.pendingChunks[0];
      // Out-of-order guard: hold chunks until the expected seq lands.
      // This keeps MSE's strictly-sequential buffer contract happy.
      if (head.seq !== this.nextExpectedSeq) break;
      this.pendingChunks.shift();
      this.appendInFlight = true;
      try {
        this.sourceBuffer.appendBuffer(head.data);
        this.highestSeqAppended = head.seq;
        this.nextExpectedSeq = head.seq + 1;
        this.onChunkAppended?.(head.seq);
        if (this.status === "buffering" || this.status === "idle") {
          this.transitionTo("playing");
        }
        return; // The `updateend` listener calls drainPending again.
      } catch (err) {
        this.appendInFlight = false;
        this.transitionTo("error");
        // eslint-disable-next-line no-console
        console.warn("[chunked-player] appendBuffer failed", head.seq, err);
        return;
      }
    }
    if (
      this.endRequested &&
      this.pendingChunks.length === 0 &&
      !this.appendInFlight &&
      this.fetchesInFlight === 0
    ) {
      this.finalize();
    }
  }

  private finalize(): void {
    if (!this.mediaSource) return;
    if (this.mediaSource.readyState !== "open") return;
    try {
      this.mediaSource.endOfStream();
    } catch (err) {
      // eslint-disable-next-line no-console
      console.warn("[chunked-player] endOfStream failed", err);
    }
    this.transitionTo("ended");
  }

  private transitionTo(next: PlayerStatus): void {
    if (this.status === next) return;
    this.status = next;
    this.statusObserver?.(next);
  }
}
