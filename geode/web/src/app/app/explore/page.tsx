import Link from "next/link";
import type { ReactElement } from "react";

import {
  getProductRegulation,
  getRuleUnitReadiness,
  searchProductRegulations,
  type ProductRegulation,
} from "@/lib/product/productIndex";

export const dynamic = "force-dynamic";

type ExplorePageProps = {
  searchParams?: Promise<{ id?: string; q?: string }>;
};

export default async function ExplorePage({ searchParams }: ExplorePageProps): Promise<ReactElement> {
  const params = await searchParams;
  const query = params?.q?.trim() || "air quality";
  const regulations = searchProductRegulations(query, 24);
  const selected = params?.id ? getProductRegulation(params.id) : regulations[0] ?? null;
  const readiness = getRuleUnitReadiness();

  return (
    <main className="app-product-page">
      <section className="app-hero compact">
        <p>Explore</p>
        <h2>Read source text beside relationships and evidence.</h2>
        <span>
          This view starts with CCR because it is the strongest completed source layer in the current
          corpus. Requirement status:{" "}
          {readiness.candidateFallbackActive ? "candidate review signals" : "validated rule units"}.
        </span>
      </section>

      <form className="app-search-row" action="/app/explore">
        <label htmlFor="explore-search">Search CCR source records</label>
        <input id="explore-search" name="q" placeholder="air quality, waste, permits" defaultValue={query} />
        <button type="submit">Search</button>
      </form>

      <section className="explore-layout" aria-label="Regulatory explorer">
        <aside className="explore-list" aria-label="Documents">
          {regulations.map((regulation) => (
            <Link
              className={selected?.id === regulation.id ? "is-active" : ""}
              href={`/app/explore?id=${encodeURIComponent(regulation.id)}&q=${encodeURIComponent(query)}`}
              key={regulation.id}
            >
              <span>{regulation.citation}</span>
              <strong>{regulation.title}</strong>
            </Link>
          ))}
        </aside>

        {selected ? <SelectedRegulation regulation={selected} /> : <EmptyExploreState />}
      </section>
    </main>
  );
}

function SelectedRegulation({ regulation }: { regulation: ProductRegulation }): ReactElement {
  return (
    <>
      <article className="explore-reader">
        <header>
          <span>{regulation.department}</span>
          <h2>{regulation.title}</h2>
          <p>
            {regulation.citation} / {regulation.agency}
          </p>
          {regulation.sourceUrl ? <a href={regulation.sourceUrl}>Official source</a> : null}
        </header>

        {regulation.sections.length > 0 ? (
          <nav className="explore-outline" aria-label="Document outline">
            <p>Document outline</p>
            {regulation.sections.slice(0, 16).map((section) => (
              <a href={`#${section.id}`} key={section.id}>
                {section.title}
              </a>
            ))}
          </nav>
        ) : null}

        <section className="explore-source-text" aria-label="Source text">
          {renderSourceText(regulation)}
        </section>
      </article>

      <aside className="explore-evidence" aria-label="Relationships and requirements">
        <section>
          <h2>Relationships</h2>
          {regulation.relationships.length > 0 ? (
            regulation.relationships.map((relationship) => (
              <article key={`${relationship.relationship}-${relationship.targetId}`}>
                <span>{relationship.relationship}</span>
                <strong>{relationship.targetId}</strong>
                <p>{relationship.evidence ?? "Relationship evidence is not available in this record."}</p>
              </article>
            ))
          ) : (
            <p>No relationship records are available for this regulation yet.</p>
          )}
        </section>

        <section>
          <h2>Requirements</h2>
          {regulation.requirements.length > 0 ? (
            regulation.requirements.map((requirement) => (
              <article key={requirement.id}>
                <span>{labelRequirementSource(requirement.sourceType)}</span>
                <strong>{requirement.title}</strong>
                <small>
                  {requirement.sourceLabel} / {requirement.actionType}
                </small>
                {requirement.regulatedEntity ? <small>{requirement.regulatedEntity}</small> : null}
                <p>{requirement.evidence}</p>
                <small>{Math.round(requirement.confidence * 100)}% confidence</small>
              </article>
            ))
          ) : (
            <p>No requirement signals were found. This does not mean no obligation exists.</p>
          )}
        </section>
      </aside>
    </>
  );
}

function renderSourceText(regulation: ProductRegulation): ReactElement[] {
  const sectionIds = new Map(regulation.sections.map((section) => [section.title, section.id]));
  const elements: ReactElement[] = [];
  const lines = regulation.body
    .slice(0, 12000)
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)
    .filter((line) => !/^\d+$/.test(line));

  for (const [index, line] of lines.entries()) {
    const headingId = sectionIds.get(cleanHeading(line));

    if (headingId) {
      elements.push(
        <h3 id={headingId} key={`${headingId}-${index}`}>
          {cleanHeading(line)}
        </h3>,
      );
      continue;
    }

    elements.push(<p key={`${line.slice(0, 24)}-${index}`}>{line}</p>);
  }

  return elements;
}

function cleanHeading(value: string): string {
  return value.replace(/^#+\s*/, "").replace(/^[^ ]+\.\s*/, "").replace(/_/g, " ");
}

function labelRequirementSource(sourceType: ProductRegulation["requirements"][number]["sourceType"]): string {
  return sourceType === "validated_rule_unit" ? "Validated rule unit" : "Candidate signal";
}

function EmptyExploreState(): ReactElement {
  return (
    <section className="explore-empty">
      <h2>No source record selected</h2>
      <p>Try a different search term or return to the default CCR source list.</p>
    </section>
  );
}
