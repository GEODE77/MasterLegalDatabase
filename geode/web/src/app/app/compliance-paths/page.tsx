import Link from "next/link";
import type { ReactElement } from "react";

import { getCompliancePath, getProductProfile, getRuleUnitReadiness } from "@/lib/product/productIndex";

export const dynamic = "force-dynamic";

export default function CompliancePathsPage(): ReactElement {
  const profile = getProductProfile();
  const readiness = getRuleUnitReadiness();
  const steps = getCompliancePath(12);

  return (
    <main className="app-product-page">
      <section className="app-hero compact">
        <p>Compliance Paths</p>
        <h2>Convert source-backed signals into review steps.</h2>
        <span>
          These are review paths generated from source evidence. They should guide follow-up, not
          replace legal review. Requirement status:{" "}
          {readiness.candidateFallbackActive ? "candidate review signals" : "validated rule units"}.
        </span>
      </section>

      <section className="profile-summary" aria-label="Path profile">
        <div>
          <span>Industry</span>
          <strong>{profile.industry}</strong>
        </div>
        <div>
          <span>Operations</span>
          <strong>{profile.operations.join(", ")}</strong>
        </div>
        <div>
          <span>Priorities</span>
          <strong>{profile.priorities.join(", ")}</strong>
        </div>
      </section>

      <section className="path-list" aria-label="Compliance review path">
        {steps.length > 0 ? (
          steps.map((step) => (
            <article key={`${step.stepOrder}-${step.sourceId}`}>
              <span>{step.stepOrder}</span>
              <div>
                <strong>{step.title}</strong>
                <p>{step.description}</p>
                <small>{step.sourceType === "validated_rule_unit" ? "Validated rule unit" : "Candidate signal"}</small>
                <blockquote>{step.evidence}</blockquote>
                <small>{step.reason}</small>
                {step.regulatedEntity ? <small>{step.regulatedEntity}</small> : null}
                <Link href={`/app/explore?id=${encodeURIComponent(step.sourceId)}`}>{step.citation}</Link>
              </div>
            </article>
          ))
        ) : (
          <article>
            <span>0</span>
            <div>
              <strong>No review steps generated yet</strong>
              <p>Geode did not find enough source-backed requirement signals for this profile.</p>
            </div>
          </article>
        )}
      </section>
    </main>
  );
}
