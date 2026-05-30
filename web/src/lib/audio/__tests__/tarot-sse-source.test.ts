/**
 * Unit tests for the tarot SSE → ChunkEventSource adapter (ISSUE-051).
 *
 * The tarot pipeline (ISSUE-049) starts with POST /api/v1/tarot/today/flip
 * and streams ``text/event-stream`` chunks. We can't use ``EventSource``
 * (GET-only), so the adapter uses ``fetch`` + ``ReadableStream``.
 *
 * These tests inject a fake fetch + ReadableStream so we exercise the
 * line/frame parser deterministically.
 */
import { describe, expect, it, vi } from "vitest";
import { openTarotSSESource } from "@/lib/audio/tarot-sse-source";
import type { ChunkEvent } from "@/lib/audio/events";

/**
 * Build a fake ``Response`` whose body yields the given SSE frames one
 * by one. Each ``frame`` should already contain the trailing ``\n\n``.
 */
function makeSSEResponse(frames: string[], status = 200): Response {
  const encoder = new TextEncoder();
  let i = 0;
  const stream = new ReadableStream<Uint8Array>({
    pull(controller) {
      if (i < frames.length) {
        controller.enqueue(encoder.encode(frames[i]));
        i += 1;
      } else {
        controller.close();
      }
    },
  });
  return new Response(stream, {
    status,
    headers: { "Content-Type": "text/event-stream" },
  });
}

async function drain(source: AsyncIterable<ChunkEvent>): Promise<ChunkEvent[]> {
  const out: ChunkEvent[] = [];
  for await (const ev of source) {
    out.push(ev);
  }
  return out;
}

describe("openTarotSSESource (ISSUE-051)", () => {
  it("forwards subtitle / audio_ready / end events to the iterator in order", async () => {
    const fetchImpl = vi.fn(async () =>
      makeSSEResponse([
        `event: subtitle\ndata: ${JSON.stringify({
          text: "오늘은 바보 카드.",
          audio_offset_ms: 0,
        })}\n\n`,
        `event: audio_ready\ndata: ${JSON.stringify({
          seq: 0,
          url: "https://r2/tarot/0.mp3",
        })}\n\n`,
        `event: subtitle\ndata: ${JSON.stringify({
          text: "새 시작이네.",
          audio_offset_ms: 200,
        })}\n\n`,
        `event: end\ndata: {}\n\n`,
      ]),
    );

    const source = openTarotSSESource({
      fetchImpl: fetchImpl as unknown as typeof fetch,
    });
    const events = await drain(source);

    expect(fetchImpl).toHaveBeenCalledWith(
      "/api/v1/tarot/today/flip",
      expect.objectContaining({ method: "POST" }),
    );
    expect(events).toHaveLength(4);
    expect(events[0]).toMatchObject({
      type: "subtitle",
      text: "오늘은 바보 카드.",
    });
    expect(events[1]).toMatchObject({
      type: "audio_ready",
      seq: 0,
      url: "https://r2/tarot/0.mp3",
    });
    expect(events[2]).toMatchObject({
      type: "subtitle",
      text: "새 시작이네.",
      audio_offset_ms: 200,
    });
    expect(events[3]).toMatchObject({ type: "end" });
  });

  it("handles frames split across multiple TextEncoder chunks", async () => {
    // Backend writers + proxies may chunk the stream anywhere. Build
    // a response whose body splits a single frame at the colon — the
    // parser must buffer across reads.
    const fetchImpl = vi.fn(async () =>
      makeSSEResponse([
        "event: sub",
        `title\ndata: ${JSON.stringify({ text: "조각난 자막", audio_offset_ms: 0 })}\n\n`,
        "event: end\ndata: {}\n\n",
      ]),
    );

    const source = openTarotSSESource({
      fetchImpl: fetchImpl as unknown as typeof fetch,
    });
    const events = await drain(source);

    expect(events).toHaveLength(2);
    expect(events[0]).toMatchObject({ type: "subtitle", text: "조각난 자막" });
    expect(events[1]).toMatchObject({ type: "end" });
  });

  it("invokes onPipelineError on event:error and completes the iterator", async () => {
    const onPipelineError = vi.fn();
    const fetchImpl = vi.fn(async () =>
      makeSSEResponse([
        `event: error\ndata: ${JSON.stringify({
          reason: "tts_failure",
          message: "voice fixture missing",
        })}\n\n`,
      ]),
    );

    const source = openTarotSSESource({
      fetchImpl: fetchImpl as unknown as typeof fetch,
      onPipelineError,
    });
    const events = await drain(source);

    expect(events).toHaveLength(0);
    expect(onPipelineError).toHaveBeenCalledWith({
      type: "pipeline_error",
      reason: "tts_failure",
      message: "voice fixture missing",
    });
  });

  it("invokes onConnectionError when the initial fetch throws", async () => {
    const onConnectionError = vi.fn();
    const fetchImpl = vi.fn(async () => {
      throw new TypeError("network down");
    });

    const source = openTarotSSESource({
      fetchImpl: fetchImpl as unknown as typeof fetch,
      onConnectionError,
    });
    const events = await drain(source);

    expect(events).toHaveLength(0);
    expect(onConnectionError).toHaveBeenCalledTimes(1);
  });

  it("invokes onConnectionError on non-2xx response", async () => {
    const onConnectionError = vi.fn();
    const fetchImpl = vi.fn(async () => new Response("nope", { status: 402 }));

    const source = openTarotSSESource({
      fetchImpl: fetchImpl as unknown as typeof fetch,
      onConnectionError,
    });
    const events = await drain(source);

    expect(events).toHaveLength(0);
    expect(onConnectionError).toHaveBeenCalledTimes(1);
  });

  it("close() aborts the stream and completes the iterator", async () => {
    // Build a response whose body never completes on its own — we
    // close from the consumer side.
    const stream = new ReadableStream<Uint8Array>({
      // No pull → the reader awaits indefinitely until aborted.
      pull() {
        // never enqueue
      },
    });
    const fetchImpl = vi.fn(
      async () =>
        new Response(stream, {
          status: 200,
          headers: { "Content-Type": "text/event-stream" },
        }),
    );

    const source = openTarotSSESource({
      fetchImpl: fetchImpl as unknown as typeof fetch,
    });

    // Start draining; close mid-flight; assert iterator completes.
    const drainP = drain(source);
    // Give the runner a tick to enter the read loop.
    await new Promise((r) => setTimeout(r, 5));
    source.close();
    const events = await drainP;
    expect(events).toHaveLength(0);
  });

  it("tracks lastOffsetMs from subtitle events", async () => {
    const fetchImpl = vi.fn(async () =>
      makeSSEResponse([
        `event: subtitle\ndata: ${JSON.stringify({
          text: "첫줄",
          audio_offset_ms: 100,
        })}\n\n`,
        `event: subtitle\ndata: ${JSON.stringify({
          text: "두번째",
          audio_offset_ms: 350,
        })}\n\n`,
        "event: end\ndata: {}\n\n",
      ]),
    );

    const source = openTarotSSESource({
      fetchImpl: fetchImpl as unknown as typeof fetch,
    });
    await drain(source);
    expect(source.lastOffsetMs).toBe(350);
  });
});
