import Link from "next/link";
import { notFound } from "next/navigation";
import { Building2, ExternalLink, FileSearch, GitBranch, ShieldCheck } from "lucide-react";
import { ConfidenceBadge, EntityTypeBadge, StatusBadge } from "@/components/badges";
import { Panel, PanelBody } from "@/components/panel";
import { getAgency, getAgencyEntities } from "@/lib/data";

type AgencyPageProps = {
  params: {
    agencyCode: string;
  };
};

export default async function AgencyPage({ params }: AgencyPageProps) {
  const agencyCode = decodeURIComponent(params.agencyCode);
  const agency = await getAgency(agencyCode);
  if (!agency) {
    notFound();
  }
  const agencyEntities = await getAgencyEntities(agency.code);

  return (
    <div className="page">
      <header className="page-header">
        <div>
          <p className="eyebrow">Agency</p>
          <h1>{agency.name}</h1>
          <p className="lede">{agency.description}</p>
        </div>
        <div className="button-row">
          <Link className="button" href={agency.sourceUrl}>
            <ExternalLink className="icon" aria-hidden="true" />
            Source
          </Link>
          <Link className="button primary" href="/search?q=air+quality">
            <FileSearch className="icon" aria-hidden="true" />
            Search objects
          </Link>
        </div>
      </header>

      <div className="two-column">
        <main className="stack">
          <Panel title="Agency Legal Objects" icon={<Building2 className="icon" aria-hidden="true" />}>
            <div className="row-list">
              {agencyEntities.map((entity) => (
                <article className="row-item" key={entity.geodeId}>
                  <Link className="search-result-title" href={`/law/${entity.geodeId}`}>
                    <span className="citation">{entity.citation}</span>
                    <span>{entity.title}</span>
                  </Link>
                  <p className="lede">{entity.summary}</p>
                  <div className="badge-row">
                    <EntityTypeBadge type={entity.entityType} />
                    <StatusBadge status={entity.status} />
                    <ConfidenceBadge value={entity.confidence} />
                  </div>
                </article>
              ))}
            </div>
          </Panel>
        </main>

        <aside className="stack">
          <Panel title="Operational Snapshot" icon={<ShieldCheck className="icon" aria-hidden="true" />}>
            <PanelBody>
              <div className="meta-grid">
                <div className="meta-row">
                  <strong>Code</strong>
                  <span>{agency.code}</span>
                </div>
                <div className="meta-row">
                  <strong>Jurisdiction</strong>
                  <span>{agency.jurisdiction}</span>
                </div>
                <div className="meta-row">
                  <strong>Objects</strong>
                  <span>{agency.entityCount}</span>
                </div>
                <div className="meta-row">
                  <strong>Open issues</strong>
                  <span>{agency.openIssues}</span>
                </div>
              </div>
            </PanelBody>
          </Panel>

          <Panel title="Rulemaking Activity" icon={<GitBranch className="icon" aria-hidden="true" />}>
            <div className="row-list">
              <article className="row-item">
                <strong>Regulation Number 7 revision window</strong>
                <div className="row-meta">
                  <span>{agency.activeRulemakings} active rulemakings</span>
                  <span>Register linked</span>
                </div>
                <div className="badge-row">
                  <span className="badge amber">Review deadline</span>
                </div>
              </article>
            </div>
          </Panel>
        </aside>
      </div>
    </div>
  );
}
