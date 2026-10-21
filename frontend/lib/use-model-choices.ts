import { useEffect, useState } from "react";

import { type ChatModel, getModels, type ModelChoices } from "./api";
import { useChosenModel } from "./use-chosen-model";

type Choices = {
  /** Null while the list loads, false when the chat is off. */
  choices: ModelChoices | null | false;
  /** The model that writes the next answer: the picked one, or the default. */
  answering: ChatModel | null;
  choose: (name: string | null) => void;
};

/**
 * The models the backend offers and the one that answers. A picked model the backend no longer
 * lists (deleted in LM Studio, or a backend with other models) falls back to the default, so a
 * question never goes out with a name the backend refuses.
 */
export function useModelChoices(): Choices {
  const [choices, setChoices] = useState<ModelChoices | null | false>(null);
  const [chosen, choose] = useChosenModel();

  useEffect(() => {
    const controller = new AbortController();
    getModels(controller.signal)
      .then(setChoices)
      .catch(() => {
        if (!controller.signal.aborted) setChoices(false);
      });
    return () => controller.abort();
  }, []);

  const listed = choices ? choices.models : [];
  const picked = listed.find(({ name }) => name === chosen);
  useEffect(() => {
    if (choices && chosen !== null && !picked) choose(null);
  }, [choices, chosen, picked, choose]);

  const fallback = choices ? listed.find(({ name }) => name === choices.default) : undefined;
  return { choices, answering: picked ?? fallback ?? null, choose };
}

/** "gpt-oss-20b": a model's id without its provider. */
export function shortName(name: string): string {
  return name.split("/").at(-1) ?? name;
}
