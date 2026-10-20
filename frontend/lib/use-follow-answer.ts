import {
  type RefObject,
  useCallback,
  useEffect,
  useEffectEvent,
  useLayoutEffect,
  useRef,
} from "react";

/** How close to the end of the page still counts as at the end, in pixels. */
const NEAR_END = 48;

/** How much room to leave above an element the page scrolls to, in pixels. */
const ABOVE_TOP = 16;

/**
 * Scrolls the page to its end each time a question is `sent` and then, while `answering`, keeps it
 * there as `content` grows, like a terminal. The reader scrolling up stops that, and scrolling back
 * down to the end starts it again. `onReaderScroll` hears of every move the reader makes, never of
 * the page's own. Returns `followAgain`, which goes back to the end and follows again, and
 * `scrollToTop`, which scrolls an element to the top of the window as one of the page's own moves.
 */
export function useFollowAnswer(
  content: RefObject<HTMLElement | null>,
  sent: number,
  answering: boolean,
  onReaderScroll: () => void = () => {},
) {
  const atEnd = useRef(true);
  const lastTop = useRef(0);
  const wasAnswering = useRef(false);
  const readerScrolled = useEffectEvent(onReaderScroll);

  useEffect(() => {
    lastTop.current = window.scrollY;
    const onScroll = () => {
      // Only a move up from where the page last was means the reader left the end. Content growing
      // below leaves the position as it was, so a scroll event that lands just after the page grew
      // doesn't count, and one scroll event can carry both a follow and the reader's move up.
      // The page's own scrolls land where they set `lastTop`, so any other position is the reader's.
      const byReader = window.scrollY !== lastTop.current;
      if (nearEnd()) atEnd.current = true;
      else if (window.scrollY < lastTop.current) atEnd.current = false;
      lastTop.current = window.scrollY;
      if (byReader) readerScrolled();
    };
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  // Layout effects, so the page moves before it is painted and stops following in the same
  // commit that turns `answering` off.
  useLayoutEffect(() => {
    if (sent === 0) return;
    atEnd.current = true;
    scrollToEnd(lastTop);
  }, [sent]);

  useLayoutEffect(() => {
    const element = content.current;
    if (!answering || !element) return;
    const growth = new ResizeObserver(() => {
      if (atEnd.current) scrollToEnd(lastTop);
    });
    growth.observe(element);
    return () => growth.disconnect();
  }, [content, answering]);

  // The pills and the usage line appear in the same commit that ends the answer, after the last
  // growth the observer saw, so a finished answer is followed to its end once more.
  useLayoutEffect(() => {
    if (wasAnswering.current && !answering && atEnd.current) scrollToEnd(lastTop);
    wasAnswering.current = answering;
  }, [answering]);

  const followAgain = useCallback(() => {
    atEnd.current = true;
    scrollToEnd(lastTop);
  }, []);

  const scrollToTop = useCallback((element: HTMLElement) => {
    window.scrollTo({ top: window.scrollY + element.getBoundingClientRect().top - ABOVE_TOP });
    lastTop.current = window.scrollY;
    atEnd.current = nearEnd();
  }, []);

  return { followAgain, scrollToTop };
}

// The page's own end, not an element's: scrolling an element into view ignores the sticky
// question box, which then covers the end of the conversation.
function scrollToEnd(lastTop: RefObject<number>) {
  window.scrollTo({ top: document.documentElement.scrollHeight });
  lastTop.current = window.scrollY;
}

/** Whether the page is scrolled to its end, or within a few pixels of it. */
export function nearEnd(): boolean {
  return window.innerHeight + window.scrollY >= document.documentElement.scrollHeight - NEAR_END;
}
