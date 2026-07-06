import { CalendarDays } from "lucide-react";
import { dateLabel } from "@/lib/format";
import type { TimelineEvent } from "@/lib/types";

export function TimelineList({ events }: { events: TimelineEvent[] }) {
  if (!events.length) {
    return <div className="empty-state">No timeline events are indexed for this object.</div>;
  }

  return (
    <div className="panel-body timeline-list">
      {events.map((event) => (
        <article className="timeline-event" key={event.id}>
          <div className="timeline-date">
            <CalendarDays className="icon" aria-hidden="true" />
            {dateLabel(event.date)}
          </div>
          <div>
            <h3>{event.label}</h3>
            <div className="row-meta">
              <span>{event.eventType}</span>
              <span>{event.sourceReference}</span>
            </div>
          </div>
        </article>
      ))}
    </div>
  );
}
