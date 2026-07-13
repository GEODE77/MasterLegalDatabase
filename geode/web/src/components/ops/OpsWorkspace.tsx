import Link from "next/link";
import type { ReactElement, ReactNode } from "react";

import { ManagerQueueEditor } from "@/components/manager/ManagerQueueEditor";
import type {
  OpsLayer,
  OpsQualityStatus,
  OpsQueueItem,
  OpsSource,
  OpsWorkspaceData,
} from "@/lib/product/opsWorkspace";

type OpsWorkspaceProps = {
  data: OpsWorkspaceData;
  manager?: {
    name: string;
    role: string;
  };
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
  { href: "/manager/sources", label: "Check Sources" },
  { href: "/manager/review-queue", label: "Open Review Queue" },
  { href: "/manager/explore", label: "Explore Law" },
  { href: "/manager/publish", label: "Publication Readiness" },
  { href: "/manager/improvements", label: "Improvement Audit" },
];

export function OpsWorkspace({ data, manager, view }: OpsWorkspaceProps): ReactElement {
  return (
    <main className="ops-page">
      {manager ? (
        <section className="ops-manager-strip" aria-label="Verified manager">
          <span>Verified manager</span>
          <strong>{manager.name}</strong>
          <p>{manager.role}</p>
        </section>
      ) : null}
      {view === "home" ? <HomeView data={data} manager={manager} /> : null}
      {view === "sources" ? <SourcesView data={data} /> : null}
      {view === "review" ? <ReviewView data={data} /> : null}
      {view === "explorer" ? <ExplorerView layers={data.layers} /> : null}
      {view === "relationships" ? <RelationshipsView data={data} /> : null}
      {view === "timeline" ? <TimelineView data={data} /> : null}
      {view === "ask" ? <AskView /> : null}
      {view === "publish" ? <PublishView data={data} /> : null}
    </main>
  );
}

function HomeView({
  data,
  manager,
}: {
  data: OpsWorkspaceData;
  manager?: OpsWorkspaceProps["manager"];
}): ReactElement {
  const currentSources = data.sources.filter((source) => source.status === "no_change_detected").length;
  const primaryLinks =
    manager?.role === "admin"
      ? [...PRIMARY_LINKS, { href: "/manager/admin", label: "Manager Accounts" }]
      : PRIMARY_LINKS;
  const boardItems = [
    ["Sources", "Identify new official material before download.", "/manager/sources"],
    ["Review Queue", "Resolve blocked files and repair work.", "/manager/review-queue"],
    ["Explorer", "Search the corpus by layer, citation, agency, and topic.", "/manager/explore"],
    ["Relationships", "Follow statute, rule, bill, agency, and rulemaking links.", "/manager/relationships"],
    ["Timeline", "See checks, downloads, audits, and publication events.", "/manager/timeline"],
    ["Ask Geode", "Ask a question with source trails and freshness warnings.", "/manager/ask"],
    ["Publish", "Confirm safety, Git, dashboards, and blockers.", "/manager/publish"],
    ["Improvement Audit", "Review all 35 completed improvements and remaining follow-up work.", "/manager/improvements"],
  ];
  if (manager?.role === "admin") {
    boardItems.push(["Manager Accounts", "Create invites, revoke access, and review account history.", "/manager/admin"]);
  }

  return (
    <>
      <section className="ops-hero">
        <div>
          <p>Geode Manager Operations</p>
          <h2>One quiet place for verified managers to keep the legal corpus current, reviewable, and usable.</h2>
        </div>
        <div className="ops-hero-panel">
          <span>{manager ? `Signed in as ${manager.name} - ${manager.role}` : "Current recommendation"}</span>
          <p>{data.summary.nextRecommendation}</p>
        </div>
      </section>

      <section className="ops-metrics" aria-label="Workspace summary">
        <Metric label="Sources watched" value={formatNumber(data.summary.watchedSources)} />
        <Metric label="Current sources" value={formatNumber(currentSources)} />
        <Metric label="Review queue" value={formatNumber(data.summary.queueItems)} />
        <Metric label="Corpus records" value={formatNumber(data.summary.totalRecords)} />
      </section>

      <QualityStatusPanel quality={data.qualityStatus} />

      <section className="ops-command-strip" aria-label="Primary actions">
        {primaryLinks.map((link) => (
          <Link href={link.href} key={link.href}>
            {link.label}
          </Link>
        ))}
      </section>

      <section className="ops-two-column">
        <Panel title="Source Operations" eyebrow="Freshness">
          <SourceList sources={data.sources.slice(0, 5)} />
        </Panel>
        <Panel title="Manager Task Inbox" eyebrow={`${data.taskInbox.length} actions`}>
          <ControlList items={data.taskInbox} />
        </Panel>
      </section>

      <section className="ops-board" aria-label="Work areas">
        {boardItems.map(([title, body, href]) => (
          <Link href={href} key={href}>
            <span>{title}</span>
            <p>{body}</p>
          </Link>
        ))}
      </section>
    </>
  );
}

