import Markdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";

import type { SourceCheck } from "@/lib/chat";
import { CITATION_RUN, runRefs, type Citations } from "@/lib/citations";
import { unbackedRanges, type UnbackedRange } from "@/lib/source-check";

import { CitationChip, CitationsContext } from "./citation-chip";
import { CheckedClaimsContext, UnbackedMark } from "./unbacked-mark";

type MarkdownNode = {
  type: string;
  value?: string;
  children?: MarkdownNode[];
  data?: { hName: string; hProperties: Record<string, string> };
  position?: { start: { offset?: number }; end: { offset?: number } };
};

/** Marks the text of each claim the sources don't back as a `mark` element. It runs before
 * `remarkCitations`, while text nodes still know where they stand in the answer. */
function remarkUnbacked(ranges: UnbackedRange[]) {
  return (tree: MarkdownNode) => {
    if (ranges.length > 0) markUnbacked(tree, ranges);
  };
}

function markUnbacked(node: MarkdownNode, ranges: UnbackedRange[]) {
  if (!node.children) return;
  node.children = node.children.flatMap((child) => {
    if (child.type === "text" && child.value) return splitUnbacked(child, ranges);
    markUnbacked(child, ranges);
    return [child];
  });
}

function splitUnbacked(node: MarkdownNode, ranges: UnbackedRange[]): MarkdownNode[] {
  const start = node.position?.start.offset;
  const end = node.position?.end.offset;
  const value = node.value!;
  if (start === undefined || end === undefined) return [node];
  const inside = ranges.filter((range) => range.start < end && range.end > start);
  if (inside.length === 0) return [node];
  // An escape or an entity makes the text shorter than its source, so offsets don't line up.
  if (end - start !== value.length) return markedText(value, inside[0].claim);
  const nodes: MarkdownNode[] = [];
  let at = 0;
  for (const range of inside) {
    const from = Math.max(range.start - start, at);
    const to = Math.min(range.end - start, value.length);
    if (from > at) nodes.push({ type: "text", value: value.slice(at, from) });
    nodes.push(...markedText(value.slice(from, to), range.claim));
    at = to;
  }
  if (at < value.length) nodes.push({ type: "text", value: value.slice(at) });
  return nodes;
}

/** The text marked, except its citations and anything without a word, so a chip never sits
 * inside the underline. */
function markedText(text: string, claim: number): MarkdownNode[] {
  const nodes: MarkdownNode[] = [];
  let end = 0;
  const mark = (part: string) => {
    if (!part) return;
    nodes.push(
      /\w/.test(part)
        ? {
            type: "unbacked",
            data: { hName: "mark", hProperties: { dataClaim: String(claim) } },
            children: [{ type: "text", value: part }],
          }
        : { type: "text", value: part },
    );
  };
  for (const run of text.matchAll(CITATION_RUN)) {
    let start = run.index;
    while (start > end && text[start - 1] === " ") start--;
    mark(text.slice(end, start));
    end = run.index + run[0].length;
    nodes.push({ type: "text", value: text.slice(start, end) });
  }
  mark(text.slice(end));
  return nodes;
}

/** Marks each run of citations in the text as a `cite` element, so it renders as a chip.
 * Code is left alone: its text isn't a `text` node. */
function remarkCitations() {
  return (tree: MarkdownNode) => markCitations(tree);
}

function markCitations(node: MarkdownNode) {
  if (!node.children) return;
  node.children = node.children.flatMap((child) => {
    if (child.type === "text" && child.value) return splitCitations(child.value);
    markCitations(child);
    return [child];
  });
}

