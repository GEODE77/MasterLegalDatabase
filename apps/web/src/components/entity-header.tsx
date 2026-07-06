import Link from "next/link";
import { BookmarkPlus, ExternalLink } from "lucide-react";
import { ConfidenceBadge, EntityTypeBadge, StatusBadge } from "@/components/badges";
import { dateLabel } from "@/lib/format";
import type { CorpusEntity } from "@/lib/types";

export function EntityHeader({ entity }: { entity: CorpusEntity }) {
  return (
    <section className="panel">
      <div className="entity-header">
        <div className="entity-title-row">
          <div>
            <p className="citation">{entity.citation}</p>
            <h1>{entity.title}</h1>
            <p className="lede">{entity.summary}</p>
          </div>
          <div className="button-row">
            <Link className="button" href={`/agencies/${entity.agencyCode}`}>
              Agency
            </Link>
            <Link className="button primary" href={`/law/${entity.geodeId}#follow`}>
              <BookmarkPlus className="icon" aria-hidden="true" />
              Follow
            </Link>
          </div>
        </div>

        <div className="badge-row">
          <EntityTypeBadge type={entity.entityType} />
          <StatusBadge status={entity.status} />
          <ConfidenceBadge value={entity.confidence} />
          <span className="badge">Effective {dateLabel(entity.effectiveDate)}</span>
          <Link className="badge" href={entity.sourceUrl}>
            <ExternalLink className="icon" aria-hidden="true" />
            Source
          </Link>
        </div>
      </div>
      <nav className="tabs" aria-label="Entity sections">
        <Link className="tab is-active" href={`/law/${entity.geodeId}`}>
          Text
        </Link>
        <Link className="tab" href={`/law/${entity.geodeId}#summary`}>
          Summary
        </Link>
        <Link className="tab" href={`/law/${entity.geodeId}/crosswalks`}>
          Crosswalks
        </Link>
        <Link className="tab" href={`/law/${entity.geodeId}/timeline`}>
          Timeline
        </Link>
        <Link className="tab" href={`/law/${entity.geodeId}#discussions`}>
          Discussions
        </Link>
        <Link className="tab" href={`/law/${entity.geodeId}#data`}>
          Data
        </Link>
      </nav>
    </section>
  );
}
