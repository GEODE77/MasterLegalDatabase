import type { ReactElement } from "react";

import {
  getFullTextDiffSummary,
  getMasterReadinessReport,
  getProductionReadinessReport,
  getRemainingWorkQueue,
  getRetrievalCatalogSummary,
  getSourceRepairDashboard,
  getSourceFreshnessReport,
  getSourceStrengthReport,
} from "@/lib/product/productIndex";

export const dynamic = "force-dynamic";

export default function SystemPage(): ReactElement {
  const diff = getFullTextDiffSummary();
  const freshness = getSourceFreshnessReport();
  const production = getProductionReadinessReport();
  const queue = getRemainingWorkQueue();
  const retrieval = getRetrievalCatalogSummary();
  const sourceStrength = getSourceStrengthReport();
  const sourceRepair = getSourceRepairDashboard();
  const masterReadiness = getMasterReadinessReport();

  return (
    <main className="app-product-page">
      <section className="app-hero compact">
        <p>System Readiness</p>
        <h2>See what is complete, what is queued, and what needs people.</h2>
        <span>
          This page brings together retrieval coverage, local diff status, source freshness,
          production controls, and the remaining work queue.
        </span>
      </section>

      <section className="app-list-panel" aria-label="Master readiness boundary">
        <header>
          <div>
            <span>{masterReadiness?.localSystemUsable ? "Locally usable" : "Local use blocked"}</span>
            <h2>Reliance boundary</h2>
          </div>
        </header>
        <article>
          <span>
            {masterReadiness?.externalRelianceReady
              ? "External reliance ready"
              : "External reliance blocked"}
          </span>
          <strong>{masterReadiness?.boundary ?? "Readiness report is not available."}</strong>
          <p>
            {(masterReadiness?.blockers ?? []).length > 0
              ? `Blockers: ${(masterReadiness?.blockers ?? []).join(", ")}.`
              : "No blockers are listed in the current readiness report."}
          </p>
        </article>
      </section>

      <section className="profile-summary" aria-label="System readiness summary">
        <div>
          <span>Retrieval records</span>
          <strong>{(retrieval?.recordsWritten ?? 0).toLocaleString("en-US")}</strong>
        </div>
        <div>
          <span>Text files checked</span>
          <strong>{(diff?.filesChecked ?? 0).toLocaleString("en-US")}</strong>
        </div>
        <div>
          <span>Stale layers</span>
          <strong>{freshness?.staleLayers ?? 0}</strong>
        </div>
        <div>
          <span>Open work</span>
          <strong>{queue?.openItems ?? 0}</strong>
        </div>
        <div>
          <span>Source score</span>
          <strong>{Math.round((sourceStrength?.averageSourceStrengthScore ?? 0) * 100)}%</strong>
        </div>
      </section>

      <section className="app-list-panel" aria-label="Source evidence strength">
        <header>
          <div>
            <span>Source Evidence</span>
            <h2>How much of the corpus is anchored to preserved source material</h2>
          </div>
        </header>
        <article>
          <span>Records scored</span>
          <strong>{(sourceStrength?.recordsScored ?? 0).toLocaleString("en-US")}</strong>
          <p>{sourceStrength?.boundary ?? "Source-strength report is not available."}</p>
        </article>
        {Object.entries(sourceStrength?.levelCounts ?? {}).map(([level, count]) => (
          <article key={level}>
            <span>{level.replaceAll("_", " ")}</span>
            <strong>{count.toLocaleString("en-US")} records</strong>
          </article>
        ))}
      </section>

      <section className="app-list-panel" aria-label="Source repair dashboard">
        <header>
          <div>
            <span>{sourceRepair?.openItems ?? 0} open</span>
            <h2>Source repair dashboard</h2>
          </div>
        </header>
        <article>
          <span>Relationship review rows</span>
          <strong>{(sourceRepair?.relationshipReviewRows ?? 0).toLocaleString("en-US")}</strong>
          <p>
            Freshness refresh items: {(sourceRepair?.freshnessRefreshItems ?? 0).toLocaleString("en-US")}.
            Human review ready: {sourceRepair?.humanReviewReadyForReliance ? "yes" : "no"}.
          </p>
        </article>
        {(sourceRepair?.items ?? []).map((item) => (
          <article key={item.id}>
            <span>{item.status}</span>
            <strong>{item.title}</strong>
            <p>{item.nextAction}</p>
          </article>
        ))}
      </section>

      <section className="app-list-panel" aria-label="Production controls">
        <header>
          <div>
            <span>{production?.systemControlsPresent ? "Controls present" : "Controls blocked"}</span>
            <h2>System control readiness</h2>
          </div>
        </header>
        {production ? (
          <article>
            <span>Boundary</span>
            <strong>{production.boundary.meaning}</strong>
            <p>{production.boundary.notImplied}</p>
            <p>{production.boundary.externalRelianceCondition}</p>
          </article>
        ) : null}
        {(production?.controls ?? []).map((control) => (
          <article key={control.controlId}>
            <span>{control.status}</span>
            <strong>{control.title}</strong>
            <p>{control.detail}</p>
            {control.evidencePath ? <p>Evidence: {control.evidencePath}</p> : null}
          </article>
        ))}
      </section>

      <section className="app-list-panel" aria-label="Remaining work queue">
        <header>
          <div>
            <span>Queued Work</span>
            <h2>Items that still need people or outside refresh</h2>
          </div>
        </header>
        {(queue?.items ?? []).map((item) => (
          <article key={item.id}>
            <span>{item.category}</span>
            <strong>{item.title}</strong>
            <p>{item.reason}</p>
            <p>{item.nextAction}</p>
          </article>
        ))}
      </section>

      <section className="app-list-panel" aria-label="Freshness by layer">
        <header>
          <div>
            <span>Freshness</span>
            <h2>Local manifest status</h2>
          </div>
        </header>
        {(freshness?.layers ?? []).map((layer) => (
          <article key={layer.layerId}>
            <span>{layer.freshnessStatus}</span>
            <strong>{layer.layerId}</strong>
            <p>
              {layer.recordCount.toLocaleString("en-US")} records, last checked{" "}
              {layer.lastChecked ?? "unknown"}.
            </p>
          </article>
        ))}
      </section>
    </main>
  );
}