function splitCitations(text: string): MarkdownNode[] {
  const nodes: MarkdownNode[] = [];
  let end = 0;
  for (const run of text.matchAll(CITATION_RUN)) {
    // The space before a citation goes with it, so a citation that is left out leaves none.
    let start = run.index;
    while (start > end && text[start - 1] === " ") start--;
    if (start > end) nodes.push({ type: "text", value: text.slice(end, start) });
    nodes.push({
      type: "citation",
      data: {
        hName: "cite",
        hProperties: { dataRefs: runRefs(run[0]).join(","), dataSpaced: String(start < run.index) },
      },
      children: [{ type: "text", value: text.slice(start, run.index + run[0].length) }],
    });
    end = run.index + run[0].length;
  }
  if (end < text.length) nodes.push({ type: "text", value: text.slice(end) });
  return nodes;
}

const components: Components = {
  mark: ({ children, ...props }) => (
    <UnbackedMark claim={Number((props as Record<string, unknown>)["data-claim"])}>
      {children}
    </UnbackedMark>
  ),
  cite: ({ children, ...props }) => {
    const data = props as Record<string, unknown>;
    return (
      <CitationChip
        refs={String(data["data-refs"]).split(",").map(Number)}
        spaced={data["data-spaced"] === "true"}
      >
        {children}
      </CitationChip>
    );
  },
  p: ({ children }) => <p className="my-3 first:mt-0 last:mb-0">{children}</p>,
  a: ({ href, children }) => (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="underline underline-offset-4"
    >
      {children}
    </a>
  ),
  ul: ({ children }) => <ul className="my-3 list-disc space-y-1 pl-6">{children}</ul>,
  ol: ({ children }) => <ol className="my-3 list-decimal space-y-1 pl-6">{children}</ol>,
  h1: ({ children }) => <h3 className="mt-4 mb-2 font-semibold">{children}</h3>,
  h2: ({ children }) => <h3 className="mt-4 mb-2 font-semibold">{children}</h3>,
  h3: ({ children }) => <h3 className="mt-4 mb-2 font-semibold">{children}</h3>,
  h4: ({ children }) => <h4 className="mt-3 mb-1 font-semibold">{children}</h4>,
  blockquote: ({ children }) => (
    <blockquote className="my-3 border-l-2 border-zinc-300 pl-3 text-zinc-700 dark:border-zinc-700 dark:text-zinc-300">
      {children}
    </blockquote>
  ),
  code: ({ children }) => (
    <code className="rounded bg-zinc-100 px-1 font-mono text-sm dark:bg-zinc-900">{children}</code>
  ),
  pre: ({ children }) => (
    <pre className="my-3 overflow-x-auto rounded-lg bg-zinc-100 p-3 dark:bg-zinc-900">
      {children}
    </pre>
  ),
  table: ({ children }) => (
    <div className="my-3 overflow-x-auto">
      <table className="min-w-full border-collapse text-sm">{children}</table>
    </div>
  ),
  th: ({ children }) => (
    <th className="border border-zinc-300 bg-zinc-50 px-2 py-1 text-left font-semibold dark:border-zinc-700 dark:bg-zinc-900">
      {children}
    </th>
  ),
  td: ({ children }) => (
    <td className="border border-zinc-300 px-2 py-1 align-top dark:border-zinc-700">{children}</td>
  ),
};

/** The answer as Markdown, GitHub style (tables, strikethrough). Raw HTML shows as text, never
 * rendered, because the answer is model output quoting untrusted label text. Citations such as
 * `[1]` and `【1】` stay as written until `citations` arrive, then become source chips. Once the
 * source check's verdict arrives, the text of each claim the sources don't back is underlined. */
export function AnswerMarkdown({
  text,
  citations = null,
  sourceCheck = null,
}: {
  text: string;
  citations?: Citations | null;
  sourceCheck?: SourceCheck | null;
}) {
  const claims = sourceCheck?.checked ? sourceCheck.claims : [];
  const ranges = unbackedRanges(text, claims);
  return (
    <CitationsContext value={citations}>
      <CheckedClaimsContext value={claims}>
        <div className="leading-relaxed break-words">
          <Markdown
            remarkPlugins={[remarkGfm, [remarkUnbacked, ranges], remarkCitations]}
            components={components}
          >
            {text}
          </Markdown>
        </div>
      </CheckedClaimsContext>
    </CitationsContext>
  );
}
