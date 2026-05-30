/**
 * Tarot-flavoured SSE adapter (ISSUE-051).
 *
 * The daily-tarot pipeline (ISSUE-049) starts via
 * ``POST /api/v1/tarot/today/flip`` which returns a
 * ``text/event-stream`` :class:`StreamingResponse`. Browser
 * ``EventSource`` is GET-only, so we can't reuse
 * :func:`openReadingSSESource` — instead we drive the stream via
 * ``fetch`` + a manual SSE line parser. The output contract is the
 * same :type:`ChunkEventSource` that :component:`<VoicePlayer>`
 * consumes (no player changes needed).
 *
 * Event shapes match the backend's :func:`_sse_event` helper:
 *
 * - ``event: subtitle`` → ``{text, audio_offset_ms}``
 * - ``event: audio_ready`` → ``{seq, url}``
 * - ``event: end`` → ``{}``
 * - ``event: error`` → ``{reason, message?}``  (LLM hard-failure)
 *
 * Lifecycle:
 *
 * 1. ``openTarotSSESource()`` returns synchronously with a stable
 *    source object; the underlying fetch starts in the background.
 *    ``<VoicePlayer>``'s ``for await`` then sees events as soon as
 *    the first frame arrives.
 * 2. When the backend emits ``event: end`` the iterator completes
 *    (mirrors :func:`openReadingSSESource`'s behaviour).
 * 3. ``.close()`` aborts the fetch via :class:`AbortController` and
 *    completes the iterator.
 *
 * Why not generalise :func:`openReadingSSESource`? The two endpoints
 * differ in shape (GET vs POST) and lifecycle (auto-reconnect rules
 * differ — tarot only has 1 chance, the row is consumed). A tiny
 * parallel adapter keeps each path obvious.
 *
 * Architecture-Ref: §6.4 (tarot flow), §8.2 (chunk strategy).
 */

import type {
  AudioReadyEvent,
  ChunkEvent,
  ChunkEventSource,
  EndEvent,
  SubtitleEvent,
} from "@/lib/audio/events";
import type { PipelineErrorEvent } from "@/lib/audio/sse-source";

export interface TarotSSESource extends ChunkEventSource {
  readonly lastOffsetMs: number;
  readonly connected: boolean;
  close(): void;
}

export interface TarotSSESourceOptions {
  /** Test hook: override ``fetch``. Defaults to ``globalThis.fetch``. */
  fetchImpl?: typeof fetch;
  /** Called when the backend emits ``event: error`` (LLM/TTS hard fail). */
  onPipelineError?: (err: PipelineErrorEvent) => void;
  /** Called when the underlying fetch fails or the stream drops. */
  onConnectionError?: () => void;
  /**
   * Endpoint override (test hook). Defaults to the production tarot
   * flip path. Production code should leave this unset.
   */
  endpoint?: string;
}

/**
 * Open a tarot flip stream and return an async-iterable source.
 *
 * Errors during the initial POST surface via ``onConnectionError`` and
 * complete the iterator immediately so the page can show its error
 * shell. The 402 quota-exhausted envelope is treated as a connection
 * error here — the page is expected to have already routed to
 * ``/tarot/paywall`` on ISSUE-050's GET path, so seeing 402 on POST
 * means the page raced the quota and should bounce back.
 */
