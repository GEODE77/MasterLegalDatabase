import Link from "next/link";
import type { ReactElement } from "react";

import {
  getImpactResults,
  getProductProfile,
  getRuleUnitReadiness,
  type ImpactResult,
} from "@/lib/product/productIndex";

export const dynamic = "force-dynamic";

const LEVELS: ImpactResult["level"][] = [
  "High Impact",
  "Medium Impact",
  "Low Impact",
  "Informational",
  "Unknown",
];

export default function ImpactPage(): ReactElement {
  const profile = getProductProfile();
  const readiness = getRuleUnitReadiness();
  const results = getImpactResults(16);
  const groupedResults = groupByLevel(results);

  return (
    <main className="app-product-page">
      <section className="app-hero compact">
        <p>Impact Lens</p>
        <h2>Rank source-backed signals for the current operating profile.</h2>
        <span>
          This deterministic MVP explains why each item appears. It is a review tool, not a legal
          conclusion. Requirement status:{" "}
          {readiness.candidateFallbackActive ? "candidate review signals" : "validated rule units"}.
        </span>
      </section>

      <section className="profile-summary" aria-label="Current profile">
        <div>
          <span>Industry</span>
          <strong>{profile.industry}</strong>
        </div>
        <div>
          <span>Jurisdiction</span>
          <strong>{profile.jurisdiction}</strong>
        </div>
        <div>
          <span>Operations</span>
          <strong>{profile.operations.join(", ")}</strong>
        </div>
      </section>

      <section className="impact-groups" aria-label="Impact results">
        {LEVELS.map((level) => {
          const levelResults = groupedResults.get(level) ?? [];

          if (levelResults.length === 0) {
            return null;
          }

          return (
            <section className="impact-group" key={level}>
              <header>
                <h2>{level}</h2>
                <span>{levelResults.length} source-backed signals</span>
              </header>
              <div className="impact-results">
                {levelResults.map((result) => (
                  <article key={result.regulation.id}>
                    <header>
                      <span>{result.level}</span>
                      <strong>{result.score}</strong>
                    </header>
                    <h2>{result.regulation.citation}</h2>
                    <p>{result.regulation.title}</p>
                    <ul>
                      {result.reasons.map((reason) => (
                        <li key={reason}>{reason}</li>
                      ))}
                    </ul>
                    <blockquote>{result.evidence}</blockquote>
                    <small>{sourceSummary(result)}</small>
                    <Link href={`/app/explore?id=${encodeURIComponent(result.regulation.id)}`}>Review source</Link>
                  </article>
                ))}
              </div>
            </section>
          );
        })}
      </section>
    </main>
  );
}

function sourceSummary(result: ImpactResult): string {
  const hasValidatedRuleUnits = result.regulation.requirements.some(
    (requirement) => requirement.sourceType === "validated_rule_unit",
  );

  return hasValidatedRuleUnits ? "Uses validated rule-unit data." : "Uses candidate review signals.";
}

function groupByLevel(results: ImpactResult[]): Map<ImpactResult["level"], ImpactResult[]> {
  const grouped = new Map<ImpactResult["level"], ImpactResult[]>();

  for (const result of results) {
    grouped.set(result.level, [...(grouped.get(result.level) ?? []), result]);
  }

  return grouped;
}
