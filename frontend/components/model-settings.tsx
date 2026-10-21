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
import type { ChatModel, ChecksChoice } from "@/lib/api";
import { useMessages } from "@/lib/messages";
import { useChosenChecks } from "@/lib/use-chosen-model";
import { shortName, useModelChoices } from "@/lib/use-model-choices";

// The models every prompt and eval was measured on: gpt-oss-20b locally, gpt-6-luna in the cloud
// (docs/decisions/chat-model.md).
export const TESTED_MODELS = ["openai/gpt-oss-20b", "openai/gpt-6-luna"];

/**
 * The settings over the chat, opened by `trigger`: which model writes the answers (#37), and which
 * models run the checks around a picked model's answer (#363).
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
          <DialogClose ref={closeRef} render={<Button variant="ghost" />}>
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
  const { choices, answering, choose } = useModelChoices();
  const [checks, chooseChecks] = useChosenChecks();
  const picked = choices && answering && answering.name !== choices.default ? answering : null;

  return (
    <section className="flex min-w-0 flex-col gap-3 text-sm text-ink-2">
      <h3 className="text-base font-semibold text-foreground">{t.settings.model}</h3>
      {choices === null && <p>{t.settings.loading}</p>}
      {choices === false && <p>{t.settings.off}</p>}
      {choices && answering && (
        <>
          <fieldset className="flex flex-col">
            <legend className="sr-only">{t.settings.model}</legend>
            {choices.models.map((model) => (
              <ModelOption
                key={model.name}
                model={model}
                isDefault={model.name === choices.default}
                checked={model.name === answering.name}
                onPick={() => choose(model.name === choices.default ? null : model.name)}
              />
            ))}
          </fieldset>
          {picked && <ChecksPicker picked={picked} checks={checks} onPick={chooseChecks} />}
          <Disclaimer
            defaultModel={choices.models[0]}
            answering={answering}
            checksOnPicked={picked !== null && checks === "picked"}
          />
        </>
      )}
    </section>
  );
}

function ModelOption({
  model,
  isDefault,
  checked,
  onPick,
}: {
  model: ChatModel;
  isDefault: boolean;
  checked: boolean;
  onPick: () => void;
}) {
  const t = useMessages();
  return (
    <Choice name="model" checked={checked} onPick={onPick}>
      <span className="min-w-0 truncate font-mono text-[13px]">{shortName(model.name)}</span>
      <span className="ml-auto shrink-0 text-xs text-ink-3">
        {[
          model.local ? t.settings.local : t.settings.cloud,
          TESTED_MODELS.includes(model.name) && t.settings.tested,
          isDefault && t.settings.default,
        ]
          .filter(Boolean)
          .join(" · ")}
      </span>
    </Choice>
  );
}

/** Whether the tested models or the picked model run the checks around its answer (#363). */
function ChecksPicker({
  picked,
  checks,
  onPick,
}: {
  picked: ChatModel;
  checks: ChecksChoice;
  onPick: (checks: ChecksChoice) => void;
}) {
  const t = useMessages();
  return (
    <fieldset className="flex flex-col">
      <legend className="pb-1.5 font-semibold text-foreground">{t.settings.checksOn}</legend>
      <Choice name="checks" checked={checks === "tested"} onPick={() => onPick("tested")}>
        {t.settings.checksTested}
      </Choice>
      <Choice name="checks" checked={checks === "picked"} onPick={() => onPick("picked")}>
        <span>
          {t.settings.checksPicked}
          <span className="font-mono text-[13px]">{shortName(picked.name)}</span>
        </span>
      </Choice>
    </fieldset>
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
        "flex cursor-pointer items-baseline gap-2.5 border-l-2 py-1.5 pl-3 hover:text-foreground",
        checked ? "border-ink text-foreground" : "border-rule",
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
  checksOnPicked,
}: {
  defaultModel: ChatModel;
  answering: ChatModel;
  checksOnPicked: boolean;
}) {
  const t = useMessages();
  return (
    <div className="flex flex-col gap-2 border-l-2 border-signal pl-3 text-[13px]">
      <p>{t.settings.developedWith}</p>
      <p>
        {checksOnPicked
          ? t.settings.checksOnPicked(shortName(answering.name))
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
