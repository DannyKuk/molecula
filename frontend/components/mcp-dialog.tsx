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

export const CHECKOUT_PLACEHOLDER = "/path/to/molecula";

// The commands and the config are the README's "MCP server" section word for word; a test checks it.
export const CLAUDE_DESKTOP_CONFIG = `{
  "mcpServers": {
    "molecula": {
      "command": "uv",
      "args": ["--directory", "${CHECKOUT_PLACEHOLDER}/backend", "run", "python", "-m", "molecula.mcp"]
    }
  }
}`;

export const START_COMMANDS = [
  { name: "stdio", how: "Over stdio", command: "uv run python -m molecula.mcp" },
  {
    name: "Streamable HTTP",
    how: "Over Streamable HTTP, at http://localhost:8001/mcp",
    command: "uv run python -m molecula.mcp --transport streamable-http",
  },
  {
    name: "Docker",
    how: "The same in Docker",
    command: "docker compose --profile mcp up --build",
  },
];

export const TOOLS = [
  {
    name: "resolve_drug",
    finds:
      "Which supported drug a name means: a generic, a brand, a non-US or German name or a salt.",
  },
  { name: "get_properties", finds: "The drug's chemical properties, from PubChem." },
  {
    name: "get_targets",
    finds: "The proteins the drug acts on and its mechanism of action, from ChEMBL.",
  },
  {
    name: "get_complex",
    finds:
      "The reviewed 3D structure of the drug bound to its target, from the Protein Data Bank, with the residues that touch it.",
  },
  {
    name: "search_labels",
    finds:
      "Passages from the FDA drug labels: uses, side effects, warnings, interactions and more.",
  },
  { name: "compare_drugs", finds: "The chemical properties of 2 to 4 drugs side by side." },
];

const SHOWN_MS = 2000;

/** What Molecula's MCP server gives another AI assistant and how to connect one to it (#301). */
export function McpGuide() {
  return (
    <div className="flex min-w-0 flex-col gap-6 text-sm text-ink-2">
      <section className="flex flex-col gap-2">
        <p>
          The chat&apos;s six tools are also an MCP server, so an assistant like Claude Desktop or
          any other MCP client can look up drugs from the same store this chat answers from. Every
          result names its sources with a number to cite them by.
        </p>
        <dl className="flex flex-col gap-1.5">
          {TOOLS.map((tool) => (
            <div key={tool.name} className="grid gap-x-3 sm:grid-cols-[9rem_1fr]">
              <dt className="font-mono text-[12.5px] text-foreground">{tool.name}</dt>
              <dd>{tool.finds}</dd>
            </div>
          ))}
        </dl>
      </section>
      <section className="flex flex-col gap-2">
        <h3 className="text-base font-semibold text-foreground">Connect Claude Desktop</h3>
        <p>
          Open Settings → Developer → Edit Config, add this to{" "}
          <code className="font-mono text-[12.5px]">claude_desktop_config.json</code>, replace{" "}
          <Placeholder /> with the folder of your Molecula checkout and restart Claude Desktop.
        </p>
        <CodeBlock text={CLAUDE_DESKTOP_CONFIG} copyLabel="Copy config" />
      </section>
      <section className="flex flex-col gap-2">
        <h3 className="text-base font-semibold text-foreground">Other MCP clients</h3>
        <p>
          Start the server in your checkout&apos;s <code className="font-mono">backend</code>{" "}
          folder. It takes about 30 seconds while it loads the embedding model.
        </p>
        <ul className="flex flex-col gap-2">
          {START_COMMANDS.map(({ name, how, command }) => (
            <li key={command} className="flex flex-col gap-1">
              <span>{how}</span>
              <CodeBlock text={command} copyLabel={`Copy the ${name} command`} />
            </li>
          ))}
        </ul>
      </section>
      <p>
        The server runs on your own computer, next to your checkout and with the same{" "}
        <code className="font-mono">.env</code> and store. It has no login and answers only requests
        addressed to localhost, so a Molecula running somewhere else can&apos;t be connected to.
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
      aria-label={copied === "copied" ? "Copied" : copied === "failed" ? "Copy failed" : label}
      className="absolute top-1.5 right-1.5 inline-flex items-center gap-1 rounded-md border border-white/15 bg-white/5 px-2 py-0.5 text-xs text-screen-ink hover:bg-white/15 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink-3"
    >
      <Icon aria-hidden className="size-3.5" />
      <span aria-live="polite">
        {copied === "copied" ? "Copied" : copied === "failed" ? "Copy failed" : "Copy"}
      </span>
    </button>
  );
}

/** The MCP setup guide over the chat, opened by `trigger` and closed with its Close button,
 * Escape or a click beside it. */
export function McpDialog({ trigger, children }: { trigger: ReactElement; children: ReactNode }) {
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
          <DialogTitle className="text-lg font-semibold">
            Use Molecula in your AI assistant
          </DialogTitle>
          <DialogClose ref={closeRef} render={<Button variant="ghost" />}>
            Close
          </DialogClose>
        </div>
        <McpGuide />
      </DialogContent>
    </Dialog>
  );
}
