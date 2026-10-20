import { useState } from "react";
import { flushSync } from "react-dom";

import type { Turn } from "./chat-turn";
import { drawPictures, picturesToDraw, type DrawPicture, type Pictures } from "./printed-pictures";

/**
 * The pictures of the conversation's 3D structures for paper. `prepare` draws the missing ones,
 * puts them on the page and resolves once the browser has decoded them, so a print dialog opened
 * after it shows them. A drug's picture is kept for later prints, also of other chats.
 */
export function usePrintedPictures(turns: Turn[], draw: DrawPicture) {
  const [pictures, setPictures] = useState<Pictures>(() => new Map());

  const prepare = async () => {
    const drawn = await drawPictures(picturesToDraw(turns, pictures), draw);
    if (drawn.size > 0) {
      // `window.print()` prints the page as it is, so the pictures must be in it before it's called.
      flushSync(() => setPictures((current) => new Map([...current, ...drawn])));
    }
    const images = document.querySelectorAll<HTMLImageElement>("img[data-printed-picture]");
    await Promise.all([...images].map((image) => image.decode().catch(() => undefined)));
  };

  return { pictures, prepare };
}
