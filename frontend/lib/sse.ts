export type ServerSentEvent = {
  event: string;
  data: string;
};

/**
 * The server-sent events in a response body, as each one completes. A frame can arrive split
 * over several chunks, and a chunk can end inside a multi-byte character. Leaving the loop early
 * cancels the body, which closes the connection.
 */
export async function* readServerSentEvents(
  body: ReadableStream<Uint8Array>,
): AsyncGenerator<ServerSentEvent> {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) return;
      buffer = (buffer + decoder.decode(value, { stream: true })).replace(/\r\n/g, "\n");
      let frameEnd = buffer.indexOf("\n\n");
      while (frameEnd !== -1) {
        const event = parseFrame(buffer.slice(0, frameEnd));
        buffer = buffer.slice(frameEnd + 2);
        if (event) yield event;
        frameEnd = buffer.indexOf("\n\n");
      }
    }
  } finally {
    // A body that ended or failed has nothing left to cancel.
    await reader.cancel().catch(() => {});
  }
}

function parseFrame(frame: string): ServerSentEvent | null {
  let event = "message";
  const data: string[] = [];
  for (const line of frame.split("\n")) {
    const [field, value] = splitField(line);
    if (field === "event") event = value;
    if (field === "data") data.push(value);
  }
  return data.length > 0 ? { event, data: data.join("\n") } : null;
}

function splitField(line: string): [string, string] {
  const colon = line.indexOf(":");
  if (colon === -1) return [line, ""];
  const value = line.slice(colon + 1);
  return [line.slice(0, colon), value.startsWith(" ") ? value.slice(1) : value];
}
