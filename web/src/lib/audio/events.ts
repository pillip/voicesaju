/**
 * Chunk-event contract for the streaming voice player (ISSUE-033).
 *
 * The reading session screen subscribes to a single SSE stream that
 * multiplexes three event kinds — `audio_ready`, `subtitle`, and `end`.
 * The actual SSE wiring lands in ISSUE-039 (pipeline orchestration); this
 * module is the typed contract that both the player and the future SSE
 * client (or any test harness) agree on.
 *
 * Architecture refs:
 *   docs/architecture.md §4.1 (frontend principles — single SSE stream)
 *   docs/architecture.md §8.2 (server-side chunk strategy)
 *
 * Why an `AsyncIterable<ChunkEvent>` rather than a callback subscription?
 *  - The player can `for await` the stream which mirrors the canonical SSE
 *    `EventSource` -> `ReadableStream` adapter pattern most teams use in
 *    Next.js apps. ISSUE-039's pipeline will expose its SSE client as an
 *    async iterable for the same reason.
 *  - Tests can `yield` events synchronously through a generator without
 *    plumbing fake `EventSource` polyfills into jsdom — the timing is
 *    governed by the player's own `currentTime` advance rather than wall
 *    clock, which is exactly what NFR-015 wants to assert.
 */

/**
 * An audio chunk has been packaged server-side and is ready to fetch.
 *
 * `url`        — presigned R2 URL pointing at an `audio/mpeg` (mp3) chunk.
 *                Sentence-level chunks per architecture §8.2.
 * `seq`        — 0-based sequence number. Used to detect out-of-order
 *                arrival; the player buffers append calls in order.
 * `mime`       — codec hint. Defaults to `audio/mpeg`. Documented so
 *                future TTS providers (e.g. opus) can land without
 *                touching the player contract.
 */
export interface AudioReadyEvent {
  type: "audio_ready";
  url: string;
  seq: number;
  mime?: string;
}

/**
 * A subtitle line should appear when audio playhead reaches
 * `audio_offset_ms`. The player schedules display within 500ms of the
 * playhead crossing the offset (NFR-015).
 *
 * `seq`             — monotonic counter for the subtitle stream. Used to
 *                     dedupe + recover from out-of-order arrival.
 * `text`            — Korean subtitle text. Pre-sanitised server-side.
 * `audio_offset_ms` — playhead position (ms from session start) at which
 *                     this line is meant to appear.
 */
export interface SubtitleEvent {
  type: "subtitle";
  seq: number;
  text: string;
  audio_offset_ms: number;
}

/**
 * The reading is complete. The player should let any buffered audio
 * finish playing, then transition out (the wiring screen decides what
 * "out" means — usually navigation to the follow-up route).
 */
export interface EndEvent {
  type: "end";
}

export type ChunkEvent = AudioReadyEvent | SubtitleEvent | EndEvent;

/**
 * Source contract the `<VoicePlayer>` accepts. We deliberately accept the
 * broadest possible async-stream shape: anything `for await ... of`-able.
 * ISSUE-039's SSE adapter satisfies this; the test harness satisfies it
 * via a vanilla async generator.
 */
export type ChunkEventSource = AsyncIterable<ChunkEvent>;
