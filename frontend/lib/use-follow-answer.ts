import { type RefObject, useEffect, useEffectEvent, useLayoutEffect, useRef } from "react";

/** How close to the end of the scroll area still counts as at the end, in pixels. */
const NEAR_END = 48;

/** How much room to leave above an element the chat scrolls to, in pixels. */
const ABOVE_TOP = 16;

/**
 * Scrolls the chat's `scroller` to its end each time a question is `sent` and then, while
 * `answering`, keeps it there as `content` grows, like a terminal. The reader scrolling up stops
 * that, and scrolling back down to the end starts it again. `onReaderScroll` hears of every move the
 * reader makes, never of the chat's own. Returns `followAgain`, which goes back to the end and
 * follows again, and `scrollToTop`, which scrolls an element to the top of the scroll area as one of
 * the chat's own moves.
 */
export function useFollowAnswer(
  scroller: RefObject<HTMLElement | null>,
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
    const area = scroller.current;
    if (!area) return;
    lastTop.current = area.scrollTop;
    const onScroll = () => {
      // Only a move up from where the chat last was means the reader left the end. Content growing
      // below leaves the position as it was, so a scroll event that lands just after the chat grew
      // doesn't count, and one scroll event can carry both a follow and the reader's move up.
      // The chat's own scrolls land where they set `lastTop`, so any other position is the reader's.
      const byReader = area.scrollTop !== lastTop.current;
      if (nearEnd(area)) atEnd.current = true;
      else if (area.scrollTop < lastTop.current) atEnd.current = false;
      lastTop.current = area.scrollTop;
      if (byReader) readerScrolled();
    };
    area.addEventListener("scroll", onScroll, { passive: true });
    return () => area.removeEventListener("scroll", onScroll);
  }, [scroller]);

  // Layout effects, so the chat moves before it is painted and stops following in the same
  // commit that turns `answering` off.
  useLayoutEffect(() => {
    if (sent === 0 || !scroller.current) return;
    atEnd.current = true;
    scrollToEnd(scroller.current, lastTop);
  }, [scroller, sent]);

  useLayoutEffect(() => {
    const area = scroller.current;
    const element = content.current;
    if (!answering || !area || !element) return;
    const growth = new ResizeObserver(() => {
      if (atEnd.current) scrollToEnd(area, lastTop);
    });
    growth.observe(element);
    return () => growth.disconnect();
  }, [scroller, content, answering]);

  // The pills and the usage line appear in the same commit that ends the answer, after the last
  // growth the observer saw, so a finished answer is followed to its end once more.
  useLayoutEffect(() => {
    if (wasAnswering.current && !answering && atEnd.current && scroller.current) {
      scrollToEnd(scroller.current, lastTop);
    }
    wasAnswering.current = answering;
  }, [scroller, answering]);

  const followAgain = () => {
    if (!scroller.current) return;
    atEnd.current = true;
    scrollToEnd(scroller.current, lastTop);
  };

  const scrollToTop = (element: HTMLElement) => {
    const area = scroller.current;
    if (!area) return;
    const below = element.getBoundingClientRect().top - area.getBoundingClientRect().top;
    area.scrollTo({ top: area.scrollTop + below - ABOVE_TOP });
    lastTop.current = area.scrollTop;
    atEnd.current = nearEnd(area);
  };

  return { followAgain, scrollToTop };
}

// The scroll area's own end, not an element's: scrolling an element into view ignores the question
// box floating over the bottom, which then covers the end of the conversation.
function scrollToEnd(area: HTMLElement, lastTop: RefObject<number>) {
  area.scrollTo({ top: area.scrollHeight });
  lastTop.current = area.scrollTop;
}

/** Whether the scroll area is scrolled to its end, or within a few pixels of it. */
export function nearEnd(area: HTMLElement): boolean {
  return area.clientHeight + area.scrollTop >= area.scrollHeight - NEAR_END;
}
