import { ArrowRight } from "lucide-react";
import type { EntityRelation } from "@/lib/types";

export function RelationList({ relations }: { relations: EntityRelation[] }) {
  if (!relations.length) {
    return <div className="empty-state">No crosswalk relationships are indexed for this object.</div>;
  }

  return (
    <div className="panel-body">
      {relations.map((relation) => (
        <div className="relation-strip" key={relation.id}>
          <div className="relation-node">
            <span className="badge">{relation.sourceType}</span>
            <strong>{relation.sourceGeodeId}</strong>
          </div>
          <div className="relation-arrow" aria-label={relation.relationship}>
            <ArrowRight aria-hidden="true" />
          </div>
          <div className="relation-node">
            <span className="badge primary">{relation.relationship}</span>
            <strong>{relation.targetGeodeId}</strong>
            <span className="row-meta">{relation.sourceEvidence}</span>
          </div>
        </div>
      ))}
    </div>
  );
}
