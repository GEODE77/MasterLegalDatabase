import { Clock } from "lucide-react";
import { Panel } from "@/components/panel";
import { TimelineList } from "@/components/timeline-list";
import { getDashboardData } from "@/lib/data";

export default async function TimelinePage() {
  const { timelineEvents } = await getDashboardData();

  return (
    <div className="page">
      <header className="page-header">
        <div>
          <p className="eyebrow">Timeline</p>
          <h1>Chronology across indexed legal objects.</h1>
          <p className="lede">
            Legislative, rulemaking, and effective-date events remain tied to source records.
          </p>
        </div>
      </header>

      <Panel title="Master Timeline" icon={<Clock className="icon" aria-hidden="true" />}>
        <TimelineList events={timelineEvents} />
      </Panel>
    </div>
  );
}
