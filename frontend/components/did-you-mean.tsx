import type { DidYouMean } from "@/lib/did-you-mean";
import { useMessages } from "@/lib/messages";

type DidYouMeanButtonsProps = {
  offers: DidYouMean[];
  onAsk: (question: string) => void;
  /** Set while another answer is coming in, which a new question would have to wait for. */
  disabled: boolean;
};

/** One button per suggested name, each asking the question again with that name. */
export function DidYouMeanButtons({ offers, onAsk, disabled }: DidYouMeanButtonsProps) {
  const t = useMessages();
  return (
    <div className="flex flex-wrap gap-2 text-sm">
      {offers.map(({ suggestion, question }) => (
        <button
          key={question}
          type="button"
          title={question}
          disabled={disabled}
          onClick={() => onAsk(question)}
          className="rounded-full border border-rule-2 px-3 py-1 hover:bg-panel focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink-3 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {t.turn.didYouMean} <strong className="font-semibold">{suggestion.alias}</strong>
          {suggestion.alias.toLowerCase() !== suggestion.name.toLowerCase() &&
            ` (${suggestion.name})`}
          ?
        </button>
      ))}
    </div>
  );
}
