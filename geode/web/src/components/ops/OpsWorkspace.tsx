import Link from "next/link";
import type { ReactElement, ReactNode } from "react";

import type { OpsLayer, OpsQueueItem, OpsSource, OpsWorkspaceData } from "@/lib/product/opsWorkspace";

type OpsWorkspaceProps = {
  data: OpsWorkspaceData;
  view:
    | "ask"
    | "explorer"
    | "home"
    | "publish"
    | "relationships"
    | "review"
    | "sources"
    | "timeline";
};

const PRIMARY_LINKS = [
  { href: "/app/sources", label: "Check Sources" },
  { href: "/app/review-queue", label: "Open Review Queue" },
  { href: "/app/explore", label: "Explore Law" },
  { href: "/app/publish", label: "Publication Readiness" },
];

export function OpsWorkspace({ data, view }: OpsWorkspaceProps): ReactElement {
  return (
    <main className="ops-page">
      {view === "home" ? <HomeView data={data} /> : null}
      {view === "sources" ? <SourcesView sources={data.sources} summary={data.summary} /> : null}
      {view === "review" ? <ReviewView queue={data.queue} /> : null}
      {view === "explorer" ? <ExplorerView layers={data.layers} /> : null}
      {view === "relationships" ? <RelationshipsView /> : null}
      {view === "timeline" ? <TimelineView data={data} /> : null}
      {view === "ask" ? <AskView /> : null}
      {view === "publish" ? <PublishView data={data} /> : null}
    </main>
  );
}

function HomeView({ data }: { data: OpsWorkspaceData }): ReactElement {
  const currentSources = data.sources.filter((source) => source.status === "no_change_detected").length;

  return (
    <>
      <section className="ops-hero">
        <div>
          <p>Geode Operations</p>
          <h2>One quiet place to keep the legal corpus current, reviewable, and usable.</h2>
        </div>
        <div className="ops-hero-panel">
          <span>Current recommendation</span>
          <p>{data.summary.nextRecommendation}</p>
        </div>
      </section>

      <section className="ops-metrics" aria-label="Workspace summary">
        <Metric label="Sources watched" value={formatNumber(data.summary.watchedSources)} />
        <Metric label="Current sources" value={formatNumber(currentSources)} />
        <Metric label="Review queue" value={formatNumber(data.summary.queueItems)} />
        <Metric label="Corpus records" value={formatNumber(data.summary.totalRecords)} />
      </section>

      <section className="ops-command-strip" aria-label="Primary actions">
        {PRIMARY_LINKS.map((link) => (
          <Link href={link.href} key={link.href}>
            {link.label}
          </Link>
        ))}
      </section>

      <section className="ops-two-column">
        <Panel title="Source Operations" eyebrow="Freshness">
          <SourceList sources={data.sources.slice(0, 5)} />
        </Panel>
        <Panel title="Review Queue" eyebrow={`${data.queue.length} open`}>
          <QueueList items={data.queue} />
        </Panel>
      </section>

      <section className="ops-board" aria-label="Work areas">
        {[
          ["Sources", "Identify new official material before download.", "/app/sources"],
          ["Review Queue", "Resolve blocked files and repair work.", "/app/review-queue"],
          ["Explorer", "Search the corpus by layer, citation, agency, and topic.", "/app/explore"],
          ["Relationships", "Follow statute, rule, bill, agency, and rulemaking links.", "/app/relationships"],
          ["Timeline", "See checks, downloads, audits, and publication events.", "/app/timeline"],
          ["Ask Geode", "Ask a question with source trails and freshness warnings.", "/app/ask"],
          ["Publish", "Confirm safety, Git, dashboards, and blockers.", "/app/publish"],
        ].map(([title, body, href]) => (
          <Link href={href} key={href}>
            <span>{title}</span>
            <p>{body}</p>
          </Link>
        ))}
      </section>
    </>
  );
}

