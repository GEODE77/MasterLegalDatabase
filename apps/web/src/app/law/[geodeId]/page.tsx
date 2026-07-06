import { notFound } from "next/navigation";
import { BookOpen, Database, GitBranch, MessageSquareText, ShieldCheck } from "lucide-react";
import { AiAssistBadge, MetadataBadge } from "@/components/badges";
import { DiscussionList } from "@/components/discussion-list";
import { EntityHeader } from "@/components/entity-header";
import { Panel, PanelBody } from "@/components/panel";
import { Reader } from "@/components/reader";
import { RelationList } from "@/components/relation-list";
import { TimelineList } from "@/components/timeline-list";
import {
  getDiscussionsForEntity,
  getEntity,
  getEntityChunks,
  getEntityRelations,
  getEntityTimeline
} from "@/lib/data";

type EntityPageProps = {
  params: {
    geodeId: string;
  };
};

export default async function EntityPage({ params }: EntityPageProps) {
  const geodeId = decodeURIComponent(params.geodeId);
  const entity = await getEntity(geodeId);
  if (!entity) {
    notFound();
  }

  const [chunks, relations, timeline, discussions] = await Promise.all([
    getEntityChunks(entity.geodeId),
    getEntityRelations(entity.geodeId),
    getEntityTimeline(entity.geodeId),
    getDiscussionsForEntity(entity.geodeId)
  ]);

  return (
    <div className="page">
      <div className="stack">
        <EntityHeader entity={entity} />

        <div className="content-grid">
          <aside className="stack">
            <Panel title="Document Outline" icon={<BookOpen className="icon" aria-hidden="true" />}>
              <div className="row-list">
                {chunks.map((chunk) => (
                  <a className="row-item" href={`#${chunk.id}`} key={chunk.id}>
                    <span className="citation">{chunk.citationScope}</span>
                    <strong>{chunk.headingPath.at(-1) ?? "Indexed passage"}</strong>
                  </a>
                ))}
              </div>
            </Panel>

            <Panel title="Metadata" icon={<Database className="icon" aria-hidden="true" />}>
              <PanelBody>
                <div className="compact-stack">
                  <MetadataBadge />
                  <div className="meta-grid">
                    <div className="meta-row">
                      <strong>Layer</strong>
                      <span>{entity.layer}</span>
                    </div>
                    <div className="meta-row">
                      <strong>Agency</strong>
                      <span>{entity.agencyCode}</span>
                    </div>
                    <div className="meta-row">
                      <strong>Subjects</strong>
                      <span>{entity.subjectTags.join(", ")}</span>
                    </div>
                    <div className="meta-row">
                      <strong>Industries</strong>
                      <span>{entity.industryTags.join(", ")}</span>
                    </div>
                  </div>
                </div>
              </PanelBody>
            </Panel>
          </aside>

          <main className="stack">
            <Panel title="Official Text" icon={<BookOpen className="icon" aria-hidden="true" />}>
              <Reader chunks={chunks} />
            </Panel>

            <Panel title="Source-Bounded Summary" icon={<ShieldCheck className="icon" aria-hidden="true" />}>
              <PanelBody>
                <div className="compact-stack">
                  <AiAssistBadge />
                  <p className="lede">{entity.summary}</p>
                </div>
              </PanelBody>
            </Panel>

            <Panel title="Crosswalks" icon={<GitBranch className="icon" aria-hidden="true" />}>
              <RelationList relations={relations} />
            </Panel>

            <Panel title="Timeline" icon={<GitBranch className="icon" aria-hidden="true" />}>
              <TimelineList events={timeline} />
            </Panel>
          </main>

          <aside className="stack" id="discussions">
            <Panel
              title="Entity Discussions"
              icon={<MessageSquareText className="icon" aria-hidden="true" />}
            >
              <DiscussionList discussions={discussions} />
            </Panel>

            <Panel title="Structured Actions" icon={<ShieldCheck className="icon" aria-hidden="true" />}>
              <div className="row-list">
                {["Ask a question", "Explain this", "Flag a data issue", "Report overlap"].map((item) => (
                  <div className="row-item" key={item}>
                    <strong>{item}</strong>
                    <div className="row-meta">
                      <span>{entity.citation}</span>
                      <span>Entity anchored</span>
                    </div>
                  </div>
                ))}
              </div>
            </Panel>
          </aside>
        </div>
      </div>
    </div>
  );
}
