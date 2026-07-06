"use client";

import Link from "next/link";
import { type FormEvent, type ReactElement, useMemo, useState } from "react";

import type {
  RuleUnitApplyProposalSummary,
  RuleUnitReviewItem,
  RuleUnitReviewStatusFilter,
} from "@/lib/product/productIndex";

type ReviewDecisionPanelProps = {
  initialApplyChanges: RuleUnitApplyProposalSummary["changes"];
  initialApplyReady: boolean;
  initialDecisionsConsidered: number;
  initialDecisionsLogged: number;
  initialProposedChanges: number;
  initialValidationErrors: string[];
  items: RuleUnitReviewItem[];
  status: RuleUnitReviewStatusFilter;
  totalMatchingItems: number;
};

type SaveState = {
  kind: "idle" | "saving" | "saved" | "error";
  message: string;
};

const OUTCOME_LABELS: Record<string, string> = {
  approve: "Approve",
  quarantine: "Quarantine",
  revise: "Revise",
  split: "Split",
};

const APPLY_CONFIRMATION = "APPLY_RULE_UNIT_DECISIONS";

export default function ReviewDecisionPanel({
  initialApplyChanges,
  initialApplyReady,
  initialDecisionsConsidered,
  initialDecisionsLogged,
  initialProposedChanges,
  initialValidationErrors,
  items,
  status,
  totalMatchingItems,
}: ReviewDecisionPanelProps): ReactElement {
  const [applyChanges, setApplyChanges] = useState(initialApplyChanges);
  const [applyReady, setApplyReady] = useState(initialApplyReady);
  const [applyStatus, setApplyStatus] = useState<SaveState>({ kind: "idle", message: "" });
  const [applyValidationErrors, setApplyValidationErrors] = useState(initialValidationErrors);
  const [confirmation, setConfirmation] = useState("");
  const [decisionsLogged, setDecisionsLogged] = useState(initialDecisionsLogged);
  const [decisionsConsidered, setDecisionsConsidered] = useState(initialDecisionsConsidered);
  const [proposedChanges, setProposedChanges] = useState(initialProposedChanges);
  const [outcomes, setOutcomes] = useState<Record<string, string>>(() =>
    Object.fromEntries(items.map((item) => [item.reviewId, initialOutcome(item)])),
  );
  const [states, setStates] = useState<Record<string, SaveState>>({});

  const savedReviewIds = useMemo(
    () =>
      new Set(
        Object.entries(states)
          .filter(([, state]) => state.kind === "saved")
          .map(([reviewId]) => reviewId),
      ),
    [states],
  );
  const canonicalChangeCount = applyChanges.filter((change) =>
    change.action === "remove" || change.action === "replace"
  ).length;
  const canApply =
    applyReady && canonicalChangeCount > 0 && confirmation.trim() === APPLY_CONFIRMATION;

  async function saveDecision(item: RuleUnitReviewItem, event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const formData = new FormData(form);
    const outcome = String(formData.get("outcome") ?? "");
    const rationale = String(formData.get("rationale") ?? "").trim();
    const replacementText = String(formData.get("proposedRuleUnits") ?? "").trim();

    setStates((current) => ({
      ...current,
      [item.reviewId]: { kind: "saving", message: "Saving decision" },
    }));

    try {
      const proposedRuleUnits = parseProposedRuleUnits(outcome, replacementText);
      const response = await fetch("/api/product/rule-units/review/decisions", {
        body: JSON.stringify({
          outcome,
          proposedRuleUnits,
          rationale,
          reviewId: item.reviewId,
        }),
        headers: { "Content-Type": "application/json" },
        method: "POST",
      });
      const payload = (await response.json()) as {
        error?: string;
        summary?: { totalDecisions?: number };
      };

      if (!response.ok) {
        throw new Error(payload.error ?? "Decision was not saved.");
      }

      setDecisionsLogged(payload.summary?.totalDecisions ?? decisionsLogged + 1);
      await rebuildApplyProposal();
      setStates((current) => ({
        ...current,
        [item.reviewId]: { kind: "saved", message: `${OUTCOME_LABELS[outcome]} saved` },
      }));
    } catch (error) {
      setStates((current) => ({
        ...current,
        [item.reviewId]: {
          kind: "error",
          message: error instanceof Error ? error.message : "Decision was not saved.",
        },
      }));
    }
  }

  async function rebuildApplyProposal() {
    const response = await fetch("/api/product/rule-units/review/apply-proposal", {
      body: JSON.stringify({ action: "rebuild" }),
      headers: { "Content-Type": "application/json" },
      method: "POST",
    });
    const payload = (await response.json()) as {
      proposal?: {
        changes?: RuleUnitApplyProposalSummary["changes"];
        decisionsConsidered?: number;
        readyToApply?: boolean;
        validationErrors?: string[];
      };
    };

    if (response.ok) {
      setApplyChanges(payload.proposal?.changes ?? applyChanges);
      setApplyReady(payload.proposal?.readyToApply ?? applyReady);
      setApplyValidationErrors(payload.proposal?.validationErrors ?? applyValidationErrors);
      setDecisionsConsidered(payload.proposal?.decisionsConsidered ?? decisionsConsidered);
      setProposedChanges(canonicalChanges(payload.proposal?.changes ?? applyChanges));
    }
  }

  async function applyDecisions(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (canonicalChangeCount === 0) {
      setApplyStatus({
        kind: "error",
        message: "There are no canonical changes to apply yet.",
      });
      return;
    }

    setApplyStatus({ kind: "saving", message: "Applying confirmed decisions" });

    try {
      const response = await fetch("/api/product/rule-units/review/apply-proposal", {
        body: JSON.stringify({ confirmation }),
        headers: { "Content-Type": "application/json" },
        method: "POST",
      });
      const payload = (await response.json()) as {
        error?: string;
        result?: {
          applied?: boolean;
          changes_applied?: number;
          decisions_applied?: number;
          message?: string;
          snapshot_expected?: boolean;
        };
        stderr?: string;
      };

      if (!response.ok) {
        throw new Error(payload.error ?? payload.stderr ?? "Apply command was not completed.");
      }

      const result = payload.result;
      const changesApplied = result?.changes_applied ?? 0;
      const decisionsApplied = result?.decisions_applied ?? 0;
      const snapshotText = result?.snapshot_expected ? "Snapshot protection was active." : "";
      setApplyStatus({
        kind: result?.applied ? "saved" : "idle",
        message:
          result?.message ??
          [
            `Applied ${changesApplied} canonical changes`,
            `from ${decisionsApplied} decisions.`,
            snapshotText,
          ].join(" "),
      });
    } catch (error) {
      setApplyStatus({
        kind: "error",
        message: error instanceof Error ? error.message : "Apply command was not completed.",
      });
    }
  }

  return (
    <>
      <section className="profile-summary" aria-label="Live review decision status">
        <div>
          <span>Decisions logged</span>
          <strong>{decisionsLogged.toLocaleString("en-US")}</strong>
        </div>
        <div>
          <span>Apply decisions</span>
          <strong>{decisionsConsidered.toLocaleString("en-US")}</strong>
        </div>
        <div>
          <span>Proposed changes</span>
          <strong>{proposedChanges.toLocaleString("en-US")}</strong>
        </div>
      </section>

      <section className="review-apply-panel" aria-label="Apply confirmed review decisions">
        <header>
          <div>
            <span>Final Apply</span>
            <h3>Apply confirmed canonical changes.</h3>
          </div>
          <strong>{applyReady ? "Ready" : "Blocked"}</strong>
        </header>
        <dl>
          <div>
            <dt>Canonical changes</dt>
            <dd>{canonicalChangeCount.toLocaleString("en-US")}</dd>
          </div>
          <div>
            <dt>Validation errors</dt>
            <dd>{applyValidationErrors.length.toLocaleString("en-US")}</dd>
          </div>
          <div>
            <dt>Confirmation</dt>
            <dd>{APPLY_CONFIRMATION}</dd>
          </div>
        </dl>
        {applyChanges.length > 0 ? (
          <ul>
            {applyChanges.slice(0, 6).map((change) => (
              <li key={`${change.decisionId}-${change.ruleUnitId}`}>
                <strong>{change.action}</strong>
                <span>{change.ruleUnitId}</span>
              </li>
            ))}
          </ul>
        ) : (
          <p>No proposed canonical changes are waiting to apply.</p>
        )}
        {applyValidationErrors.length > 0 ? (
          <p>{applyValidationErrors.slice(0, 3).join(" ")}</p>
        ) : null}
        <form className="review-apply-form" onSubmit={applyDecisions}>
          <label>
            <span>Type confirmation phrase</span>
            <input
              name="confirmation"
              onChange={(event) => setConfirmation(event.target.value)}
              value={confirmation}
            />
          </label>
          <div className="review-submit-row">
            <button disabled={!canApply || applyStatus.kind === "saving"} type="submit">
              Apply Confirmed Changes
            </button>
            {applyStatus.message ? (
              <span className={`review-save-status ${applyStatus.kind}`}>
                {applyStatus.message}
              </span>
            ) : null}
          </div>
        </form>
      </section>

      <section className="review-list" aria-label="Needs-review rule units">
        <header className="review-list-header">
          <div>
            <span>Current filter</span>
            <strong>{statusLabel(status)}</strong>
          </div>
          <p>
            Showing {items.length.toLocaleString("en-US")} of{" "}
            {totalMatchingItems.toLocaleString("en-US")} matching queue items.
          </p>
        </header>
        {items.map((item) => {
          const selectedOutcome = outcomes[item.reviewId] ?? initialOutcome(item);
          const needsReplacement = selectedOutcome === "revise" || selectedOutcome === "split";
          const state = states[item.reviewId] ?? { kind: "idle", message: "" };
          const isPreviouslyDecided = item.loggedDecision !== null;
          const isLocked = savedReviewIds.has(item.reviewId) || isPreviouslyDecided || state.kind === "saving";

          return (
            <article key={item.reviewId}>
              <header>
                <span>{item.priority} priority</span>
                <strong>{item.ruleUnitId}</strong>
                <Link href={`/app/explore?id=${encodeURIComponent(item.parentRegulationId)}`}>
                  Source
                </Link>
              </header>
              <div className="review-actions" aria-label="Review state">
                <span>{statusLabel(item.reviewStatus)}</span>
                {item.canonicalChangeReady ? <span>Canonical change ready</span> : null}
                {item.loggedDecision ? (
                  <span>{`Decision ${item.loggedDecision.decisionId}`}</span>
                ) : null}
              </div>
              <p>{item.reviewReason}</p>
              <blockquote>{item.sourceSentence}</blockquote>
              <div className="review-actions" aria-label="Suggested outcomes">
                {item.suggestedOutcomes.map((outcome) => (
                  <span key={`${item.reviewId}-${outcome}`}>
                    {OUTCOME_LABELS[outcome] ?? outcome}
                  </span>
                ))}
              </div>
              <dl>
                <div>
                  <dt>Entity</dt>
                  <dd>{item.currentRuleUnit.regulatedEntity ?? "Not captured"}</dd>
                </div>
                <div>
                  <dt>Section</dt>
                  <dd>{item.sourceSection}</dd>
                </div>
                <div>
                  <dt>Quality</dt>
                  <dd>{Math.round((item.quality.overall ?? 0) * 100)}%</dd>
                </div>
              </dl>
              {item.sourceContext ? <small>{item.sourceContext}</small> : null}
              <form
                className="review-decision-form"
                onSubmit={(event) => saveDecision(item, event)}
              >
                <label>
                  <span>Outcome</span>
                  <select
                    disabled={isLocked}
                    name="outcome"
                    onChange={(event) =>
                      setOutcomes((current) => ({
                        ...current,
                        [item.reviewId]: event.target.value,
                      }))
                    }
                    value={selectedOutcome}
                  >
                    {item.allowedOutcomes.map((outcome) => (
                      <option key={`${item.reviewId}-${outcome}-option`} value={outcome}>
                        {OUTCOME_LABELS[outcome] ?? outcome}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  <span>Rationale</span>
                  <textarea
                    disabled={isLocked}
                    name="rationale"
                    required
                    rows={3}
                    placeholder="Brief reason for this decision"
                  />
                </label>
                {needsReplacement ? (
                  <label className="review-replacement-field">
                    <span>Replacement records</span>
                    <textarea
                      defaultValue={JSON.stringify(
                        [toReplacementTemplate(item.currentRuleUnit)],
                        null,
                        2,
                      )}
                      disabled={isLocked}
                      name="proposedRuleUnits"
                      required
                      rows={8}
                    />
                  </label>
                ) : null}
                <div className="review-submit-row">
                  <button disabled={isLocked} type="submit">
                    {isPreviouslyDecided ? "Decision Logged" : "Save Decision"}
                  </button>
                  {state.message ? (
                    <span className={`review-save-status ${state.kind}`}>{state.message}</span>
                  ) : null}
                </div>
              </form>
            </article>
          );
        })}
      </section>
    </>
  );
}

function initialOutcome(item: RuleUnitReviewItem): string {
  const suggestedOutcome = item.suggestedOutcomes.find((outcome) =>
    item.allowedOutcomes.includes(outcome),
  );
  return suggestedOutcome ?? item.allowedOutcomes[0] ?? "approve";
}

function statusLabel(status: RuleUnitReviewStatusFilter): string {
  if (status === "all") {
    return "All";
  }

  if (status === "change_ready") {
    return "Canonical change ready";
  }

  const outcomeKey =
    status === "approved"
      ? "approve"
      : status === "quarantined"
        ? "quarantine"
        : status === "revised"
          ? "revise"
          : status;

  return OUTCOME_LABELS[outcomeKey] ?? status;
}

function canonicalChanges(changes: RuleUnitApplyProposalSummary["changes"]): number {
  return changes.filter((change) => change.action === "remove" || change.action === "replace")
    .length;
}

function parseProposedRuleUnits(outcome: string, replacementText: string): unknown[] {
  if (outcome !== "revise" && outcome !== "split") {
    return [];
  }

  if (!replacementText) {
    throw new Error("Replacement records are required for this outcome.");
  }

  const parsed = JSON.parse(replacementText) as unknown;
  return Array.isArray(parsed) ? parsed : [parsed];
}

function toReplacementTemplate(ruleUnit: Record<string, unknown>): Record<string, unknown> {
  return {
    action_required: ruleUnit.action_required,
    conditions: ruleUnit.conditions,
    confidence: ruleUnit.confidence,
    enabling_statute: ruleUnit.enabling_statute,
    entity_type: ruleUnit.entity_type,
    exceptions: ruleUnit.exceptions,
    id: ruleUnit.id,
    parent_regulation_id: ruleUnit.parent_regulation_id,
    penalties: ruleUnit.penalties,
    plain_english_summary: ruleUnit.plain_english_summary,
    regulated_entity: ruleUnit.regulated_entity,
    rule_type: ruleUnit.rule_type,
    source_section: ruleUnit.source_section,
    subject_tags: ruleUnit.subject_tags,
    temporal: ruleUnit.temporal,
  };
}
