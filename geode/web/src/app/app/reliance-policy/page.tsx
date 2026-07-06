import type { ReactElement } from "react";

import { getReliancePolicy } from "@/lib/product/productIndex";

export const dynamic = "force-dynamic";

export default function ReliancePolicyPage(): ReactElement {
  const policy = getReliancePolicy();

  if (!policy) {
    return (
      <main className="app-product-page">
        <section className="app-hero compact">
          <p>Reliance Policy</p>
          <h2>No reliance policy is available.</h2>
          <span>Run the Step 5 policy builder before relying on review outputs.</span>
        </section>
      </main>
    );
  }

  return (
    <main className="app-product-page">
      <section className="app-hero compact">
        <p>Reliance Policy</p>
        <h2>Define when Geode outputs can support real-world decisions.</h2>
        <span>{policy.purpose}</span>
      </section>

      <section className="profile-summary" aria-label="Policy status">
        <div>
          <span>Policy</span>
          <strong>{policy.policyId}</strong>
        </div>
        <div>
          <span>Version</span>
          <strong>{policy.version}</strong>
        </div>
        <div>
          <span>Approval levels</span>
          <strong>{policy.approvalLevels.length.toLocaleString("en-US")}</strong>
        </div>
      </section>

      <section className="path-list" aria-label="Reviewer roles">
        {policy.reviewerRoles.map((role, index) => (
          <article key={role.roleId}>
            <span>{index + 1}</span>
            <div>
              <strong>{role.label}</strong>
              <p>{role.description}</p>
              <small>Log decisions: {role.mayLogDecisions ? "yes" : "no"}</small>
              <small>
                Apply canonical changes: {role.mayApplyCanonicalChanges ? "yes" : "no"}
              </small>
              <small>
                Approve external reliance: {role.mayApproveExternalReliance ? "yes" : "no"}
              </small>
            </div>
          </article>
        ))}
      </section>

      <section className="review-list" aria-label="Reliance boundaries">
        <header className="review-list-header">
          <div>
            <span>Boundaries</span>
            <strong>Output-specific reliance limits</strong>
          </div>
          <p>These limits travel with review outputs.</p>
        </header>
        {policy.relianceBoundaries.map((boundary) => (
          <article key={boundary.outputType}>
            <header>
              <span>{boundary.defaultLevel}</span>
              <strong>{boundary.outputType}</strong>
            </header>
            <p>{boundary.boundary}</p>
          </article>
        ))}
      </section>

      <section className="path-list" aria-label="Approval criteria">
        {policy.approvalCriteria.map((criterion, index) => (
          <article key={criterion.criterionId}>
            <span>{index + 1}</span>
            <div>
              <strong>{criterion.label}</strong>
              <p>{criterion.description}</p>
              <small>Required for {criterion.requiredFor}</small>
            </div>
          </article>
        ))}
      </section>
    </main>
  );
}
