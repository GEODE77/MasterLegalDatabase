import Link from "next/link";
import type { ReactElement } from "react";

import { readOnboardingAnalytics } from "@/lib/onboarding/analytics";

export const dynamic = "force-dynamic";

export default function OnboardingAnalyticsPage(): ReactElement {
  const analytics = readOnboardingAnalytics();

  return (
    <main className="debug-page">
      <header className="debug-header">
        <Link className="dashboard-mark" href="/debug/personalization">
          <span className="dashboard-mark-symbol">GE</span>
          <span>GEODE</span>
        </Link>
        <span>Onboarding Analytics</span>
      </header>
      <section className="debug-panel">
        <p className="query-kicker">Founder demo readiness</p>
        <h1>{formatPercent(analytics.conversionRate)} confirmed</h1>
        <div className="debug-summary-grid">
          <Metric label="Starts" value={String(analytics.startedSessions)} />
          <Metric label="Analyzed" value={String(analytics.analyzedDocuments)} />
          <Metric label="Confirmed" value={String(analytics.confirmedProfiles)} />
          <Metric label="Skipped" value={String(analytics.skippedProfiles)} />
        </div>
      </section>
      <section className="debug-grid">
        <MetricPanel
          label="Surface drop-off"
          rows={[
            ["entry to analysis", formatPercent(analytics.analysisRate)],
            ["analysis to confirm", formatPercent(analytics.analysisToConfirmRate)],
            ["skip rate", formatPercent(analytics.skipRate)],
          ]}
        />
        <MetricPanel
          label="Timing"
          rows={[
            ["average parse", formatSeconds(analytics.averageParseSeconds)],
            ["average completion", formatSeconds(analytics.averageCompletionSeconds)],
            ["parse failures", String(analytics.failedParses)],
          ]}
        />
        <MetricPanel
          label="Input mix"
          rows={[
            ["file drops", String(analytics.droppedFiles)],
            ["pasted files", String(analytics.pastedDocuments)],
            ["profiles observed", String(analytics.totalProfiles)],
          ]}
        />
        <MetricPanel
          label="Progressive prompts"
          rows={[
            ["shown", String(analytics.promptShows)],
            ["answered", String(analytics.promptAnswers)],
            ["dismissed", String(analytics.promptDismissals)],
            ["answer rate", formatPercent(analytics.promptAnswerRate)],
          ]}
        />
      </section>
    </main>
  );
}

type MetricProps = {
  label: string;
  value: string;
};

function Metric({ label, value }: MetricProps): ReactElement {
  return (
    <div className="debug-metric">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

type MetricPanelProps = {
  label: string;
  rows: Array<[string, string]>;
};

function MetricPanel({ label, rows }: MetricPanelProps): ReactElement {
  return (
    <section className="debug-panel">
      <p className="query-kicker">{label}</p>
      <div className="analytics-list">
        {rows.map(([name, value]) => (
          <div key={name}>
            <span>{name}</span>
            <strong>{value}</strong>
          </div>
        ))}
      </div>
    </section>
  );
}

function formatPercent(value: number): string {
  return `${Math.round(value * 100)}%`;
}

function formatSeconds(value: number | null): string {
  return value === null ? "n/a" : `${value}s`;
}
