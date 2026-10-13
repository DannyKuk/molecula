import { type RefObject, useEffect, useLayoutEffect, useRef } from "react";

/** How close to the end of the page still counts as at the end, in pixels. */
const NEAR_END = 48;

/**
 * Scrolls the page to its end each time a question is `sent` and then, while `following` is on,
 * keeps it there as `content` grows, like a terminal. The reader scrolling up stops that, and
 * scrolling back down to the end starts it again.
 */
export function useFollowAnswer(
  content: RefObject<HTMLElement | null>,
  sent: number,
  following: boolean,
) {
  const atEnd = useRef(true);
  const lastTop = useRef(0);

  useEffect(() => {
    lastTop.current = window.scrollY;
    const onScroll = () => {
      // Only a move up from where the page last was means the reader left the end. Content growing
      // below leaves the position as it was, so a scroll event that lands just after the page grew
      // doesn't count, and one scroll event can carry both a follow and the reader's move up.
      if (nearEnd()) atEnd.current = true;
      else if (window.scrollY < lastTop.current) atEnd.current = false;
      lastTop.current = window.scrollY;
    };
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  // Layout effects, so the page moves before it is painted and stops following in the same
  // commit that turns `following` off.
  useLayoutEffect(() => {
    if (sent === 0) return;
    atEnd.current = true;
    scrollToEnd(lastTop);
  }, [sent]);

  useLayoutEffect(() => {
    const element = content.current;
    if (!following || !element) return;
    const growth = new ResizeObserver(() => {
      if (atEnd.current) scrollToEnd(lastTop);
    });
    growth.observe(element);
    return () => growth.disconnect();
  }, [content, following]);
}

// The page's own end, not an element's: scrolling an element into view ignores the sticky
// question box, which then covers the end of the conversation.
function scrollToEnd(lastTop: RefObject<number>) {
  window.scrollTo({ top: document.documentElement.scrollHeight });
  lastTop.current = window.scrollY;
}

function nearEnd(): boolean {
  return window.innerHeight + window.scrollY >= document.documentElement.scrollHeight - NEAR_END;
}
