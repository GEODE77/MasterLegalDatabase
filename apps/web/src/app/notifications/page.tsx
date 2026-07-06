import { Bell } from "lucide-react";
import { Panel } from "@/components/panel";

export default function NotificationsPage() {
  return (
    <div className="page">
      <header className="page-header">
        <div>
          <p className="eyebrow">Notifications</p>
          <h1>Watched legal changes and review updates.</h1>
          <p className="lede">
            Notifications are tied to followed entities, agencies, data issues, and review outcomes.
          </p>
        </div>
      </header>

      <Panel title="Recent Updates" icon={<Bell className="icon" aria-hidden="true" />}>
        <div className="row-list">
          <article className="row-item">
            <strong>Regulation Number 7 timeline updated</strong>
            <div className="row-meta">
              <span>5 CCR 1001-9</span>
              <span>Rulemaking event</span>
            </div>
          </article>
          <article className="row-item">
            <strong>Correction proposal moved to review</strong>
            <div className="row-meta">
              <span>RM-2024-00412</span>
              <span>Data issue</span>
            </div>
          </article>
        </div>
      </Panel>
    </div>
  );
}
