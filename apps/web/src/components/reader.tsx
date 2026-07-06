import { SourceBackedBadge } from "@/components/badges";
import type { TextChunk } from "@/lib/types";

export function Reader({ chunks }: { chunks: TextChunk[] }) {
  if (!chunks.length) {
    return <div className="empty-state">No source text chunks are indexed for this object.</div>;
  }

  return (
    <div className="reader">
      <div className="compact-stack reader-badge-row">
        <SourceBackedBadge />
      </div>
      <article className="source-text">
        {chunks.map((chunk) => (
          <section className="passage-anchor" id={chunk.id} key={chunk.id}>
            <h2>{chunk.headingPath.at(-1) ?? chunk.citationScope}</h2>
            <p>{chunk.text}</p>
          </section>
        ))}
      </article>
    </div>
  );
}
