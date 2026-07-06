import Link from "next/link";
import { notFound } from "next/navigation";
import type { ReactElement } from "react";

import { getAuthorityById } from "@/lib/authority/authorityIndex";

type AuthorityPageProps = {
  params: Promise<{ id: string }>;
};

type ArticleBlock =
  | { kind: "heading"; level: 2 | 3; text: string }
  | { kind: "paragraph"; text: string };

export default async function AuthorityPage({
  params,
}: AuthorityPageProps): Promise<ReactElement> {
  const { id } = await params;
  const authority = getAuthorityById(id);

  if (!authority) {
    notFound();
  }

  const blocks = toArticleBlocks(authority.fullText);

  return (
    <main className="regulation-document-page">
      <article className="regulation-document">
        <header className="regulation-citation-strip">
          <span>{layerLabel(authority.layer)}</span>
          <span>{authority.citation}</span>
          <span>{authority.dataVersion ?? "Current indexed source"}</span>
        </header>

        <section className="regulation-document-head">
          <p>{authority.titleName}</p>
          <h1>{authority.sectionHeading}</h1>
          <p>{[authority.articleName, authority.partName].filter(Boolean).join(" / ")}</p>
          {authority.sourceUrl ? <a href={authority.sourceUrl}>Official source</a> : null}
        </section>

        <section className="regulation-article-body">
          {blocks.map((block, index) => {
            if (block.kind === "heading") {
              const Heading = block.level === 2 ? "h2" : "h3";
              return <Heading key={`${block.text}-${index}`}>{block.text}</Heading>;
            }

            return <p key={`${block.text}-${index}`}>{block.text}</p>;
          })}
        </section>

        {authority.crossReferences.length > 0 ? (
          <section className="regulation-related">
            <h2>CRS References</h2>
            <ul>
              {authority.crossReferences.slice(0, 24).map((reference) => (
                <li key={reference}>
                  <Link href={`/authorities/${encodeURIComponent(reference)}`}>
                    {reference.replace(/^CRS-/, "CRS ")}
                  </Link>
                </li>
              ))}
            </ul>
          </section>
        ) : null}

        {authority.relatedAuthorities.length > 0 ? (
          <section className="regulation-related">
            <h2>Related Authority</h2>
            <ul>
              {authority.relatedAuthorities.map((relation) => (
                <li key={`${relation.relationship}-${relation.id}`}>
                  <Link href={authorityHref(relation.id, relation.layer)}>
                    {relation.title || relation.id.replaceAll("_", " ")}
                  </Link>
                  <span> {relation.relationship}</span>
                </li>
              ))}
            </ul>
          </section>
        ) : null}

        {authority.timelineEvents.length > 0 ? (
          <section className="regulation-related">
            <h2>Timeline</h2>
            <ul>
              {authority.timelineEvents.slice(0, 12).map((event) => (
                <li key={event.eventId}>
                  <span>{event.date}</span>
                  <span> {event.description || event.eventType}</span>
                </li>
              ))}
            </ul>
          </section>
        ) : null}

        {authority.historyNote ? (
          <footer className="regulation-footnotes">
            <h2>Source Note</h2>
            <p>{authority.historyNote}</p>
            {authority.sourceVersions.length > 0 ? (
              <ul>
                {authority.sourceVersions.map((version) => (
                  <li key={`${version.label}-${version.path}`}>
                    <span>{version.label}: </span>
                    <span>{version.path}</span>
                  </li>
                ))}
              </ul>
            ) : null}
          </footer>
        ) : null}
      </article>
    </main>
  );
}

function toArticleBlocks(body: string): ArticleBlock[] {
  const blocks: ArticleBlock[] = [];
  const paragraphs = body
    .replace(/\r/g, "")
    .split(/\n{2,}|\n(?=\(\d+[a-zA-Z]?\)|\([a-z]\)|\([IVXLCDM]+\))/)
    .map((line) => line.trim())
    .filter(Boolean);

  for (const paragraph of paragraphs) {
    if (/^Source:/i.test(paragraph)) {
      blocks.push({ kind: "heading", level: 2, text: "Source" });
      blocks.push({ kind: "paragraph", text: paragraph.replace(/^Source:\s*/i, "") });
      continue;
    }

    blocks.push({ kind: "paragraph", text: paragraph.replace(/\s+/g, " ") });
  }

  return blocks;
}

function authorityHref(id: string, layer?: string | null): string {
  if (layer === "02_Regulations_CCR") {
    return `/regulations/${encodeURIComponent(id)}`;
  }

  if (!layer && /_CCR_/.test(id)) {
    return `/regulations/${encodeURIComponent(id)}`;
  }

  return `/authorities/${encodeURIComponent(id)}`;
}

function layerLabel(layer: string): string {
  if (layer === "01_Statutes_CRS") {
    return "Colorado Revised Statutes";
  }

  if (layer === "02_Regulations_CCR") {
    return "Code of Colorado Regulations";
  }

  if (layer === "03_Legislation") {
    return "Colorado Legislation";
  }

  if (layer === "04_Rulemaking") {
    return "Colorado Rulemaking";
  }

  if (layer === "05_Executive_Orders") {
    return "Colorado Executive Orders";
  }

  if (layer === "06_Session_Laws") {
    return "Colorado Session Laws";
  }

  if (layer === "07_Supplementary") {
    return "Supplementary Authority";
  }

  return "Geode Authority";
}
