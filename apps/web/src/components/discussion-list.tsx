import { MessageSquareText } from "lucide-react";
import { ReviewBadge } from "@/components/badges";
import type { DiscussionPreview } from "@/lib/types";

export function DiscussionList({ discussions }: { discussions: DiscussionPreview[] }) {
  return (
    <div className="row-list">
      {discussions.map((discussion) => (
        <article className="row-item" key={discussion.id}>
          <div className="search-result-title">
            <MessageSquareText className="icon" aria-hidden="true" />
            <span>{discussion.title}</span>
          </div>
          <div className="row-meta">
            <span>{discussion.type}</span>
            <span>{discussion.anchor}</span>
            <span>{discussion.status}</span>
          </div>
          <div className="badge-row">
            <ReviewBadge label={discussion.sourceState} />
          </div>
        </article>
      ))}
    </div>
  );
}
