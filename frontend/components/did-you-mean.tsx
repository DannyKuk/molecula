import type { DidYouMean } from "@/lib/did-you-mean";

type DidYouMeanButtonsProps = {
  offers: DidYouMean[];
  onAsk: (question: string) => void;
  /** Set while another answer is coming in, which a new question would have to wait for. */
  disabled: boolean;
};

/** One button per suggested name, each asking the question again with that name. */
export function DidYouMeanButtons({ offers, onAsk, disabled }: DidYouMeanButtonsProps) {
  return (
    <div className="flex flex-wrap gap-2 text-sm">
      {offers.map(({ suggestion, question }) => (
        <button
          key={question}
          type="button"
          title={question}
          disabled={disabled}
          onClick={() => onAsk(question)}
          className="rounded-full border border-zinc-300 px-3 py-1 hover:bg-zinc-100 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-zinc-500 disabled:cursor-not-allowed disabled:opacity-50 dark:border-zinc-700 dark:hover:bg-zinc-900"
        >
          Did you mean <strong className="font-semibold">{suggestion.alias}</strong>
          {suggestion.alias.toLowerCase() !== suggestion.name.toLowerCase() &&
            ` (${suggestion.name})`}
          ?
        </button>
      ))}
    </div>
  );
}
