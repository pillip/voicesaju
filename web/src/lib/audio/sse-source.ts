/**
 * SSE → `ChunkEventSource` adapter (ISSUE-042).
 *
 * Bridges the browser `EventSource` API (consuming the
 * `GET /api/v1/reading/{id}/stream` endpoint from ISSUE-039) into the
 * `AsyncIterable<ChunkEvent>` contract that `<VoicePlayer>` expects
 * (see `lib/audio/events.ts`).
 *
 * Why a manual adapter instead of `for await ... of source`?
 *  - `EventSource` is callback-driven (`onmessage` / addEventListener).
 *  - `<VoicePlayer>` consumes events with `for await`, so we buffer
 *    incoming SSE messages into an internal queue and surface them via
 *    a single async iterator.
 *  - This also gives us a clean place to handle the named SSE events
 *    (`event: subtitle`, `event: audio_ready`, `event: end`, plus
 *    `event: error` from the backend) without bloating the player.
 *
 * Architecture refs:
 *   docs/architecture.md §6.3 (pipeline → SSE)
 *   docs/architecture.md §8.2 (chunk strategy)
 *   api/voicesaju/readings/services/pipeline_service.py (event framing)
 */

import type {
  AudioReadyEvent,
  ChunkEvent,
  ChunkEventSource,
  EndEvent,
  SubtitleEvent,
} from '@/lib/audio/events';

/**
 * `event: error` (LLM/TTS pipeline failure) is surfaced separately from
 * the standard chunk-event stream. The page-level shell on
 * `/reading/play` flips into the full-screen error state when this
 * fires; the player's own subtitle-only fallback (FR-034) is reserved
 * for the *audio-only* failure mode handled by the `<VoicePlayer>`'s
 * 5-second first-chunk timeout.
 */
export interface PipelineErrorEvent {
  type: 'pipeline_error';
  reason: 'llm_failure' | 'tts_failure' | 'unknown';
  message?: string;
}

export interface ReadingSSESource extends ChunkEventSource {
  /** Most recent audio playhead position (ms) advertised by a subtitle event. */
  readonly lastOffsetMs: number;
  /** Whether the underlying EventSource is currently connected. */
  readonly connected: boolean;
  /** Forcibly close the EventSource and the queue. */
  close(): void;
}

export interface ReadingSSESourceOptions {
  /** EventSource constructor — overridable for tests. Defaults to global. */
  EventSourceCtor?: typeof EventSource;
  /** Called when the pipeline fires `event: error`. */
  onPipelineError?: (err: PipelineErrorEvent) => void;
  /** Called when EventSource fires its low-level `error` (network/4xx). */
  onConnectionError?: () => void;
}

/**
 * Open an SSE connection to `/api/v1/reading/{readingId}/stream` and
 * return an async-iterable source compatible with `<VoicePlayer>`.
 *
 * The returned source completes (i.e. `for await` exits) when:
 *   1. the backend sends `event: end` (normal completion), OR
 *   2. the consumer calls `.close()`, OR
 *   3. an LLM error event was received (`onPipelineError` fires;
 *      the iterator then completes so the player stops consuming).
 *
 * EventSource auto-reconnect is **disabled** by closing on `error` —
 * the page shell decides whether to retry, since UX (network-drop
 * banner vs. full-screen LLM error) depends on the failure class.
 */
export function openReadingSSESource(
  readingId: string,
  options: ReadingSSESourceOptions = {},
): ReadingSSESource {
  const Ctor = options.EventSourceCtor ?? globalThis.EventSource;
  if (!Ctor) {
    throw new Error(
      'EventSource is not available in this environment. Pass `EventSourceCtor` for tests.',
    );
  }

  const url = `/api/v1/reading/${encodeURIComponent(readingId)}/stream`;
  const es = new Ctor(url, { withCredentials: true });

  // Internal queue + waiter — mirrors the pattern from VoicePlayer's
  // test harness.
  const queue: ChunkEvent[] = [];
  let resolveWaiter: (() => void) | null = null;
  let closed = false;
  let connected = false;
  let lastOffsetMs = 0;

  const wake = () => {
    const r = resolveWaiter;
    resolveWaiter = null;
    if (r) r();
  };
  const wait = () =>
    new Promise<void>((resolve) => {
      if (queue.length > 0 || closed) {
        resolve();
        return;
      }
      resolveWaiter = resolve;
    });

  // Parse a single SSE `data:` payload into our typed ChunkEvent.
  // Each handler reads `event.data` (JSON-encoded by the backend, see
  // `_sse_event()` in pipeline_service.py).
  const safeParse = (raw: string): Record<string, unknown> | null => {
    try {
      const parsed = JSON.parse(raw);
      return parsed && typeof parsed === 'object' ? (parsed as Record<string, unknown>) : null;
    } catch {
      return null;
    }
  };

  es.addEventListener('subtitle', (e: MessageEvent) => {
    const data = safeParse(e.data);
    if (!data) return;
    const text = typeof data.text === 'string' ? data.text : '';
    const offset = typeof data.audio_offset_ms === 'number' ? data.audio_offset_ms : 0;
    // The backend doesn't emit a `seq` on subtitle events — derive a
    // monotonic one from the offset to satisfy the SubtitleSync
    // dedupe contract.
    const ev: SubtitleEvent = {
      type: 'subtitle',
      seq: offset,
      text,
      audio_offset_ms: offset,
    };
    lastOffsetMs = Math.max(lastOffsetMs, offset);
    queue.push(ev);
    wake();
  });

  es.addEventListener('audio_ready', (e: MessageEvent) => {
    const data = safeParse(e.data);
    if (!data) return;
    const seq = typeof data.seq === 'number' ? data.seq : 0;
    const audioUrl = typeof data.url === 'string' ? data.url : '';
    if (!audioUrl) return;
    const ev: AudioReadyEvent = { type: 'audio_ready', url: audioUrl, seq };
    queue.push(ev);
    wake();
  });

  es.addEventListener('end', () => {
    const ev: EndEvent = { type: 'end' };
    queue.push(ev);
    closed = true;
    es.close();
    connected = false;
    wake();
  });

  es.addEventListener('error', (e: MessageEvent) => {
    // The pipeline emits `event: error` only on hard LLM failure.
    // Distinguish from the EventSource native `error` (no `.data`).
    if (typeof e.data === 'string') {
      const data = safeParse(e.data);
      const reason =
        data && typeof data.reason === 'string'
          ? (data.reason as PipelineErrorEvent['reason'])
          : 'unknown';
      const message = data && typeof data.message === 'string' ? data.message : undefined;
      options.onPipelineError?.({ type: 'pipeline_error', reason, message });
      closed = true;
      es.close();
      connected = false;
      wake();
      return;
    }
    // Native error → connection drop. Don't close the iterator (the
    // page shell may reconnect); just notify the caller.
    options.onConnectionError?.();
  });

  es.addEventListener('open', () => {
    connected = true;
  });

  const source: ReadingSSESource = {
    [Symbol.asyncIterator]: () => ({
      next: async (): Promise<IteratorResult<ChunkEvent>> => {
        while (queue.length === 0 && !closed) {
          await wait();
        }
        if (queue.length > 0) {
          return { value: queue.shift()!, done: false };
        }
        return { value: undefined as unknown as ChunkEvent, done: true };
      },
    }),
    get lastOffsetMs() {
      return lastOffsetMs;
    },
    get connected() {
      return connected;
    },
    close() {
      if (closed) return;
      closed = true;
      try {
        es.close();
      } catch {
        // ignore
      }
      connected = false;
      wake();
    },
  };

  return source;
}
