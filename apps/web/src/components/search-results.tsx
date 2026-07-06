import Link from "next/link";
import { ArrowRight, SearchCheck } from "lucide-react";
import { ConfidenceBadge, EntityTypeBadge, StatusBadge } from "@/components/badges";
import type { SearchResult } from "@/lib/types";

export function SearchResults({ results }: { results: SearchResult[] }) {
  if (!results.length) {
    return <div className="empty-state">No indexed legal objects matched this query.</div>;
  }

  return (
    <div className="panel-body">
      {results.map(({ entity, matchReason }) => (
        <article className="search-result" key={entity.geodeId}>
          <div className="search-result-title">
            <SearchCheck className="icon" aria-hidden="true" />
            <Link href={`/law/${entity.geodeId}`}>{entity.title}</Link>
          </div>
          <p className="lede">{entity.summary}</p>
          <div className="row-meta">
            <span className="citation">{entity.citation}</span>
            <span>{matchReason}</span>
            <span>{entity.layer}</span>
          </div>
          <div className="badge-row">
            <EntityTypeBadge type={entity.entityType} />
            <StatusBadge status={entity.status} />
            <ConfidenceBadge value={entity.confidence} />
            {entity.subjectTags.slice(0, 3).map((tag) => (
              <span className="badge" key={tag}>
                {tag}
              </span>
            ))}
            <Link className="badge primary" href={`/law/${entity.geodeId}`}>
              Open
              <ArrowRight className="icon" aria-hidden="true" />
            </Link>
          </div>
        </article>
      ))}
    </div>
  );
}
