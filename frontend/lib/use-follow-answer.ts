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

  useEffect(() => {
    let lastTop = window.scrollY;
    const onScroll = () => {
      // Content growing below leaves the scroll position where it was, so only a move up means
      // the reader left the end, not a scroll event that lands just after the page grew.
      if (nearEnd()) atEnd.current = true;
      else if (window.scrollY < lastTop) atEnd.current = false;
      lastTop = window.scrollY;
    };
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  // Layout effects, so the page moves before it is painted and stops following in the same
  // commit that turns `following` off.
  useLayoutEffect(() => {
    if (sent === 0) return;
    atEnd.current = true;
    scrollToEnd();
  }, [sent]);

  useLayoutEffect(() => {
    const element = content.current;
    if (!following || !element) return;
    const growth = new ResizeObserver(() => {
      if (atEnd.current) scrollToEnd();
    });
    growth.observe(element);
    return () => growth.disconnect();
  }, [content, following]);
}

// The page's own end, not an element's: scrolling an element into view ignores the sticky
// question box, which then covers the end of the conversation.
function scrollToEnd() {
  window.scrollTo({ top: document.documentElement.scrollHeight });
}

function nearEnd(): boolean {
  return window.innerHeight + window.scrollY >= document.documentElement.scrollHeight - NEAR_END;
}
