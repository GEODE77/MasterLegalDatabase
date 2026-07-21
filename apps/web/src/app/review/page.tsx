import { ShieldCheck } from "lucide-react";
import { Panel } from "@/components/panel";

const queue = [
  {
    type: "Correction proposal",
    title: "Effective date confirmation",
    anchor: "RM-2024-00412",
    priority: "Medium"
  },
  {
    type: "Unsupported claim",
    title: "Monitoring threshold answer requires citation",
    anchor: "5 CCR 1001-9",
    priority: "High"
  }
];

export default function ReviewPage() {
  return (
    <div className="page">
      <header className="page-header">
        <div>
          <p className="eyebrow">Review</p>
          <h1>Source and correction review queue.</h1>
          <p className="lede">
            Review actions preserve source evidence, anchor context, and auditable outcomes.
          </p>
        </div>
      </header>

      <Panel title="Reviewer Queue" icon={<ShieldCheck className="icon" aria-hidden="true" />}>
        <div className="row-list">
          {queue.map((item) => (
            <article className="row-item" key={item.title}>
              <strong>{item.title}</strong>
              <div className="row-meta">
                <span>{item.type}</span>
                <span>{item.anchor}</span>
              </div>
              <div className="badge-row">
                <span className={item.priority === "High" ? "badge rose" : "badge amber"}>
                  {item.priority}
                </span>
              </div>
            </article>
          ))}
        </div>
      </Panel>
    </div>
  );
}