export function openTarotSSESource(
  options: TarotSSESourceOptions = {},
): TarotSSESource {
  const fetchImpl = options.fetchImpl ?? globalThis.fetch;
  if (!fetchImpl) {
    throw new Error(
      "fetch is not available in this environment. Pass `fetchImpl` for tests.",
    );
  }
  const endpoint = options.endpoint ?? "/api/v1/tarot/today/flip";

  const queue: ChunkEvent[] = [];
  let resolveWaiter: (() => void) | null = null;
  let closed = false;
  let connected = false;
  let lastOffsetMs = 0;
  const controller = new AbortController();

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

  const safeParse = (raw: string): Record<string, unknown> | null => {
    try {
      const parsed = JSON.parse(raw);
      return parsed && typeof parsed === "object"
        ? (parsed as Record<string, unknown>)
        : null;
    } catch {
      return null;
    }
  };

  const handleEvent = (eventName: string, rawData: string): void => {
    if (eventName === "subtitle") {
      const data = safeParse(rawData);
      if (!data) return;
      const text = typeof data.text === "string" ? data.text : "";
      const offset =
        typeof data.audio_offset_ms === "number" ? data.audio_offset_ms : 0;
      const ev: SubtitleEvent = {
        type: "subtitle",
        seq: offset,
        text,
        audio_offset_ms: offset,
      };
      lastOffsetMs = Math.max(lastOffsetMs, offset);
      queue.push(ev);
      wake();
      return;
    }
    if (eventName === "audio_ready") {
      const data = safeParse(rawData);
      if (!data) return;
      const seq = typeof data.seq === "number" ? data.seq : 0;
      const audioUrl = typeof data.url === "string" ? data.url : "";
      if (!audioUrl) return;
      const ev: AudioReadyEvent = { type: "audio_ready", url: audioUrl, seq };
      queue.push(ev);
      wake();
      return;
    }
    if (eventName === "end") {
      const ev: EndEvent = { type: "end" };
      queue.push(ev);
      closed = true;
      connected = false;
      wake();
      return;
    }
    if (eventName === "error") {
      const data = safeParse(rawData);
      const reason =
        data && typeof data.reason === "string"
          ? (data.reason as PipelineErrorEvent["reason"])
          : "unknown";
      const message =
        data && typeof data.message === "string" ? data.message : undefined;
      options.onPipelineError?.({ type: "pipeline_error", reason, message });
      closed = true;
      connected = false;
      wake();
      return;
    }
    // Unknown event → ignore (forward-compat: backend may add new
    // event names later that the player doesn't know about).
  };

  /**
   * Parse a single SSE "frame" — a block separated by ``\n\n``. Each
   * frame is a sequence of ``field: value`` lines. We only care about
   * ``event:`` + ``data:``; ``id:`` and retry are not used by the
   * tarot pipeline.
   */
  const parseFrame = (frame: string): void => {
    let eventName = "message";
    const dataLines: string[] = [];
    for (const line of frame.split("\n")) {
      if (line.startsWith(":")) continue; // SSE comment
      if (line.startsWith("event:")) {
        eventName = line.slice(6).trim();
      } else if (line.startsWith("data:")) {
        dataLines.push(line.slice(5).trim());
      }
    }
    if (dataLines.length === 0 && eventName === "end") {
      // ``end`` events sometimes have no payload — still dispatch.
      handleEvent(eventName, "");
      return;
    }
    if (dataLines.length === 0) return;
    handleEvent(eventName, dataLines.join("\n"));
  };

  // -- background reader ---------------------------------------------
  // We do NOT await the start of the fetch in the function body —
  // the page mounts the source synchronously and waits on the
  // iterator. The async runner pushes events into the queue as they
  // arrive; errors are surfaced via callbacks.

  const run = async (): Promise<void> => {
    let response: Response;
    try {
      response = await fetchImpl(endpoint, {
        method: "POST",
        credentials: "include",
        headers: { Accept: "text/event-stream" },
        signal: controller.signal,
      });
    } catch (err) {
      if ((err as Error).name === "AbortError") {
        // .close() was called — silently complete.
        closed = true;
        wake();
        return;
      }
      options.onConnectionError?.();
      closed = true;
      wake();
      return;
    }

    if (!response.ok || response.body === null) {
      // 402 or 5xx — page shell decides recovery. We don't try to
      // surface 402 as PipelineErrorEvent because that's reserved for
      // mid-stream LLM failures.
      options.onConnectionError?.();
      closed = true;
      wake();
      return;
    }

    connected = true;
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    try {
      while (!closed) {
        const { value, done } = await reader.read();
        if (done) {
          // Stream ended without an explicit ``event: end`` — flush any
          // remaining frame then complete the iterator.
          if (buffer.trim().length > 0) {
            parseFrame(buffer);
          }
          closed = true;
          connected = false;
          wake();
          return;
        }
        buffer += decoder.decode(value, { stream: true });
        // SSE frames are separated by a blank line — i.e. two
        // consecutive ``\n``. We tolerate ``\r\n`` for proxies that
        // re-line-end the stream.
        while (true) {
          const sepIdx = buffer.indexOf("\n\n");
          const crlfIdx = buffer.indexOf("\r\n\r\n");
          const idx =
            sepIdx === -1
              ? crlfIdx
              : crlfIdx === -1
                ? sepIdx
                : Math.min(sepIdx, crlfIdx);
          if (idx === -1) break;
          const frame = buffer.slice(0, idx);
          buffer = buffer.slice(idx + (buffer[idx] === "\r" ? 4 : 2));
          parseFrame(frame);
        }
      }
    } catch (err) {
      if ((err as Error).name !== "AbortError") {
        options.onConnectionError?.();
      }
      closed = true;
      connected = false;
      wake();
    }
  };

  // Kick off the reader. We deliberately do not await — the iterator
  // contract is "I'll yield events as they show up".
  void run();

  const source: TarotSSESource = {
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
        controller.abort();
      } catch {
        // ignore — already aborted.
      }
      connected = false;
      wake();
    },
  };

  return source;
}
