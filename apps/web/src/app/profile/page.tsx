import { UserRound } from "lucide-react";
import { Panel, PanelBody } from "@/components/panel";

const trustDimensions = [
  ["Citation accuracy", "Developing"],
  ["Explanation helpfulness", "Reviewed"],
  ["Data review", "Contributor"],
  ["Civic conduct", "Good standing"],
  ["Moderation judgment", "Not scoped"]
];

export default function ProfilePage() {
  return (
    <div className="page">
      <header className="page-header">
        <div>
          <p className="eyebrow">Profile</p>
          <h1>Contribution history without a single karma score.</h1>
          <p className="lede">
            Trust is shown by dimension, source quality, and reviewed contribution history.
          </p>
        </div>
      </header>

      <Panel title="Trust Dimensions" icon={<UserRound className="icon" aria-hidden="true" />}>
        <PanelBody>
          <div className="meta-grid">
            {trustDimensions.map(([dimension, level]) => (
              <div className="meta-row" key={dimension}>
                <strong>{dimension}</strong>
                <span>{level}</span>
              </div>
            ))}
          </div>
        </PanelBody>
      </Panel>
    </div>
  );
}
