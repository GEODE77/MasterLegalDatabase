import Link from "next/link";
import type { ReactElement } from "react";

import { getRelationshipCoverageReport } from "@/lib/product/productIndex";

export const dynamic = "force-dynamic";

export default function RelationshipsPage(): ReactElement {
  const report = getRelationshipCoverageReport();
  const coveragePercent = Math.round((report?.ccrRelationshipCoverageRatio ?? 0) * 100);

  return (
    <main className="app-product-page">
      <section className="app-hero compact">
        <p>Relationship Health</p>
        <h2>Measure crosswalk coverage before building a visual graph.</h2>
        <span>
          Step 9 keeps the early graph as a structured relationship panel in Explore. A visual graph
          stays queued until relationship coverage and evidence are stronger.
        </span>
      </section>

      <section className="profile-summary" aria-label="Relationship coverage summary">
        <div>
          <span>Total relationships</span>
          <strong>{(report?.totalRelationships ?? 0).toLocaleString("en-US")}</strong>
        </div>
        <div>
          <span>CCR coverage</span>
          <strong>{coveragePercent}%</strong>
        </div>
        <div>
          <span>Missing evidence</span>
          <strong>{(report?.totalMissingEvidence ?? 0).toLocaleString("en-US")}</strong>
        </div>
        <div>
          <span>Visual graph</span>
          <strong>{report?.visualGraphReady ? "Ready" : "Queued"}</strong>
        </div>
      </section>

      <section className="app-list-panel" aria-label="Relationship graph boundary">
        <header>
          <div>
            <span>Graph Boundary</span>
            <h2>Why graph work stays later</h2>
          </div>
        </header>
        <article>
          <span>{report?.structuredRelationshipPanelReady ? "Panel ready" : "Panel limited"}</span>
          <strong>Use structured relationship panels first</strong>
          <p>
            {report?.visualGraphDeferredReason ??
              "Generate relationship coverage to decide when graph work is ready."}
          </p>
          <Link href="/app/explore">Open Explore relationship panel</Link>
        </article>
      </section>

      <section className="app-list-panel" aria-label="Crosswalk coverage">
        <header>
          <div>
            <span>Crosswalk Coverage</span>
            <h2>Measured relationship sources</h2>
          </div>
        </header>
        {(report?.coverageRecords ?? []).map((record) => (
          <article key={record.crosswalkFile}>
            <span>{record.coverageStatus}</span>
            <strong>{record.crosswalkFile}</strong>
            <p>
              {record.relationshipCount.toLocaleString("en-US")} relationships across{" "}
              {record.uniqueSourceCount.toLocaleString("en-US")} sources and{" "}
              {record.uniqueTargetCount.toLocaleString("en-US")} targets.
            </p>
            <p>
              Missing evidence: {record.missingEvidenceCount.toLocaleString("en-US")} | Low
              confidence: {record.lowConfidenceCount.toLocaleString("en-US")} | Duplicates:{" "}
              {record.duplicateCount.toLocaleString("en-US")}
            </p>
          </article>
        ))}
      </section>

      <section className="app-list-panel" aria-label="Recommended relationship work">
        <header>
          <div>
            <span>Next Actions</span>
            <h2>Relationship improvements to queue</h2>
          </div>
        </header>
        {(report?.recommendedNextActions ?? []).map((action) => (
          <article key={action}>
            <span>Queued</span>
            <strong>{action}</strong>
          </article>
        ))}
      </section>
    </main>
  );
}