function SourcesView({
  sources,
  summary,
}: {
  sources: OpsSource[];
  summary: OpsWorkspaceData["summary"];
}): ReactElement {
  return (
    <>
      <Intro
        eyebrow="Sources"
        title="Official source monitoring before download."
        body="Each source is shown as a plain operating decision: current, new material, needs review, or blocked."
      />
      <section className="ops-metrics" aria-label="Source summary">
        <Metric label="New material" value={formatNumber(summary.newDataItems)} />
        <Metric label="Manual review" value={formatNumber(summary.manualReviewItems)} />
        <Metric label="Watched" value={formatNumber(summary.watchedSources)} />
        <Metric label="Generated" value={shortDate(summary.generatedAt)} />
      </section>
      <section className="ops-table-panel">
        <header>
          <span>Live Watcher</span>
          <h3>Source readiness</h3>
        </header>
        <div className="ops-source-table">
          {sources.map((source) => (
            <article key={source.id}>
              <div>
                <strong>{source.name}</strong>
                <span>{source.layerIds.join(", ") || "No layer assigned"}</span>
              </div>
              <Status value={source.status} />
              <span>{source.localMarker ?? "none"}</span>
              <span>{source.observedMarker ?? "none"}</span>
              <p>{source.nextStep}</p>
            </article>
          ))}
        </div>
      </section>
    </>
  );
}

function ReviewView({ queue }: { queue: OpsQueueItem[] }): ReactElement {
  return (
    <>
      <Intro
        eyebrow="Review Queue"
        title="Every blocked or human-needed item in one place."
        body="This page should be the working list for official source repairs, blocked downloads, and manual review."
      />
      <Panel title="Open items" eyebrow={`${queue.length} queued`}>
        <QueueList items={queue} />
      </Panel>
      <section className="ops-review-flow" aria-label="Review flow">
        {["Find official source", "Confirm file", "Run guarded intake", "Validate", "Push"].map((step, index) => (
          <div key={step}>
            <span>{index + 1}</span>
            <strong>{step}</strong>
          </div>
        ))}
      </section>
    </>
  );
}

function ExplorerView({ layers }: { layers: OpsLayer[] }): ReactElement {
  return (
    <>
      <Intro
        eyebrow="Explorer"
        title="Browse the law by layer before asking a question."
        body="The frontend should make the corpus feel like a library, not a file tree."
      />
      <section className="ops-search-shell" aria-label="Search surface">
        <label htmlFor="ops-search">Search Geode</label>
        <input id="ops-search" placeholder="Try CRS 25-7-109, air quality, licensing, rulemaking" />
      </section>
      <section className="ops-layer-grid" aria-label="Legal layers">
        {layers.map((layer) => (
          <article key={layer.id}>
            <span>{layer.source}</span>
            <strong>{layer.id}</strong>
            <p>{formatNumber(layer.records)} records</p>
          </article>
        ))}
      </section>
    </>
  );
}

function RelationshipsView(): ReactElement {
  return (
    <>
      <Intro
        eyebrow="Relationships"
        title="Start from one legal item and follow the connected authority."
        body="This view is arranged around the relationships Geode already builds: statute to regulation, bill to statute, rulemaking to regulation, and agency to statute."
      />
      <section className="ops-relationship-map" aria-label="Relationship map mockup">
        <div>Statute</div>
        <div>Regulations</div>
        <div>Bills</div>
        <div>Rulemaking</div>
        <div>Agencies</div>
      </section>
    </>
  );
}

function TimelineView({ data }: { data: OpsWorkspaceData }): ReactElement {
  const events = [
    ["Official source check", data.summary.generatedAt ?? "unknown", "Watcher refreshed source markers."],
    ["Manual review remains", "active", `${data.summary.queueItems} queue items need review.`],
    ["Corpus state", "current local", `${formatNumber(data.summary.totalRecords)} records are indexed.`],
    ["Publication", "after closeout", data.summary.pushedState],
  ];

  return (
    <>
      <Intro
        eyebrow="Timeline"
        title="A simple chronology for source checks, downloads, audits, and publication."
        body="The user should always know when Geode last checked a source and what changed afterward."
      />
      <section className="ops-timeline" aria-label="Timeline">
        {events.map(([title, date, body]) => (
          <article key={title}>
            <span>{date}</span>
            <strong>{title}</strong>
            <p>{body}</p>
          </article>
        ))}
      </section>
    </>
  );
}

