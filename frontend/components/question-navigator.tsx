import { useMessages } from "@/lib/messages";
import { cn } from "@/lib/utils";

type QuestionNavigatorProps = {
  questions: string[];
  /** The question being read, marked with a long orange dash and its number. */
  read: number;
  /** The question whose answer is coming in, whose dash pulses. */
  live: number | null;
  onJump: (index: number) => void;
};

/**
 * One dash per question on the chat's right edge, after the owner's wish for scroll marks "like
 * Grok's dashes" (#296). Hovering them shows their numbers and the questions as a list; phones keep
 * only the dashes.
 */
export function QuestionNavigator({ questions, read, live, onJump }: QuestionNavigatorProps) {
  const t = useMessages();
  return (
    <nav
      aria-label={t.navigator.label}
      className="group absolute top-1/2 right-1 z-20 -translate-y-1/2 py-2 pl-4 min-[900px]:right-3 print:hidden"
    >
      <ol className="flex flex-col items-end">
        {questions.map((question, index) => (
          <li key={index}>
            <button
              type="button"
              aria-label={t.navigator.question(index + 1, question)}
              aria-current={index === read || undefined}
              data-live={index === live || undefined}
              onClick={() => onJump(index)}
              className="group/dash flex h-3 w-7 min-[900px]:w-11 items-center justify-end gap-1.5"
            >
              <span
                aria-hidden
                className={cn(
                  "hidden font-mono text-[9.5px] text-ink-3 opacity-0 transition-opacity group-hover:opacity-100 min-[900px]:inline",
                  index === read && "text-signal opacity-100",
                )}
              >
                {String(index + 1).padStart(2, "0")}
              </span>
              <span
                aria-hidden
                className={cn(
                  "h-px w-2.5 rounded-full bg-ink-3 transition-[width,background-color]",
                  index === read
                    ? "h-0.5 w-[22px] bg-signal"
                    : "group-hover/dash:w-[18px] group-hover/dash:bg-ink-2",
                  index === live && "animate-pulse bg-signal motion-reduce:animate-none",
                )}
              />
            </button>
          </li>
        ))}
      </ol>
      <ol
        // The dashes already name each question to a screen reader; the list is for the pointer.
        aria-hidden
        className="invisible absolute top-1/2 right-full hidden max-h-[60dvh] w-64 -translate-y-1/2 overflow-y-auto rounded-[10px] border border-rule-2 bg-card p-1.5 opacity-0 shadow-lg transition-opacity group-hover:visible group-hover:opacity-100 min-[900px]:block"
      >
        {questions.map((question, index) => (
          <li key={index}>
            <button
              type="button"
              tabIndex={-1}
              onClick={() => onJump(index)}
              className={cn(
                "flex w-full items-baseline gap-2.5 rounded-md px-2 py-1.5 text-left text-[13px] text-ink-2 hover:bg-panel hover:text-ink",
                index === read && "text-ink",
              )}
            >
              <span
                className={cn(
                  "flex-none font-mono text-[11px] text-ink-3",
                  index === read && "text-signal",
                )}
              >
                {index + 1}
              </span>
              <span className="truncate">{question}</span>
            </button>
          </li>
        ))}
      </ol>
    </nav>
  );
}
