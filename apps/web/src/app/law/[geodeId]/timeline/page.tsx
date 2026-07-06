import { notFound } from "next/navigation";
import { Clock } from "lucide-react";
import { EntityHeader } from "@/components/entity-header";
import { Panel } from "@/components/panel";
import { TimelineList } from "@/components/timeline-list";
import { getEntity, getEntityTimeline } from "@/lib/data";

type TimelinePageProps = {
  params: {
    geodeId: string;
  };
};

export default async function EntityTimelinePage({ params }: TimelinePageProps) {
  const geodeId = decodeURIComponent(params.geodeId);
  const entity = await getEntity(geodeId);
  if (!entity) {
    notFound();
  }
  const timeline = await getEntityTimeline(entity.geodeId);

  return (
    <div className="page">
      <div className="stack">
        <EntityHeader entity={entity} />
        <Panel title="Entity Timeline" icon={<Clock className="icon" aria-hidden="true" />}>
          <TimelineList events={timeline} />
        </Panel>
      </div>
    </div>
  );
}
