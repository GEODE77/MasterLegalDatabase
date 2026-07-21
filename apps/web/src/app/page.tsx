import Link from "next/link";
import {
  AlertCircle,
  ArrowRight,
  Building2,
  CheckCircle2,
  Clock,
  FileSearch,
  GitBranch,
  Search,
  ShieldCheck
} from "lucide-react";
import { ConfidenceBadge, EntityTypeBadge, StatusBadge } from "@/components/badges";
import { DiscussionList } from "@/components/discussion-list";
import { Panel, PanelBody } from "@/components/panel";
import { TimelineList } from "@/components/timeline-list";
import { getDashboardData } from "@/lib/data";

export default async function DashboardPage() {
  const { entities, timelineEvents, discussions, agencies } = await getDashboardData();
  const primaryEntity = entities[0];

  return (
    <div className="page">
      <header className="page-header">
        <div>
          <p className="eyebrow">Geode Commons</p>
          <h1>Source-backed legal research centered on Colorado law.</h1>
          <p className="lede">
            Browse indexed legal objects, inspect source relationships, and track review work
            without mixing canonical law with commentary.
          </p>
        </div>
        <div className="button-row">
          <Link className="button" href="/search">
            <Search className="icon" aria-hidden="true" />
            Search
          </Link>
          <Link className="button primary" href={`/law/${primaryEntity.geodeId}`}>
            <FileSearch className="icon" aria-hidden="true" />
            Open entity
          </Link>
        </div>
      </header>

      <div className="dashboard-grid">
        <div className="stack">
          <section className="panel hero-search">
            <form action="/search">
              <input
                className="search-large"
                name="q"
                placeholder="CRS 25-7-109, air permit, AQCC, Regulation 7"
                type="search"
              />
              <button className="button primary" type="submit">
                <Search className="icon" aria-hidden="true" />
                Search corpus
              </button>
            </form>
            <div className="stat-strip">
              <div className="stat">
                <strong>{entities.length}</strong>
                <span>Indexed objects</span>
              </div>
              <div className="stat">
                <strong>{timelineEvents.length}</strong>
                <span>Timeline events</span>
              </div>
              <div className="stat">
                <strong>{agencies.length}</strong>
                <span>Agencies</span>
              </div>
              <div className="stat">
                <strong>3</strong>
                <span>Review items</span>
              </div>
            </div>
          </section>

          <Panel
            title="Recent Legal Changes"
            icon={<Clock className="icon" aria-hidden="true" />}
            action={
              <Link className="badge primary" href="/timeline">
                Timeline
                <ArrowRight className="icon" aria-hidden="true" />
              </Link>
            }
          >
            <TimelineList events={timelineEvents.slice(0, 3)} />
          </Panel>

          <Panel title="Followed Legal Objects" icon={<FileSearch className="icon" aria-hidden="true" />}>
            <div className="row-list">
              {entities.map((entity) => (
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
        </div>

        <aside className="stack">
          <Panel title="Review Needed" icon={<ShieldCheck className="icon" aria-hidden="true" />}>
            <div className="row-list">
              <article className="row-item">
                <div className="search-result-title">
                  <AlertCircle className="icon" aria-hidden="true" />
                  <span>Effective date crosswalk</span>
                </div>
                <div className="row-meta">
                  <span>Data Issue</span>
                  <span>RM-2024-00412</span>
                </div>
                <div className="badge-row">
                  <span className="badge amber">Evidence attached</span>
                </div>
              </article>
              <article className="row-item">
                <div className="search-result-title">
                  <CheckCircle2 className="icon" aria-hidden="true" />
                  <span>Source-backed explanation</span>
                </div>
                <div className="row-meta">
                  <span>Explanation</span>
                  <span>CRS 25-7-109</span>
                </div>
                <div className="badge-row">
                  <span className="badge green">Reviewed</span>
                </div>
              </article>
            </div>
          </Panel>

          <Panel title="Active Questions" icon={<GitBranch className="icon" aria-hidden="true" />}>
            <DiscussionList discussions={discussions} />
          </Panel>

          <Panel title="Agency Context" icon={<Building2 className="icon" aria-hidden="true" />}>
            <div className="row-list">
              {agencies.map((agency) => (
                <article className="row-item" key={agency.code}>
                  <Link className="search-result-title" href={`/agencies/${agency.code}`}>
                    {agency.name}
                  </Link>
                  <p className="lede">{agency.description}</p>
                  <div className="badge-row">
                    <span className="badge primary">{agency.code}</span>
                    <span className="badge">{agency.entityCount} objects</span>
                    <span className="badge amber">{agency.activeRulemakings} rulemakings</span>
                  </div>
                </article>
              ))}
            </div>
          </Panel>
        </aside>
      </div>
    </div>
  );
}
