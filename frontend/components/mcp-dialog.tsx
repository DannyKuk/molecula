"use client";

import { Check, Copy } from "lucide-react";
import { type ReactElement, type ReactNode, useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { useMessages } from "@/lib/messages";

export const CHECKOUT_PLACEHOLDER = "/path/to/molecula";

// The commands and the config are the "MCP server" section of docs/setup.md word for word; a test checks it.
export const CLAUDE_DESKTOP_CONFIG = `{
  "mcpServers": {
    "molecula": {
      "command": "uv",
      "args": ["--directory", "${CHECKOUT_PLACEHOLDER}/backend", "run", "python", "-m", "molecula.mcp"]
    }
  }
}`;

export const START_COMMANDS = [
  { name: "stdio", command: "uv run python -m molecula.mcp" },
  {
    name: "Streamable HTTP",
    command: "uv run python -m molecula.mcp --transport streamable-http",
  },
  { name: "Docker", command: "docker compose --profile mcp up --build" },
] as const;

/** The server's tools; what each finds is in the interface text (`mcp.tools`). */
export const TOOLS = [
  { name: "resolve_drug" },
  { name: "get_properties" },
  { name: "get_targets" },
  { name: "get_complex" },
  { name: "search_labels" },
  { name: "compare_drugs" },
] as const;

const SHOWN_MS = 2000;

/** What Molecula's MCP server gives another AI assistant and how to connect one to it (#301). */
export function McpGuide() {
  const t = useMessages();
  return (
    <div className="flex min-w-0 flex-col gap-6 text-sm text-ink-2">
      <section className="flex flex-col gap-2">
        <p>{t.mcp.intro}</p>
        <dl className="flex flex-col gap-1.5">
          {TOOLS.map((tool) => (
            <div key={tool.name} className="grid gap-x-3 sm:grid-cols-[9rem_1fr]">
              <dt className="font-mono text-[12.5px] text-foreground">{tool.name}</dt>
              <dd>{t.mcp.tools[tool.name]}</dd>
            </div>
          ))}
        </dl>
      </section>
      <section className="flex flex-col gap-2">
        <h3 className="text-base font-semibold text-foreground">{t.mcp.connectTitle}</h3>
        <p>
          {t.mcp.connectOpen}{" "}
          <code className="font-mono text-[12.5px]">claude_desktop_config.json</code>
          {t.mcp.connectReplace} <Placeholder /> {t.mcp.connectWith}
        </p>
        <CodeBlock text={CLAUDE_DESKTOP_CONFIG} copyLabel={t.mcp.copyConfig} />
      </section>
      <section className="flex flex-col gap-2">
        <h3 className="text-base font-semibold text-foreground">{t.mcp.otherTitle}</h3>
        <p>
          {t.mcp.otherStart} <code className="font-mono">backend</code> {t.mcp.otherFolder}
        </p>
        <ul className="flex flex-col gap-2">
          {START_COMMANDS.map(({ name, command }) => (
            <li key={command} className="flex flex-col gap-1">
              <span>{t.mcp.start[name]}</span>
              <CodeBlock text={command} copyLabel={t.mcp.copyCommand(name)} />
            </li>
          ))}
        </ul>
      </section>
      <p>
        {t.mcp.localBefore} <code className="font-mono">.env</code> {t.mcp.localAfter}
      </p>
    </div>
  );
}

function Placeholder() {
  return (
    <mark className="rounded-sm bg-signal-soft px-0.5 font-mono text-[12.5px] text-foreground">
      {CHECKOUT_PLACEHOLDER}
    </mark>
  );
}

function CodeBlock({ text, copyLabel }: { text: string; copyLabel: string }) {
  const [before, ...after] = text.split(CHECKOUT_PLACEHOLDER);
  return (
    <div className="relative">
      <pre className="rounded-lg whitespace-pre-wrap [overflow-wrap:anywhere] bg-screen py-2.5 pr-20 pl-3 font-mono text-[12px] leading-relaxed text-screen-ink">
        {before}
        {after.map((rest, index) => (
          <span key={index}>
            <mark className="rounded-sm bg-signal-soft px-0.5 text-ink">
              {CHECKOUT_PLACEHOLDER}
            </mark>
            {rest}
          </span>
        ))}
      </pre>
      <CopyButton text={text} label={copyLabel} />
    </div>
  );
}

function CopyButton({ text, label }: { text: string; label: string }) {
  const t = useMessages();
  const [copied, setCopied] = useState<"copied" | "failed" | null>(null);

  useEffect(() => {
    if (!copied) return;
    const timer = setTimeout(() => setCopied(null), SHOWN_MS);
    return () => clearTimeout(timer);
  }, [copied]);

  async function copy() {
    try {
      await navigator.clipboard.writeText(text);
      setCopied("copied");
    } catch {
      setCopied("failed");
    }
  }

  const Icon = copied === "copied" ? Check : Copy;
  return (
    <button
      type="button"
      onClick={copy}
      aria-label={
        copied === "copied" ? t.mcp.copied : copied === "failed" ? t.mcp.copyFailed : label
      }
      className="absolute top-1.5 right-1.5 inline-flex items-center gap-1 rounded-md border border-white/15 bg-white/5 px-2 py-0.5 text-xs text-screen-ink hover:bg-white/15 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink-3"
    >
      <Icon aria-hidden className="size-3.5" />
      <span aria-live="polite">
        {copied === "copied" ? t.mcp.copied : copied === "failed" ? t.mcp.copyFailed : t.mcp.copy}
      </span>
    </button>
  );
}

/** The MCP setup guide over the chat, opened by `trigger` and closed with its Close button,
 * Escape or a click beside it. */
export function McpDialog({ trigger, children }: { trigger: ReactElement; children: ReactNode }) {
  const t = useMessages();
  const closeRef = useRef<HTMLButtonElement>(null);

  return (
    <Dialog>
      <DialogTrigger render={trigger}>{children}</DialogTrigger>
      <DialogContent
        showCloseButton={false}
        initialFocus={closeRef}
        className="top-auto bottom-0 max-h-[90dvh] max-w-2xl translate-y-0 gap-4 overflow-y-auto rounded-b-none bg-background p-4 sm:top-1/2 sm:bottom-auto sm:max-w-2xl sm:-translate-y-1/2 sm:rounded-2xl sm:p-6"
      >
        <div className="flex items-center justify-between gap-4">
          <DialogTitle className="text-lg font-semibold">{t.mcp.title}</DialogTitle>
          <DialogClose ref={closeRef} render={<Button variant="ghost" />}>
            {t.mcp.close}
          </DialogClose>
        </div>
        <McpGuide />
      </DialogContent>
    </Dialog>
  );
}
