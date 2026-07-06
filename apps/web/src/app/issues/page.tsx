import { ShieldAlert } from "lucide-react";
import { Panel } from "@/components/panel";

const issues = [
  {
    title: "Confirm effective date in Register notice crosswalk",
    target: "RM-2024-00412",
    state: "Review",
    evidence: "Register citation attached"
  },
  {
    title: "Check enabling statute reference for Regulation 7",
    target: "5_CCR_1001-9",
    state: "Open",
    evidence: "Source excerpt requested"
  }
];

export default function IssuesPage() {
  return (
    <div className="page">
      <header className="page-header">
        <div>
          <p className="eyebrow">Data Issues</p>
          <h1>Reviewable issues that do not mutate the corpus directly.</h1>
          <p className="lede">
            Data issues are app-layer records until reviewed through a controlled correction workflow.
          </p>
        </div>
      </header>

      <Panel title="Issue Queue" icon={<ShieldAlert className="icon" aria-hidden="true" />}>
        <div className="row-list">
          {issues.map((issue) => (
            <article className="row-item" key={issue.title}>
              <strong>{issue.title}</strong>
              <div className="row-meta">
                <span>{issue.target}</span>
                <span>{issue.evidence}</span>
              </div>
              <div className="badge-row">
                <span className={issue.state === "Review" ? "badge amber" : "badge primary"}>
                  {issue.state}
                </span>
              </div>
            </article>
          ))}
        </div>
      </Panel>
    </div>
  );
}
