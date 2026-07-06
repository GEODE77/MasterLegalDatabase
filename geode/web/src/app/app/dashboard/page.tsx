import Link from "next/link";
import type { ReactElement } from "react";

import { getImpactResults, getRuleUnitReadiness } from "@/lib/product/productIndex";
import { getGeodeIndexStats } from "@/lib/index/geodeIndexStats";

export const dynamic = "force-dynamic";

const WORKFLOWS = [
  {
    description: "Read source text beside citations, relationships, and requirement evidence.",
    href: "/app/explore",
    label: "Explore",
  },
  {
    description: "See which source-backed signals appear most relevant to the current profile.",
    href: "/app/impact",
    label: "Impact Lens",
  },
  {
    description: "Turn evidence into review steps without treating them as legal advice.",
    href: "/app/compliance-paths",
    label: "Compliance Paths",
  },
  {
    description: "Resolve rule units flagged for split, revision, approval, or quarantine.",
    href: "/app/review",
    label: "Rule-Unit Review",
  },
];

export default function AppDashboardPage(): ReactElement {
  const stats = getGeodeIndexStats();
  const impactResults = getImpactResults(3);
  const readiness = getRuleUnitReadiness();

  return (
    <main className="app-product-page">
      <section className="app-hero">
        <p>Product dashboard</p>
        <h2>Source-backed regulatory intelligence is ready for review.</h2>
        <span>
          The current product layer reads from the canonical Geode corpus. It does not replace the
          corpus or write to active download areas.
        </span>
      </section>

      <section className="app-signal-grid" aria-label="Corpus status">
        <div>
          <span>Indexed records</span>
          <strong>{stats.count.toLocaleString("en-US")}</strong>
        </div>
        <div>
          <span>High-priority signals</span>
          <strong>{impactResults.length.toLocaleString("en-US")}</strong>
        </div>
        <div>
          <span>{readiness.quality ? "High-quality rule units" : "Requirement source"}</span>
          <strong>
            {readiness.quality
              ? readiness.quality.highQualityUnits.toLocaleString("en-US")
              : readiness.candidateFallbackActive
                ? "Signals"
                : "Rule units"}
          </strong>
        </div>
      </section>

      <section className="app-workflow-grid" aria-label="Primary workflows">
        {WORKFLOWS.map((workflow) => (
          <Link href={workflow.href} key={workflow.href}>
            <strong>{workflow.label}</strong>
            <span>{workflow.description}</span>
          </Link>
        ))}
      </section>

      <section className="app-list-panel" aria-label="Current high impact signals">
        <header>
          <h2>Current profile signals</h2>
          <Link href="/app/impact">Open Impact Lens</Link>
        </header>
        {impactResults.map((result) => (
          <article key={result.regulation.id}>
            <span>{result.level}</span>
            <strong>{result.regulation.citation}</strong>
            <p>{result.reasons.slice(0, 2).join(" ")}</p>
          </article>
        ))}
      </section>
    </main>
  );
}
