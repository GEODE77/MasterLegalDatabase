import Link from "next/link";
import { notFound } from "next/navigation";
import type { ReactElement } from "react";

import {
  findRegulationReference,
  getRegulationById,
  getRelatedRegulations,
} from "@/lib/search/searchRegulations";

type RegulationPageProps = {
  params: Promise<{ id: string }>;
};

type ArticleBlock =
  | { kind: "heading"; level: 2 | 3; text: string }
  | { kind: "paragraph"; text: string };

type ReferencePreview = {
  citation: string;
  title: string;
};

export default async function RegulationPage({ params }: RegulationPageProps): Promise<ReactElement> {
  const { id } = await params;
  const regulation = getRegulationById(id);

  if (!regulation) {
    notFound();
  }

  const related = getRelatedRegulations(regulation.id);
  const blocks = toArticleBlocks(regulation.body);
  const footnotes = collectFootnotes(blocks);
  const referencePreviews = buildReferencePreviews(footnotes);

  return (
    <main className="regulation-document-page">
      <article className="regulation-document">
        <header className="regulation-citation-strip">
          <span>{regulation.agency}</span>
          <span>{regulation.citation}</span>
          <span>{regulation.effectiveDate ? formatDate(regulation.effectiveDate) : "Effective date not stated"}</span>
        </header>

        <section className="regulation-document-head">
          <h1>{regulation.title}</h1>
        </section>

        <section className="regulation-article-body">
          {blocks.map((block, index) => {
            if (block.kind === "heading") {
              const Heading = block.level === 2 ? "h2" : "h3";
              return <Heading key={`${block.text}-${index}`}>{block.text}</Heading>;
            }

            return (
              <ParagraphWithRefs
                footnotes={footnotes}
                key={`${block.text}-${index}`}
                previews={referencePreviews}
                text={block.text}
              />
            );
          })}
        </section>

        {footnotes.length > 0 ? (
          <footer className="regulation-footnotes">
            <h2>Notes</h2>
            <ol>
              {footnotes.map((note, index) => (
                <li key={note}>
                  <span>{index + 1}.</span>{" "}
                  <ReferenceText
                    index={index}
                    preview={referencePreviews.get(note)}
                    reference={note}
                    showNumber={false}
                  />
                </li>
              ))}
            </ol>
          </footer>
        ) : null}

        {related.length > 0 ? (
          <section className="regulation-related">
            <h2>Related</h2>
            <ul>
              {related.map((item) => (
                <li key={item.id}>
                  <Link href={`/regulations/${encodeURIComponent(item.id)}`}>
                    {item.citation}. {item.title}
                  </Link>
                </li>
              ))}
            </ul>
          </section>
        ) : null}
      </article>
    </main>
  );
}

function toArticleBlocks(body: string): ArticleBlock[] {
  const lines = body
    .replace(/\r/g, "")
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean)
    .filter((line) => !/^\d+$/.test(line))
    .filter((line) => !/^code of colorado regulations$/i.test(line))
    .filter((line) => !/^secretary of state$/i.test(line))
    .filter((line) => !/^state of colorado$/i.test(line))
    .filter((line) => !/^_+$/.test(line));

  const blocks: ArticleBlock[] = [];
  let paragraph: string[] = [];

  function flushParagraph(): void {
    if (paragraph.length === 0) {
      return;
    }

    blocks.push({ kind: "paragraph", text: paragraph.join(" ") });
    paragraph = [];
  }

  for (const line of lines) {
    if (line.startsWith("#### ")) {
      flushParagraph();
      blocks.push({ kind: "heading", level: 2, text: cleanHeading(line) });
      continue;
    }

    if (isMajorHeading(line)) {
      flushParagraph();
      blocks.push({ kind: "heading", level: 2, text: line });
      continue;
    }

    if (isSectionHeading(line)) {
      flushParagraph();
      blocks.push({ kind: "heading", level: 3, text: line });
      continue;
    }

    paragraph.push(line);
  }

  flushParagraph();
  return blocks.slice(0, 90);
}

function cleanHeading(value: string): string {
  return value.replace(/^#+\s*/, "").replace(/^[^ ]+\.\s*/, "").replace(/_/g, " ");
}

function isMajorHeading(value: string): boolean {
  return /^(PART|RULE|REGULATION|APPENDIX)\s+[A-Z0-9]/.test(value) || /^[A-Z][A-Z\s,;()/-]{14,}$/.test(value);
}

function isSectionHeading(value: string): boolean {
  return /^([IVXLCDM]+\.|[A-Z]\.|[A-Z]\.[A-Z]\.|[0-9]+\.)\s*$/.test(value)
    || /^([IVXLCDM]+\.|[A-Z]\.[A-Z]\.|[0-9]+\.)\s+[A-Z0-9]/.test(value);
}

function collectFootnotes(blocks: ArticleBlock[]): string[] {
  const notes = new Set<string>();

  for (const block of blocks) {
    if (block.kind !== "paragraph") {
      continue;
    }

    for (const reference of block.text.matchAll(referencePattern())) {
      notes.add(reference[0]);
    }
  }

  return Array.from(notes).slice(0, 24);
}

function buildReferencePreviews(footnotes: string[]): Map<string, ReferencePreview> {
  const previews = new Map<string, ReferencePreview>();

  for (const note of footnotes) {
    const target = findRegulationReference(note);
    previews.set(note, {
      citation: target?.citation ?? note,
      title: target?.title ?? "Referenced authority in this document.",
    });
  }

  return previews;
}

function ParagraphWithRefs({
  footnotes,
  previews,
  text,
}: {
  footnotes: string[];
  previews: Map<string, ReferencePreview>;
  text: string;
}): ReactElement {
  const parts: Array<string | ReactElement> = [];
  let lastIndex = 0;

  for (const match of text.matchAll(referencePattern())) {
    const reference = match[0];
    const index = match.index ?? 0;
    const noteIndex = footnotes.indexOf(reference);

    if (index > lastIndex) {
      parts.push(text.slice(lastIndex, index));
    }

    parts.push(
      <ReferenceText
        index={noteIndex}
        key={`${reference}-${index}`}
        preview={previews.get(reference)}
        reference={reference}
        showNumber={noteIndex >= 0}
      />,
    );
    lastIndex = index + reference.length;
  }

  if (lastIndex < text.length) {
    parts.push(text.slice(lastIndex));
  }

  return <p>{parts}</p>;
}

function ReferenceText({
  index,
  preview,
  reference,
  showNumber,
}: {
  index: number;
  preview?: ReferencePreview;
  reference: string;
  showNumber: boolean;
}): ReactElement {
  return (
    <span className="regulation-cross-reference" tabIndex={0}>
      {reference}
      {showNumber ? <sup>{index + 1}</sup> : null}
      <span className="regulation-reference-preview">
        <strong>{preview?.citation ?? reference}</strong>
        <span>{preview?.title ?? "Referenced authority in this document."}</span>
      </span>
    </span>
  );
}

function referencePattern(): RegExp {
  return /\b(?:\d+\s+CCR\s+\d+-\d+|C\.?R\.?S\.?\s*(?:section\s*)?\d{1,2}-\d{1,3}-\d{1,4}|(?:section|sections)\s+[IVXLCDM0-9A-Z.]+|(?:\d+\s+U\.?S\.?C\.?|\d+\s+C\.?F\.?R\.?)\s*[A-Za-z0-9().-]*)/gi;
}

function formatDate(value: string): string {
  return new Intl.DateTimeFormat("en", {
    day: "numeric",
    month: "short",
    timeZone: "UTC",
    year: "numeric",
  }).format(new Date(value));
}
