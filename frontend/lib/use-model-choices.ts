import { useEffect, useState } from "react";

import { type ChatModel, type CheckerId, getModels, type ModelChoices } from "./api";
import { useChosenChecker, useChosenModel } from "./use-chosen-model";

type Choices = {
  /** Null while the list loads, false when the chat is off. */
  choices: ModelChoices | null | false;
  /** The model that writes the next answer: the picked one, or the default. */
  answering: ChatModel | null;
  choose: (name: string | null) => void;
  /** Who checks the next messages: the picked checker, or the default (#363). */
  checking: CheckerId | null;
  chooseChecker: (checker: CheckerId | null) => void;
};

/**
 * The models the backend offers, the one that answers and the one that checks. A picked model or
 * checker the backend no longer offers (deleted in LM Studio, Jev after a switch to offline, or a
 * backend with other models) falls back to the default, so a question never goes out with a
 * choice the backend refuses.
 */
export function useModelChoices(): Choices {
  const [choices, setChoices] = useState<ModelChoices | null | false>(null);
  const [chosen, choose] = useChosenModel();
  const [chosenChecker, chooseChecker] = useChosenChecker();

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

  const offered =
    choices &&
    (chosenChecker === "answer" || choices.checkers.some(({ id }) => id === chosenChecker));
  useEffect(() => {
    if (choices && chosenChecker !== null && !offered) chooseChecker(null);
  }, [choices, chosenChecker, offered, chooseChecker]);

  const fallback = choices ? listed.find(({ name }) => name === choices.default) : undefined;
  const defaultChecker = choices ? choices.default_checker : null;
  return {
    choices,
    answering: picked ?? fallback ?? null,
    choose,
    checking: offered ? chosenChecker : defaultChecker,
    chooseChecker: (checker) => chooseChecker(checker === defaultChecker ? null : checker),
  };
}

/** "gpt-oss-20b": a model's id without its provider. */
export function shortName(name: string): string {
  return name.split("/").at(-1) ?? name;
}
