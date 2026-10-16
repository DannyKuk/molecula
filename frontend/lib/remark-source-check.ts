import { CITATION_RUN } from "./citations";
import type { FoundCitation, SourceCheckMarks, UnbackedRange } from "./source-check";

/** A node of the Markdown syntax tree, as far as the answer's plugins read and write it. */
export type MarkdownNode = {
  type: string;
  value?: string;
  children?: MarkdownNode[];
  data?: { hName: string; hProperties: Record<string, string> };
  position?: { start: { offset?: number }; end: { offset?: number } };
};

/**
 * Puts the source check into the answer: the text of each claim the sources don't back becomes
 * a `mark` element, and a claim another returned result holds gets a `cite` element for it. It
 * runs before the citations become chips, while text nodes still know where they stand in the
 * answer.
 */
export function remarkSourceCheck(marks: SourceCheckMarks) {
  return (tree: MarkdownNode) => {
    if (marks.unbacked.length > 0 || marks.found.length > 0) visit(tree, marks);
  };
}

function visit(node: MarkdownNode, marks: SourceCheckMarks) {
  if (!node.children) return;
  node.children = node.children.flatMap((child) => {
    if (child.type === "text" && child.value) return split(child, marks);
    visit(child, marks);
    return [child];
  });
}

function split(node: MarkdownNode, { unbacked, found }: SourceCheckMarks): MarkdownNode[] {
  const start = node.position?.start.offset;
  const end = node.position?.end.offset;
  const value = node.value!;
  if (start === undefined || end === undefined) return [node];
  const inside = unbacked.filter((range) => range.start < end && range.end > start);
  const here = found.filter((citation) => citation.at > start && citation.at <= end);
  if (inside.length === 0 && here.length === 0) return [node];
  // An escape or an entity makes the text shorter than its source, so offsets don't line up.
  if (end - start !== value.length) {
    return inside.length > 0 ? markedText(value, inside[0].claim) : [node];
  }
  const cuts = new Set([0, value.length]);
  for (const range of inside) {
    cuts.add(Math.max(range.start - start, 0));
    cuts.add(Math.min(range.end - start, value.length));
  }
  for (const citation of here) cuts.add(citation.at - start);
  const points = [...cuts].sort((a, b) => a - b);
  const nodes: MarkdownNode[] = [];
  for (let index = 1; index < points.length; index++) {
    const [from, to] = [points[index - 1], points[index]];
    const range = inside.find((r) => r.start - start <= from && r.end - start >= to);
    const text = value.slice(from, to);
    nodes.push(...(range ? markedText(text, range.claim) : [{ type: "text", value: text }]));
    nodes.push(...here.filter((citation) => citation.at - start === to).map(foundCitation));
  }
  return nodes;
}

/** The text marked, except its citations and anything without a word, so a chip never sits
 * inside the underline. */
function markedText(text: string, claim: UnbackedRange["claim"]): MarkdownNode[] {
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

/** A chip the answer didn't write; it has no text, so the citations step leaves it alone. */
function foundCitation({ refs }: FoundCitation): MarkdownNode {
  return {
    type: "citation",
    data: {
      hName: "cite",
      hProperties: { dataRefs: refs.join(","), dataSpaced: "true", dataFound: "true" },
    },
    children: [],
  };
}
