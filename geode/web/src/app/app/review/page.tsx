import type { ReactElement } from "react";

import {
  getRuleUnitApplyProposalSummary,
  getRuleUnitReviewDecisionSummary,
  getRuleUnitReviewQueue,
  getRuleUnitReviewStatusSummary,
  type RuleUnitReviewStatusFilter,
} from "@/lib/product/productIndex";

import ReviewDecisionPanel from "./ReviewDecisionPanel";

export const dynamic = "force-dynamic";

type RuleUnitReviewPageProps = {
  searchParams?: Promise<{ status?: string }>;
};

export default async function RuleUnitReviewPage({
  searchParams,
}: RuleUnitReviewPageProps): Promise<ReactElement> {
  const params = await searchParams;
  const status = normalizeStatus(params?.status);
  const decisionSummary = getRuleUnitReviewDecisionSummary();
  const statusSummary = getRuleUnitReviewStatusSummary();
  const applyProposal = getRuleUnitApplyProposalSummary();
  const items = getRuleUnitReviewQueue(40, status);

  return (
    <main className="app-product-page">
      <section className="app-hero compact">
        <p>Rule-Unit Review</p>
        <h2>Work the queue of rule units that need human or critic review.</h2>
        <span>
          Each item keeps the original source sentence, current extraction, quality issues, and
          allowed outcomes.
        </span>
      </section>

      <section className="profile-summary" aria-label="Review queue status">
        <div>
          <span>Untouched</span>
          <strong>{statusSummary.pending.toLocaleString("en-US")}</strong>
        </div>
        <div>
          <span>Decision-aware queue</span>
          <strong>{statusSummary.total.toLocaleString("en-US")}</strong>
        </div>
        <div>
          <span>Decisions logged</span>
          <strong>{decisionSummary.totalDecisions.toLocaleString("en-US")}</strong>
        </div>
      </section>

      <section className="review-filter-row" aria-label="Review queue filters">
        {reviewFilters(statusSummary).map((filter) => (
          <a
            className={filter.key === status ? "is-active" : ""}
            href={`/app/review?status=${filter.key}`}
            key={filter.key}
          >
            <span>{filter.label}</span>
            <strong>{filter.count.toLocaleString("en-US")}</strong>
          </a>
        ))}
      </section>

      <ReviewDecisionPanel
        initialApplyChanges={applyProposal?.changes ?? []}
        initialApplyReady={applyProposal?.readyToApply ?? false}
        initialDecisionsConsidered={applyProposal?.decisionsConsidered ?? 0}
        initialDecisionsLogged={decisionSummary.totalDecisions}
        initialProposedChanges={canonicalChanges(applyProposal?.changes ?? [])}
        initialValidationErrors={applyProposal?.validationErrors ?? []}
        items={items}
        status={status}
        totalMatchingItems={filterCount(statusSummary, status)}
      />
    </main>
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

function reviewFilters(summary: ReturnType<typeof getRuleUnitReviewStatusSummary>): Array<{
  count: number;
  key: RuleUnitReviewStatusFilter;
  label: string;
}> {
  return [
    { count: summary.pending, key: "pending", label: "Pending" },
    { count: summary.approved, key: "approved", label: "Approved" },
    { count: summary.revised, key: "revised", label: "Revised" },
    { count: summary.split, key: "split", label: "Split" },
    { count: summary.quarantined, key: "quarantined", label: "Quarantined" },
    { count: summary.changeReady, key: "change_ready", label: "Change ready" },
    { count: summary.total, key: "all", label: "All" },
  ];
}

function filterCount(
  summary: ReturnType<typeof getRuleUnitReviewStatusSummary>,
  status: RuleUnitReviewStatusFilter,
): number {
  if (status === "all") {
    return summary.total;
  }

  if (status === "change_ready") {
    return summary.changeReady;
  }

  return summary[status];
}

function canonicalChanges(changes: Array<{ action: string }>): number {
  return changes.filter((change) => change.action === "remove" || change.action === "replace")
    .length;
}
