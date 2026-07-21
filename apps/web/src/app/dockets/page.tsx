import Link from "next/link";
import { FileSearch } from "lucide-react";
import { Panel } from "@/components/panel";
import { searchCorpus } from "@/lib/data";

export default async function DocketsPage() {
  const results = await searchCorpus("rulemaking");

  return (
    <div className="page">
      <header className="page-header">
        <div>
          <p className="eyebrow">Dockets</p>
          <h1>Rulemaking notices and active regulatory changes.</h1>
          <p className="lede">
            Docket views keep notices connected to affected rules, agencies, and timeline events.
          </p>
        </div>
      </header>

      <Panel title="Active Rulemaking Notices" icon={<FileSearch className="icon" aria-hidden="true" />}>
        <div className="row-list">
          {results.map(({ entity }) => (
            <article className="row-item" key={entity.geodeId}>
              <Link className="search-result-title" href={`/law/${entity.geodeId}`}>
                <span className="citation">{entity.citation}</span>
                <span>{entity.title}</span>
              </Link>
              <p className="lede">{entity.summary}</p>
              <div className="badge-row">
                <span className="badge amber">{entity.status}</span>
                <span className="badge primary">{entity.agencyCode}</span>
              </div>
            </article>
          ))}
        </div>
      </Panel>
    </div>
  );
}
