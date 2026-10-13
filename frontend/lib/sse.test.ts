import { describe, expect, it } from "vitest";

import { readServerSentEvents, type ServerSentEvent } from "./sse";

function streamOf(chunks: (string | Uint8Array)[]): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder();
  return new ReadableStream({
    start(controller) {
      for (const chunk of chunks) {
        controller.enqueue(typeof chunk === "string" ? encoder.encode(chunk) : chunk);
      }
      controller.close();
    },
  });
}

async function readAll(chunks: (string | Uint8Array)[]): Promise<ServerSentEvent[]> {
  const events: ServerSentEvent[] = [];
  for await (const event of readServerSentEvents(streamOf(chunks))) events.push(event);
  return events;
}

describe("readServerSentEvents", () => {
  it("reads each frame's event name and data", async () => {
    const events = await readAll([
      'event: status\ndata: {"message":"Looking up Gleevec"}\n\n',
      'event: token\ndata: {"text":"Imatinib"}\n\n',
    ]);

    expect(events).toEqual([
      { event: "status", data: '{"message":"Looking up Gleevec"}' },
      { event: "token", data: '{"text":"Imatinib"}' },
    ]);
  });

  it("puts a frame split across chunks back together", async () => {
    const events = await readAll(["eve", 'nt: token\ndata: {"te', 'xt":"a"}\n', "\nevent: done\n"]);

    expect(events).toEqual([{ event: "token", data: '{"text":"a"}' }]);
  });

  it("decodes a character split across chunks", async () => {
    const bytes = new TextEncoder().encode("event: token\ndata: 【1】\n\n");
    const middleOfBracket = "event: token\ndata: ".length + 1;

    const events = await readAll([bytes.slice(0, middleOfBracket), bytes.slice(middleOfBracket)]);

    expect(events).toEqual([{ event: "token", data: "【1】" }]);
  });

  it("reads CRLF line endings, joins data lines and skips comments", async () => {
    const events = await readAll([
      ": keep-alive\r\n\r\nevent: token\r\ndata: a\r\ndata: b\r\n\r\n",
    ]);

    expect(events).toEqual([{ event: "token", data: "a\nb" }]);
  });

  it("names a frame without an event line 'message'", async () => {
    expect(await readAll(["data: hello\n\n"])).toEqual([{ event: "message", data: "hello" }]);
  });
});
