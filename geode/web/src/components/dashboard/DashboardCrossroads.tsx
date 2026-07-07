import Link from "next/link";
import type { ReactElement } from "react";

import { LiveDataCenterpiece } from "@/components/index/LiveDataCenterpiece";
import { LiveIndexChart } from "@/components/index/LiveIndexChart";
import type { GeodeIndexStats } from "@/lib/index/geodeIndexStats";

type Workflow = {
  cta: string;
  description: string;
  href: string;
  label: string;
};

type DashboardCrossroadsProps = {
  greeting: string;
  headline: string;
  indexStats: GeodeIndexStats;
  recentItems: DashboardActivityEntry[];
};

type DashboardActivityEntry = {
  action: string;
  author: string;
  authorHref: string;
  id: string;
  timeAgo: string;
  title: string;
};

const WORKFLOWS: Workflow[] = [
  {
    cta: "Open",
    description: "Turn regulatory interpretation into shared operating judgment.",
    href: "/forum",
    label: "Open the forum.",
  },
  {
    cta: "Ask",
    description: "Search the corpus for cited authority and source-backed answers.",
    href: "/query",
    label: "Ask a question.",
  },
  {
    cta: "Find",
    description: "Search source-backed duties, permits, reporting, and inspection signals.",
    href: "/manager/requirements",
    label: "Find requirements.",
  },
  {
    cta: "Review",
    description: "See the signals Geode uses to shape your regulatory view.",
    href: "/settings",
    label: "Review my activity.",
  },
];

export function DashboardCrossroads({
  greeting,
  headline,
  indexStats,
  recentItems,
}: DashboardCrossroadsProps): ReactElement {
  return (
    <main className="dashboard-crossroads">
      <section className="dashboard-document" aria-label="Dashboard">
        <section className="dashboard-hero">
          <h1 className="dashboard-personalization-line">{greeting}</h1>
          <p className="dashboard-current-line">{headline}</p>
          <LiveDataCenterpiece initialStats={indexStats} size="compact" />
          <LiveIndexChart initialStats={indexStats} size="compact" />
        </section>

        <section className="dashboard-workflows" aria-label="Primary workflows">
          {WORKFLOWS.map((workflow) => (
            <Link href={workflow.href} key={workflow.label}>
              <span>{workflow.label}</span>
              <span>{workflow.description}</span>
              <strong>{workflow.cta}</strong>
            </Link>
          ))}
        </section>

        {recentItems.length > 0 ? (
          <section className="dashboard-history" id="recent-activity" aria-label="Recent activity">
            <p>Recent activity</p>
            <div>
              {recentItems.map((item) => (
                <span key={item.id}>
                  <Link href={item.authorHref}>{item.author}</Link> {item.action}{" "}
                  <i>{item.title}</i> {item.timeAgo} ago.
                </span>
              ))}
            </div>
          </section>
        ) : null}
      </section>
    </main>
  );
}
