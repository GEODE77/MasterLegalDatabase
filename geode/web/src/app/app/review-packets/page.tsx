import Link from "next/link";
import type { ReactElement } from "react";

import {
  getRuleUnitReviewPacketSummary,
  getRuleUnitReviewPackets,
  type RuleUnitReviewPacket,
  type RuleUnitReviewStatusFilter,
} from "@/lib/product/productIndex";

export const dynamic = "force-dynamic";

type ReviewPacketsPageProps = {
  searchParams?: Promise<{ status?: string }>;
};

export default async function ReviewPacketsPage({
  searchParams,
}: ReviewPacketsPageProps): Promise<ReactElement> {
  const params = await searchParams;
  const status = normalizeStatus(params?.status);
  const summary = getRuleUnitReviewPacketSummary();
  const packets = getRuleUnitReviewPackets(50, status);

  return (
    <main className="app-product-page">
      <section className="app-hero compact">
        <p>Review Packets</p>
        <h2>Formal review handoff for source-backed rule units.</h2>
        <span>
          Each packet keeps the source sentence, quality issues, current extraction, decision state,
          and reliance boundary. Packets do not change canonical law.
        </span>
      </section>

      <section className="profile-summary" aria-label="Review packet status">
        <div>
          <span>Packets</span>
          <strong>{(summary?.packetsWritten ?? packets.length).toLocaleString("en-US")}</strong>
        </div>
        <div>
          <span>Pending</span>
          <strong>{(summary?.pending ?? 0).toLocaleString("en-US")}</strong>
        </div>
        <div>
          <span>Change ready</span>
          <strong>{(summary?.canonicalChangeReady ?? 0).toLocaleString("en-US")}</strong>
        </div>
      </section>

      <section className="review-filter-row" aria-label="Review packet filters">
        {packetFilters(summary).map((filter) => (
          <a
            className={filter.key === status ? "is-active" : ""}
            href={`/app/review-packets?status=${filter.key}`}
            key={filter.key}
          >
            <span>{filter.label}</span>
            <strong>{filter.count.toLocaleString("en-US")}</strong>
          </a>
        ))}
      </section>

      <section className="review-list" aria-label="Formal review packets">
        <header className="review-list-header">
          <div>
            <span>Current filter</span>
            <strong>{statusLabel(status)}</strong>
          </div>
          <p>Showing {packets.length.toLocaleString("en-US")} packets.</p>
        </header>
        {packets.length > 0 ? (
          packets.map((packet) => <ReviewPacketCard key={packet.packetId} packet={packet} />)
        ) : (
          <article>
            <header>
              <span>No packets</span>
              <strong>No matching review packets were found.</strong>
              <Link href="/app/review">Review queue</Link>
            </header>
          </article>
        )}
      </section>
    </main>
  );
}

function ReviewPacketCard({ packet }: { packet: RuleUnitReviewPacket }): ReactElement {
  return (
    <article>
      <header>
        <span>{packet.priority} priority</span>
        <strong>{packet.ruleUnitId}</strong>
        <Link href={`/app/explore?id=${encodeURIComponent(packet.parentRegulationId)}`}>Source</Link>
      </header>
      <div className="review-actions" aria-label="Packet state">
        <span>{statusLabel(packet.status)}</span>
        {packet.canonicalChangeReady ? <span>Canonical change ready</span> : null}
        <span>{packet.reviewId}</span>
      </div>
      <p>{packet.reviewerInstruction}</p>
      <blockquote>{packet.sourceSentence}</blockquote>
      <dl>
        <div>
          <dt>Section</dt>
          <dd>{packet.sourceSection}</dd>
        </div>
        <div>
          <dt>Issues</dt>
          <dd>{packet.issues.length.toLocaleString("en-US")}</dd>
        </div>
        <div>
          <dt>Suggested</dt>
          <dd>{packet.suggestedOutcomes.join(", ") || "None"}</dd>
        </div>
      </dl>
      {packet.sourceContext ? <small>{packet.sourceContext}</small> : null}
      <small>{packet.relianceBoundary}</small>
    </article>
  );
}

function normalizeStatus(value: string | undefined): RuleUnitReviewStatusFilter {
  if (
    value === "all"
    || value === "approved"
    || value === "change_ready"
    || value === "pending"
    || value === "quarantined"
    || value === "revised"
    || value === "split"
  ) {
    return value;
  }

  return "pending";
}

function packetFilters(summary: ReturnType<typeof getRuleUnitReviewPacketSummary>): Array<{
  count: number;
  key: RuleUnitReviewStatusFilter;
  label: string;
}> {
  return [
    { count: summary?.pending ?? 0, key: "pending", label: "Pending" },
    { count: summary?.approved ?? 0, key: "approved", label: "Approved" },
    { count: summary?.revised ?? 0, key: "revised", label: "Revised" },
    { count: summary?.split ?? 0, key: "split", label: "Split" },
    { count: summary?.quarantined ?? 0, key: "quarantined", label: "Quarantined" },
    {
      count: summary?.canonicalChangeReady ?? 0,
      key: "change_ready",
      label: "Change ready",
    },
    { count: summary?.packetsWritten ?? 0, key: "all", label: "All" },
  ];
}

function statusLabel(status: RuleUnitReviewStatusFilter): string {
  if (status === "all") {
    return "All";
  }

  if (status === "change_ready") {
    return "Canonical change ready";
  }

  if (status === "approved") {
    return "Approved";
  }

  if (status === "quarantined") {
    return "Quarantined";
  }

  return status.charAt(0).toUpperCase() + status.slice(1);
}
