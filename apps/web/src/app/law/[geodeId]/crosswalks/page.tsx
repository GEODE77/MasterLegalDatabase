import { notFound } from "next/navigation";
import { GitBranch } from "lucide-react";
import { EntityHeader } from "@/components/entity-header";
import { Panel } from "@/components/panel";
import { RelationList } from "@/components/relation-list";
import { getEntity, getEntityRelations } from "@/lib/data";

type CrosswalkPageProps = {
  params: {
    geodeId: string;
  };
};

export default async function CrosswalkPage({ params }: CrosswalkPageProps) {
  const geodeId = decodeURIComponent(params.geodeId);
  const entity = await getEntity(geodeId);
  if (!entity) {
    notFound();
  }
  const relations = await getEntityRelations(entity.geodeId);

  return (
    <div className="page">
      <div className="stack">
        <EntityHeader entity={entity} />
        <Panel title="Crosswalk Relationship Graph" icon={<GitBranch className="icon" aria-hidden="true" />}>
          <RelationList relations={relations} />
        </Panel>
      </div>
    </div>
  );
}