function QualityStatusPanel({ quality }: { quality: OpsQualityStatus }): ReactElement {
  const needsReviewCount = quality.layerSummary.needs_review ?? 0;
  const trustedCount = quality.layerSummary.trusted ?? 0;
  const validatedCount = quality.layerSummary.validated ?? 0;
  const visibleLayers = quality.layers.slice(0, 7);

  return (
    <Panel title="Corpus Quality Status" eyebrow={quality.overallQualityStage}>
      <div className="ops-quality-snapshot" aria-label="Quality status summary">
        <article>
          <span>Overall</span>
          <strong>{readableStatus(quality.overallQualityStage)}</strong>
          <p>{quality.localSystemUsable ? "Local system usable" : "Local system not ready"}</p>
        </article>
        <article>
          <span>Outside reliance</span>
          <strong>{quality.externalRelianceReady ? "Ready" : "Not ready"}</strong>
          <p>{quality.openSystemBlockers.length} blockers open</p>
        </article>
        <article>
          <span>Needs review</span>
          <strong>{formatNumber(needsReviewCount)}</strong>
          <p>{formatNumber(validatedCount + trustedCount)} layers validated or trusted</p>
        </article>
      </div>
      <div className="ops-quality-layer-list">
        {visibleLayers.map((layer) => (
          <article key={layer.id}>
            <div>
              <strong>{layer.label}</strong>
              <p>{formatNumber(layer.recordCount)} records</p>
              <p>{layer.reasons[0] ?? "No open quality limit is listed."}</p>
            </div>
            <div>
              <Status value={layer.qualityStage} />
              <span>{layer.officialRefreshRequired ? "Freshness check needed" : "Freshness checked"}</span>
            </div>
          </article>
        ))}
      </div>
      <p>{quality.agentGuidance}</p>
    </Panel>
  );
}
function SourcesView({ data }: { data: OpsWorkspaceData }): ReactElement {
  return (
    <>
      <Intro
        eyebrow="Sources"
        title="Official source monitoring before download."
        body="Each source is shown as a plain operating decision: current, new material, needs review, or blocked."
      />
      <section className="ops-metrics" aria-label="Source summary">
        <Metric label="New material" value={formatNumber(data.summary.newDataItems)} />
        <Metric label="Manual review" value={formatNumber(data.summary.manualReviewItems)} />
        <Metric label="Watched" value={formatNumber(data.summary.watchedSources)} />
        <Metric label="Generated" value={shortDate(data.summary.generatedAt)} />
      </section>
      <section className="ops-table-panel">
        <header>
          <span>Live Watcher</span>
          <h3>Source readiness</h3>
        </header>
        <div className="ops-source-table">
          {data.sources.map((source) => (
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
      <section className="ops-two-column">
        <Panel title="Download Approval Gate" eyebrow="Before download">
          <ControlList items={data.downloadGate} />
        </Panel>
        <Panel title="Live Source Probes" eyebrow="Automation">
          <ControlList items={data.sourceProbeControls} />
        </Panel>
      </section>
      <section className="ops-two-column">
        <Panel title="Source Operations Calendar" eyebrow="Next checks">
          <div className="ops-list">
            {data.calendar.slice(0, 6).map((item) => (
              <article key={item.sourceId}>
                <div>
                  <strong>{item.label}</strong>
                  <p>{item.nextCheck}</p>
                </div>
                <Status value={item.cadence} />
              </article>
            ))}
          </div>
        </Panel>
      </section>
    </>
  );
}

function ReviewView({ data }: { data: OpsWorkspaceData }): ReactElement {
  return (
    <>
      <Intro
        eyebrow="Review Queue"
        title="Every blocked or human-needed item in one place."
        body="This page should be the working list for official source repairs, blocked downloads, and manual review."
      />
      <Panel title="Open items" eyebrow={`${data.queue.length} queued`}>
        <QueueList items={data.queue} />
      </Panel>
      <section className="ops-two-column">
        <Panel title="Modern Repair Progress" eyebrow="LegiScan">
          <ControlList items={data.repairProgress} />
        </Panel>
        <Panel title="Known Blockers" eyebrow="Separated">
          <ControlList items={data.knownBlockers} />
        </Panel>
      </section>
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

function RelationshipsView({ data }: { data: OpsWorkspaceData }): ReactElement {
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
      <Panel title="Crosswalk Review" eyebrow={`${data.crosswalkReviews.length} files`}>
        <div className="ops-list">
          {data.crosswalkReviews.map((item) => (
            <article key={item.file}>
              <div>
                <strong>{item.file}</strong>
                <p>
                  {item.relationships.toLocaleString("en-US")} relationships. {item.missingEvidence} missing
                  evidence. {item.lowConfidence} low-confidence.
                </p>
              </div>
              <Status value={item.status} />
            </article>
          ))}
        </div>
      </Panel>
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
      <section className="ops-two-column">
        <Panel title="Download Closeout" eyebrow="Four checks">
          <ControlList items={data.closeout} />
        </Panel>
        <Panel title="Trust Controls" eyebrow="Safety">
          <ControlList items={data.trustControls} />
        </Panel>
      </section>
      <section className="ops-two-column">
        <Panel title="Pipeline Audit" eyebrow="Readable state">
          <QualityList items={data.pipelineAudit.slice(0, 6)} />
        </Panel>
        <Panel title="Quality And Reliability" eyebrow="Health">
          <QualityList items={data.qualityAreas} />
        </Panel>
      </section>
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
            <p>{item.ageLabel} - {item.owner}</p>
            <p>{item.officialSourceConfirmation}</p>
          </div>
          <Status value={item.status} />
          <ManagerQueueEditor item={item} />
        </article>
      ))}
    </div>
  );
}

function Status({ value }: { value: string }): ReactElement {
  return <span className="ops-status">{value.replaceAll("_", " ")}</span>;
}

function ControlList({
  items,
}: {
  items: Array<{ detail: string; label: string; status: string }>;
}): ReactElement {
  if (!items.length) {
    return <p>No active items are listed.</p>;
  }

  return (
    <div className="ops-list">
      {items.map((item) => (
        <article key={`${item.label}-${item.status}`}>
          <div>
            <strong>{item.label}</strong>
            <p>{item.detail}</p>
          </div>
          <Status value={item.status} />
        </article>
      ))}
    </div>
  );
}

function QualityList({
  items,
}: {
  items: Array<{ area: string; detail: string; status: string }>;
}): ReactElement {
  return (
    <div className="ops-list">
      {items.map((item) => (
        <article key={item.area}>
          <div>
            <strong>{item.area}</strong>
            <p>{item.detail}</p>
          </div>
          <Status value={item.status} />
        </article>
      ))}
    </div>
  );
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

function readableStatus(value: string): string {
  return value.replaceAll("_", " ");
}
