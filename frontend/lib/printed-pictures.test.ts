import { afterEach, describe, expect, it, vi } from "vitest";

import { startTurn, type Turn } from "./chat-turn";
import {
  DRAW_TIMEOUT_MS,
  drawPictures,
  picturesToDraw,
  type Picture,
  type Pictures,
} from "./printed-pictures";
import {
  ACETAMINOPHEN_NO_COMPLEX,
  IMATINIB_COMPLEX,
  METFORMIN_PROPERTIES,
} from "./test-tool-results";
import type { StructureTarget, ToolRun } from "./tool-cards";

function lookup(name: string, result: unknown): ToolRun {
  return { id: name, name, args: {}, result };
}

function turnWith(...tools: ToolRun[]): Turn {
  return {
    ...startTurn("How do they work?"),
    state: "done",
    steps: tools.map((tool) => ({ text: tool.name, tool })),
  };
}

const IMATINIB = lookup("get_complex", IMATINIB_COMPLEX);
const ACETAMINOPHEN = lookup("get_complex", ACETAMINOPHEN_NO_COMPLEX);

const READY: Picture = { status: "ready", png: "data:image/png;base64,", complex: null };

const cids = (targets: StructureTarget[]) => targets.map((target) => target.cid);

afterEach(() => {
  vi.useRealTimers();
});

describe("picturesToDraw", () => {
  it("takes every drug the conversation showed in 3D once, with or without a complex", () => {
    const turns = [
      turnWith(lookup("get_properties", METFORMIN_PROPERTIES), IMATINIB),
      turnWith(ACETAMINOPHEN, IMATINIB),
    ];

    const targets = picturesToDraw(turns, new Map());

    expect(cids(targets)).toEqual([5291, 1983]);
    expect(targets[0].complex?.pdb_id).toBe("2HYY");
    expect(targets[1].complex).toBeNull();
  });

  it("skips a drug already drawn or without a 3D model, and tries a failed one again", () => {
    const turns = [turnWith(IMATINIB, ACETAMINOPHEN)];
    const drawn = (picture: Picture): Pictures => new Map([[5291, picture]]);

    expect(cids(picturesToDraw(turns, drawn(READY)))).toEqual([1983]);
    expect(cids(picturesToDraw(turns, drawn({ status: "missing" })))).toEqual([1983]);
    expect(cids(picturesToDraw(turns, drawn({ status: "failed" })))).toEqual([5291, 1983]);
  });

  it("has nothing to draw for a conversation without 3D", () => {
    expect(
      picturesToDraw([turnWith(lookup("get_properties", METFORMIN_PROPERTIES))], new Map()),
    ).toEqual([]);
  });
});

describe("drawPictures", () => {
  const targets = picturesToDraw([turnWith(IMATINIB, ACETAMINOPHEN)], new Map());

  it("draws one picture at a time", async () => {
    const started: string[] = [];
    const finish: (() => void)[] = [];
    const drawing = drawPictures(targets, (target) => {
      started.push(target.name);
      return new Promise((resolve) => finish.push(() => resolve(READY)));
    });

    await vi.waitFor(() => expect(started).toEqual(["imatinib"]));
    finish[0]();
    await vi.waitFor(() => expect(started).toEqual(["imatinib", "acetaminophen"]));
    finish[1]();

    expect(await drawing).toEqual(
      new Map([
        [5291, READY],
        [1983, READY],
      ]),
    );
  });

  it("goes on after a picture that fails, which comes back as failed", async () => {
    const drawn = await drawPictures(targets, (target) =>
      target.cid === 5291 ? Promise.reject(new Error("WebGL is off")) : Promise.resolve(READY),
    );

    expect(drawn.get(5291)).toEqual({ status: "failed" });
    expect(drawn.get(1983)).toEqual(READY);
  });

  it("gives up on a picture that takes too long", async () => {
    vi.useFakeTimers();
    const drawing = drawPictures(targets, (target) =>
      target.cid === 5291 ? new Promise<Picture>(() => {}) : Promise.resolve(READY),
    );

    await vi.advanceTimersByTimeAsync(DRAW_TIMEOUT_MS);

    const drawn = await drawing;
    expect(drawn.get(5291)).toEqual({ status: "failed" });
    expect(drawn.get(1983)).toEqual(READY);
  });
});
