"use client";

import { cn } from "cn";
import { type ReactElement, type ReactNode, useRef } from "react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import type { ChatModel } from "@/lib/api";
import { useMessages } from "@/lib/messages";
import { shortName, useModelChoices } from "@/lib/use-model-choices";

// The models every prompt and eval was measured on: gpt-oss-20b locally, gpt-6-luna in the cloud
// (docs/decisions/chat-model.md).
export const TESTED_MODELS = ["openai/gpt-oss-20b", "openai/gpt-6-luna"];

/**
 * The settings over the chat, opened by `trigger`: which model checks the messages (#363) and
 * which model writes the answers (#37).
 */
export function ModelSettings({
  trigger,
  children,
}: {
  trigger: ReactElement;
  children: ReactNode;
}) {
  const t = useMessages();
  const closeRef = useRef<HTMLButtonElement>(null);

  return (
    <Dialog>
      <DialogTrigger render={trigger}>{children}</DialogTrigger>
      <DialogContent
        showCloseButton={false}
        initialFocus={closeRef}
        className="top-auto bottom-0 max-h-[90dvh] max-w-lg translate-y-0 gap-4 overflow-y-auto rounded-b-none bg-background p-4 sm:top-1/2 sm:bottom-auto sm:max-w-lg sm:-translate-y-1/2 sm:rounded-2xl sm:p-6"
      >
        <div className="flex items-center justify-between gap-4">
          <DialogTitle className="text-lg font-semibold">{t.settings.title}</DialogTitle>
          <DialogClose
            ref={closeRef}
            render={<Button variant="ghost" className="hover:bg-rule dark:hover:bg-rule" />}
          >
            {t.settings.close}
          </DialogClose>
        </div>
        <ModelPicker />
      </DialogContent>
    </Dialog>
  );
}

export function ModelPicker() {
  const t = useMessages();
  const { choices, answering, choose, checking, chooseChecker } = useModelChoices();

  if (choices === null) return <p className="text-sm text-ink-2">{t.settings.loading}</p>;
  if (choices === false || !answering || !checking) {
    return <p className="text-sm text-ink-2">{t.settings.off}</p>;
  }
  return (
    <div className="flex min-w-0 flex-col gap-5 text-sm text-ink-2">
      <Group title={t.settings.checker}>
        <p className="text-[13px]">{t.settings.checkerAbout}</p>
        <fieldset className="flex flex-col">
          <legend className="sr-only">{t.settings.checker}</legend>
          {choices.checkers.map((checker) => (
            <Choice
              key={checker.id}
              name="checker"
              checked={checking === checker.id}
              onPick={() => chooseChecker(checker.id)}
            >
              <ModelName name={checker.name} />
              <Tags
                tags={[
                  checker.local ? t.settings.local : t.settings.cloud,
                  t.settings.tested,
                  checker.id === choices.default_checker && t.settings.default,
                ]}
              />
            </Choice>
          ))}
          <Choice
            name="checker"
            checked={checking === "answer"}
            onPick={() => chooseChecker("answer")}
          >
            <span>{t.settings.checkerAnswer}</span>
            <Tags tags={[choices.default_checker === "answer" && t.settings.default]} />
          </Choice>
        </fieldset>
      </Group>
      <Group title={t.settings.model}>
        <fieldset className="flex flex-col">
          <legend className="sr-only">{t.settings.model}</legend>
          {choices.models.map((model) => (
            <Choice
              key={model.name}
              name="model"
              checked={model.name === answering.name}
              onPick={() => choose(model.name === choices.default ? null : model.name)}
            >
              <ModelName name={model.name} />
              <Tags
                tags={[
                  model.local ? t.settings.local : t.settings.cloud,
                  TESTED_MODELS.includes(model.name) && t.settings.tested,
                  model.name === choices.default && t.settings.default,
                ]}
              />
            </Choice>
          ))}
        </fieldset>
      </Group>
      <Disclaimer
        defaultModel={choices.models[0]}
        answering={answering}
        checkedByAnswer={
          checking === "answer" && !choices.checkers.some(({ name }) => name === answering.name)
        }
      />
    </div>
  );
}

function Group({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="flex flex-col gap-3">
      <h3 className="text-base font-semibold text-foreground">{title}</h3>
      {children}
    </section>
  );
}

function ModelName({ name }: { name: string }) {
  return <span className="min-w-0 truncate font-mono text-[13px]">{shortName(name)}</span>;
}

function Tags({ tags }: { tags: (string | false)[] }) {
  return (
    <span className="ml-auto shrink-0 text-xs text-ink-3">{tags.filter(Boolean).join(" · ")}</span>
  );
}

function Choice({
  name,
  checked,
  onPick,
  children,
}: {
  name: string;
  checked: boolean;
  onPick: () => void;
  children: ReactNode;
}) {
  return (
    <label
      className={cn(
        "flex cursor-pointer items-baseline gap-2.5 rounded-r-md border-l-2 py-1.5 pr-2 pl-3 hover:bg-rule hover:text-foreground",
        checked ? "border-ink text-foreground" : "border-rule hover:border-ink-3",
      )}
    >
      <input
        type="radio"
        name={name}
        checked={checked}
        onChange={onPick}
        className="translate-y-px accent-ink"
      />
      {children}
    </label>
  );
}

/** Why the tested models are the safe pick: everything was measured on them (#37). */
function Disclaimer({
  defaultModel,
  answering,
  checkedByAnswer,
}: {
  defaultModel: ChatModel;
  answering: ChatModel;
  checkedByAnswer: boolean;
}) {
  const t = useMessages();
  return (
    <div className="flex flex-col gap-2 border-l-2 border-signal pl-3 text-[13px]">
      <p>{t.settings.developedWith}</p>
      <p>
        {checkedByAnswer
          ? t.settings.checksByAnswer(shortName(answering.name))
          : t.settings.checksStay}
      </p>
      {answering.local && answering.name !== defaultModel.name && (
        <p>
          {t.settings.loadsFirst}
          {defaultModel.local && t.settings.fitsNextTo(shortName(defaultModel.name))}
          {t.settings.context}
        </p>
      )}
    </div>
  );
}
