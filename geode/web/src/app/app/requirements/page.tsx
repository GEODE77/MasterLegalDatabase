import Link from "next/link";
import type { ReactElement } from "react";

import {
  getRuleUnitReadiness,
  searchRequirements,
  type RequirementSearchResult,
} from "@/lib/product/productIndex";

export const dynamic = "force-dynamic";

type RequirementsPageProps = {
  searchParams?: Promise<{ q?: string }>;
};

export default async function RequirementsPage({
  searchParams,
}: RequirementsPageProps): Promise<ReactElement> {
  const params = await searchParams;
  const query = params?.q?.trim() || "air quality permitting reporting";
  const requirements = searchRequirements(query, 30);
  const readiness = getRuleUnitReadiness();

  return (
    <main className="app-product-page">
      <section className="app-hero compact">
        <p>Requirements</p>
        <h2>Find operational duties before opening the full source.</h2>
        <span>
          Results come from rule units when available and from source-backed candidate signals
          when a source has not been fully reviewed. Requirement status:{" "}
          {readiness.candidateFallbackActive ? "candidate review signals" : "validated rule units"}.
        </span>
      </section>

      <form className="app-search-row" action="/app/requirements">
        <label htmlFor="requirements-search">Search requirements</label>
        <input
          id="requirements-search"
          name="q"
          placeholder="permits, reporting, inspections, waste"
          defaultValue={query}
        />
        <button type="submit">Search</button>
      </form>

      <section className="path-list" aria-label="Requirement results">
        {requirements.length > 0 ? (
          requirements.map((requirement, index) => (
            <RequirementCard
              key={`${requirement.regulationId}-${requirement.id}`}
              order={index + 1}
              requirement={requirement}
            />
          ))
        ) : (
          <article>
            <span>0</span>
            <div>
              <strong>No requirement signals found</strong>
              <p>Try a broader topic such as air quality, waste, permits, or reporting.</p>
            </div>
          </article>
        )}
      </section>
    </main>
  );
}

function RequirementCard({
  order,
  requirement,
}: {
  order: number;
  requirement: RequirementSearchResult;
}): ReactElement {
  return (
    <article>
      <span>{order}</span>
      <div>
        <strong>{requirement.title}</strong>
        <p>{requirement.actionRequired}</p>
        <small>
          {requirement.sourceType === "validated_rule_unit" ? "Validated rule unit" : "Candidate signal"} /{" "}
          {requirement.actionType} / {Math.round(requirement.confidence * 100)}% confidence
        </small>
        {requirement.regulatedEntity ? <small>{requirement.regulatedEntity}</small> : null}
        <blockquote>{requirement.evidence}</blockquote>
        <small>{requirement.reason}</small>
        <Link href={`/app/explore?id=${encodeURIComponent(requirement.regulationId)}`}>
          {requirement.citation} / {requirement.regulationTitle}
        </Link>
      </div>
    </article>
  );
}
