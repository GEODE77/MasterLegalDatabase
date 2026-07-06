"use client";

import Link from "next/link";
import type { ReactElement } from "react";

import { usePersonalization } from "@/hooks/usePersonalization";

export function PersonalizationDebugSurface(): ReactElement {
  const { profile } = usePersonalization();
  const recentEvents = profile.behaviorEvents.slice(-12).reverse();

  return (
    <main className="debug-page">
      <header className="debug-header">
        <Link className="dashboard-mark" href="/app/dashboard">
          <span className="dashboard-mark-symbol">GE</span>
          <span>GEODE</span>
        </Link>
        <span>Personalization Debug</span>
      </header>
      <section className="debug-panel">
        <p className="query-kicker">Derived model</p>
        <Link className="debug-secondary-link" href="/debug/onboarding">
          View onboarding analytics
        </Link>
        <h1>{profile.derived.primaryInterest ?? "No dominant interest yet"}</h1>
        <div className="debug-summary-grid">
          <Metric label="Confidence" value={`${Math.round(profile.derived.confidence * 100)}%`} />
          <Metric label="Reading density" value={profile.derived.readingDensity} />
          <Metric label="Tone" value={profile.derived.preferredTone} />
          <Metric label="Events" value={String(profile.behaviorEvents.length)} />
        </div>
      </section>
      <section className="debug-grid">
        <VectorBlock label="Industries" rows={profile.derived.industryVector} />
        <VectorBlock label="Agencies" rows={profile.derived.agencyVector} />
        <VectorBlock label="Surfaces" rows={profile.derived.surfaceVector} />
        <VectorBlock label="Roles" rows={profile.derived.roleVector} />
      </section>
      <section className="debug-panel">
        <p className="query-kicker">Recent behavior</p>
        <div className="debug-event-list">
          {recentEvents.length > 0 ? (
            recentEvents.map((event) => (
              <article key={event.eventId}>
                <strong>{event.type}</strong>
                <span>{new Date(event.recordedAt).toLocaleString()}</span>
                <code>{JSON.stringify(event.payload)}</code>
              </article>
            ))
          ) : (
            <article className="recovery-state">
              <span className="recovery-illustration" aria-hidden="true" />
              <p>No behavior events have been recorded yet. Use search, forum, or onboarding to generate the first signals.</p>
              <Link href="/query">Ask a question</Link>
            </article>
          )}
        </div>
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

type VectorBlockProps = {
  label: string;
  rows: Array<{ key: string; weight: number }>;
};

function VectorBlock({ label, rows }: VectorBlockProps): ReactElement {
  return (
    <section className="debug-panel">
      <p className="query-kicker">{label}</p>
      <div className="debug-vector">
        {rows.length > 0 ? (
          rows.map((row) => (
            <div key={row.key}>
              <span>{row.key}</span>
              <meter max={1} min={0} value={row.weight} />
              <strong>{Math.round(row.weight * 100)}%</strong>
            </div>
          ))
        ) : (
          <div className="debug-empty recovery-state">
            <span className="recovery-illustration" aria-hidden="true" />
            <p>No signal has been recorded for this dimension yet.</p>
            <Link href="/onboarding">Review onboarding</Link>
          </div>
        )}
      </div>
    </section>
  );
}