function AskView(): ReactElement {
  return (
    <>
      <Intro
        eyebrow="Ask Geode"
        title="A question surface grounded in citations and freshness."
        body="The answer area should always show what documents were used, whether any source is stale, and which citations support the response."
      />
      <section className="ops-ask-layout" aria-label="Ask Geode">
        <div>
          <label htmlFor="ops-question">Question</label>
          <textarea id="ops-question" placeholder="What Colorado requirements affect a small manufacturer?" />
          <button type="button">Prepare cited answer</button>
        </div>
        <aside>
          <span>Answer requirements</span>
          <p>Citations, source snippets, related laws, and freshness warnings must appear with every answer.</p>
        </aside>
      </section>
    </>
  );
}

function PublishView({ data }: { data: OpsWorkspaceData }): ReactElement {
  const checks = [
    ["Secrets", "Passed"],
    ["Pending downloads", data.summary.queueItems ? "Review remains" : "Clear"],
    ["Dashboard", "Updated"],
    ["Git", "Pushed"],
  ];

  return (
    <>
      <Intro
        eyebrow="Publish"
        title="A release checklist before anything becomes public."
        body="Publication should feel like a controlled final review, not a search through logs."
      />
      <section className="ops-publish-grid" aria-label="Publication readiness">
        {checks.map(([label, value]) => (
          <article key={label}>
            <span>{label}</span>
            <strong>{value}</strong>
          </article>
        ))}
      </section>
      <Panel title="Release boundary" eyebrow={data.summary.overallStatus}>
        <p>{data.summary.nextRecommendation}</p>
      </Panel>
    </>
  );
}

function Intro({ body, eyebrow, title }: { body: string; eyebrow: string; title: string }): ReactElement {
  return (
    <section className="ops-intro">
      <p>{eyebrow}</p>
      <h2>{title}</h2>
      <span>{body}</span>
    </section>
  );
}

function Panel({
  children,
  eyebrow,
  title,
}: {
  children: ReactNode;
  eyebrow: string;
  title: string;
}): ReactElement {
  return (
    <section className="ops-panel">
      <header>
        <span>{eyebrow}</span>
        <h3>{title}</h3>
      </header>
      {children}
    </section>
  );
}

function Metric({ label, value }: { label: string; value: string }): ReactElement {
  return (
    <article>
      <span>{label}</span>
      <strong>{value}</strong>
    </article>
  );
}

function SourceList({ sources }: { sources: OpsSource[] }): ReactElement {
  return (
    <div className="ops-list">
      {sources.map((source) => (
        <article key={source.id}>
          <div>
            <strong>{source.name}</strong>
            <p>{source.nextStep}</p>
          </div>
          <Status value={source.status} />
        </article>
      ))}
    </div>
  );
}

function QueueList({ items }: { items: OpsQueueItem[] }): ReactElement {
  if (!items.length) {
    return <p>No review items are queued.</p>;
  }

  return (
    <div className="ops-list">
      {items.map((item) => (
        <article key={item.id}>
          <div>
            <strong>{item.id}</strong>
            <p>{item.reason}</p>
          </div>
          <Status value={item.status} />
        </article>
      ))}
    </div>
  );
}

function Status({ value }: { value: string }): ReactElement {
  return <span className="ops-status">{value.replaceAll("_", " ")}</span>;
}

function formatNumber(value: number): string {
  return value.toLocaleString("en-US");
}

function shortDate(value: string | null): string {
  if (!value) {
    return "unknown";
  }

  return value.slice(0, 10);
}
