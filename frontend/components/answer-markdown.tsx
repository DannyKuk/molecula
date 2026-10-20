import Markdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";

import type { SourceCheck } from "@/lib/chat";
import { CITATION_RUN, runRefs, type Citations } from "@/lib/citations";
import { remarkSourceCheck, type MarkdownNode } from "@/lib/remark-source-check";
import { sourceCheckMarks } from "@/lib/source-check";

import { CitationChip, CitationsContext } from "./citation-chip";
import { CheckedClaimsContext, UnbackedMark } from "./unbacked-mark";

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
        found={data["data-found"] === "true"}
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
    <blockquote className="my-3 border-l-2 border-rule-2 pl-3 text-ink-2">{children}</blockquote>
  ),
  code: ({ children }) => (
    <code className="rounded bg-panel px-1 font-mono text-sm">{children}</code>
  ),
  pre: ({ children }) => (
    <pre className="my-3 overflow-x-auto rounded-lg bg-panel p-3">{children}</pre>
  ),
  table: ({ children }) => (
    <div className="my-3 overflow-x-auto">
      <table className="min-w-full border-collapse text-sm">{children}</table>
    </div>
  ),
  th: ({ children }) => (
    <th className="border border-rule-2 bg-card px-2 py-1 text-left font-semibold">{children}</th>
  ),
  td: ({ children }) => <td className="border border-rule-2 px-2 py-1 align-top">{children}</td>,
};

/** The answer as Markdown, GitHub style (tables, strikethrough). Raw HTML shows as text, never
 * rendered, because the answer is model output quoting untrusted label text. Citations such as
 * `[1]` and `【1】` stay as written until `citations` arrive, then become source chips. Once the
 * source check's verdict arrives, the text of each claim Molecula's sources don't hold is
 * underlined, and a claim that another returned result holds gets a chip for it. */
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
  const marks = sourceCheckMarks(text, claims);
  return (
    <CitationsContext value={citations}>
      <CheckedClaimsContext value={claims}>
        <div data-answer className="text-[16.5px] leading-[1.78] break-words">
          <Markdown
            remarkPlugins={[remarkGfm, [remarkSourceCheck, marks], remarkCitations]}
            components={components}
          >
            {text}
          </Markdown>
        </div>
      </CheckedClaimsContext>
    </CitationsContext>
  );
}
