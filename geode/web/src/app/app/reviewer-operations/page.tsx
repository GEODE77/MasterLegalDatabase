import Link from "next/link";
import type { ReactElement } from "react";

import { getReviewerOperations } from "@/lib/product/productIndex";

export const dynamic = "force-dynamic";

export default function ReviewerOperationsPage(): ReactElement {
  const operations = getReviewerOperations();

  if (!operations) {
    return (
      <main className="app-product-page">
        <section className="app-hero compact">
          <p>Reviewer Operations</p>
          <h2>No reviewer operations registry is available.</h2>
          <span>Run the Step 6 reviewer operations builder before assigning review work.</span>
        </section>
      </main>
    );
  }

  return (
    <main className="app-product-page">
      <section className="app-hero compact">
        <p>Reviewer Operations</p>
        <h2>Prepare reviewer slots and operating instructions.</h2>
        <span>{operations.boundary}</span>
      </section>

      <section className="profile-summary" aria-label="Reviewer assignment status">
        <div>
          <span>Required roles</span>
          <strong>{operations.requiredRoles.toLocaleString("en-US")}</strong>
        </div>
        <div>
          <span>Unassigned</span>
          <strong>{operations.unassignedRoles.toLocaleString("en-US")}</strong>
        </div>
        <div>
          <span>SOP</span>
          <strong>{operations.sopPath ? "Ready" : "Missing"}</strong>
        </div>
      </section>

      <section className="path-list" aria-label="Reviewer assignment slots">
        {operations.assignments.map((assignment, index) => (
          <article key={assignment.roleId}>
            <span>{index + 1}</span>
            <div>
              <strong>{assignment.label}</strong>
              <p>{assignment.name ?? assignment.assignedTo ?? "No reviewer has been assigned to this role yet."}</p>
              <small>Status: {assignment.assignmentStatus}</small>
              <small>Email: {assignment.email ?? "unassigned"}</small>
              <small>Effective: {assignment.effectiveDate ?? "not authorized"}</small>
              <small>Revoked: {assignment.revocationDate ?? "not revoked"}</small>
              <small>Policy: {assignment.reliancePolicyBackReference}</small>
              <small>Log decisions: {assignment.canLogDecisions ? "yes" : "no"}</small>
              <small>
                Apply canonical changes: {assignment.canApplyCanonicalChanges ? "yes" : "no"}
              </small>
              <small>
                Approve external reliance: {assignment.canApproveExternalReliance ? "yes" : "no"}
              </small>
            </div>
          </article>
        ))}
      </section>

      <section className="review-list" aria-label="Reviewer operations SOP">
        <header className="review-list-header">
          <div>
            <span>Operating instructions</span>
            <strong>Reviewer SOP</strong>
          </div>
          <p>{operations.sopPath ?? "SOP path unavailable"}</p>
        </header>
        <article>
          <header>
            <span>Next action</span>
            <strong>Assign named reviewers</strong>
            <Link href="/app/reliance-policy">Policy</Link>
          </header>
          <p>
            The system has prepared the roles and instructions. A project owner still needs to
            name the people who will serve in each role.
          </p>
        </article>
      </section>
    </main>
  );
}
