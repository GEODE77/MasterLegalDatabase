import Link from "next/link";
import { notFound } from "next/navigation";
import { Landmark, MessageSquareText, ShieldCheck } from "lucide-react";
import { DiscussionList } from "@/components/discussion-list";
import { Panel, PanelBody } from "@/components/panel";
import { getDashboardData } from "@/lib/data";

const communityDetails = {
  "air-quality": {
    name: "Air Quality",
    scope: "Colorado air quality statutes, regulations, notices, and source-backed issues.",
    policy: "Legal claims need a citation or passage anchor."
  },
  manufacturing: {
    name: "Manufacturing",
    scope: "Operational compliance questions and source-backed impact reports.",
    policy: "Impact stories remain clearly labeled and separate from official law."
  }
};

type CommunityPageProps = {
  params: {
    slug: keyof typeof communityDetails;
  };
};

export default async function CommunityPage({ params }: CommunityPageProps) {
  const detail = communityDetails[params.slug];
  if (!detail) {
    notFound();
  }
  const { entities, discussions } = await getDashboardData();

  return (
    <div className="page">
      <header className="page-header">
        <div>
          <p className="eyebrow">Community</p>
          <h1>{detail.name}</h1>
          <p className="lede">{detail.scope}</p>
        </div>
      </header>

      <div className="two-column">
        <main className="stack">
          <Panel title="Relevant Legal Objects" icon={<Landmark className="icon" aria-hidden="true" />}>
            <div className="row-list">
              {entities.map((entity) => (
                <article className="row-item" key={entity.geodeId}>
                  <Link className="search-result-title" href={`/law/${entity.geodeId}`}>
                    <span className="citation">{entity.citation}</span>
                    <span>{entity.title}</span>
                  </Link>
                  <p className="lede">{entity.summary}</p>
                </article>
              ))}
            </div>
          </Panel>
        </main>

        <aside className="stack">
          <Panel title="Posting Policy" icon={<ShieldCheck className="icon" aria-hidden="true" />}>
            <PanelBody>
              <p className="lede">{detail.policy}</p>
            </PanelBody>
          </Panel>

          <Panel title="Active Threads" icon={<MessageSquareText className="icon" aria-hidden="true" />}>
            <DiscussionList discussions={discussions} />
          </Panel>
        </aside>
      </div>
    </div>
  );
}
