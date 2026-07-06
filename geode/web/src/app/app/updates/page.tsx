import Link from "next/link";
import type { ReactElement } from "react";

import {
  getProductUpdates,
  getUpdateLedger,
  getUpdateLedgerSummary,
} from "@/lib/product/productIndex";

export const dynamic = "force-dynamic";

export default function UpdatesPage(): ReactElement {
  const updates = getProductUpdates();
  const ledger = getUpdateLedger(25);
  const ledgerSummary = getUpdateLedgerSummary();

  return (
    <main className="app-product-page">
      <section className="app-hero compact">
        <p>Updates</p>
        <h2>Track source-backed corpus updates before full text diff.</h2>
        <span>
          This view reports layer freshness and the Update Ledger. Full text diff remains queued
          until stable version storage is available.
        </span>
      </section>

      <section className="profile-summary" aria-label="Update ledger summary">
        <div>
          <span>Update Ledger</span>
          <strong>{(ledgerSummary?.eventsWritten ?? ledger.length).toLocaleString("en-US")}</strong>
        </div>
        <div>
          <span>Full text diff</span>
          <strong>{ledgerSummary?.fullDiffReady ? "Ready" : "Queued"}</strong>
        </div>
        <div>
          <span>Timeline events</span>
          <strong>{(ledgerSummary?.timelineEvents ?? 0).toLocaleString("en-US")}</strong>
        </div>
        <div>
          <span>Log events</span>
          <strong>{(ledgerSummary?.updateLogEvents ?? 0).toLocaleString("en-US")}</strong>
        </div>
      </section>

      <section className="app-list-panel" aria-label="Corpus updates">
        <header>
          <div>
            <span>Layer Freshness</span>
            <h2>Current corpus status</h2>
          </div>
        </header>
        {updates.map((update) => (
          <article key={`${update.label}-${update.date}`}>
            <span>{update.date}</span>
            <strong>{update.label}</strong>
            <p>{update.description}</p>
            <Link href={update.href}>Open related view</Link>
          </article>
        ))}
      </section>

      <section className="app-list-panel" aria-label="Update ledger events">
        <header>
          <div>
            <span>Update Ledger</span>
            <h2>Recent source-backed events</h2>
          </div>
          <p>{ledgerSummary?.nextAction ?? "Generate the update ledger to populate this view."}</p>
        </header>
        {ledger.map((event) => (
          <article key={event.eventId}>
            <span>{event.eventDate}</span>
            <strong>{event.title}</strong>
            <p>{event.description}</p>
            <p>
              Source: {event.sourcePath || "control plane"} | Diff:{" "}
              {event.fullTextDiffAvailable ? "available" : "not started"}
            </p>
          </article>
        ))}
      </section>
    </main>
  );
}
