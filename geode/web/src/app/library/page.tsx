import Link from "next/link";
import type { ReactElement } from "react";

import { getOpsWorkspaceData } from "@/lib/product/opsWorkspace";

export const dynamic = "force-dynamic";

export default function PublicLibraryPage(): ReactElement {
  const data = getOpsWorkspaceData();

  return (
    <main className="public-library-page">
      <header className="public-library-header">
        <Link href="/">Geode</Link>
        <nav aria-label="Public library navigation">
          <Link href="/query">Search</Link>
          <Link href="/trust">Trust</Link>
          <Link href="/manager/verify">Managers</Link>
        </nav>
      </header>

      <section className="public-library-hero">
        <p>Colorado Legal Data Library</p>
        <h1>Search by citation, browse by source, and check freshness before relying on a result.</h1>
        <div>
          <Link href="/query">Search by citation</Link>
          <a href="#sources">Browse sources</a>
        </div>
      </section>

      <section className="public-library-search" aria-label="Citation-first search guide">
        <span>Citation-first search</span>
        <p>Start with CRS, CCR, bill number, executive order, agency, or topic.</p>
        <div>
          {["CRS 25-7-109", "5 CCR 1001-9", "SB23-016", "EO-2025-003", "CDPHE", "air quality"].map(
            (example) => (
              <Link href={`/query?q=${encodeURIComponent(example)}`} key={example}>
                {example}
              </Link>
            ),
          )}
        </div>
      </section>

      <section className="public-library-grid" id="sources" aria-label="Legal data layers">
        {data.layers.map((layer) => (
          <article key={layer.id}>
            <span>{layer.status}</span>
            <h2>{layer.id.replaceAll("_", " ")}</h2>
            <p>{layer.records.toLocaleString("en-US")} records from {layer.source}.</p>
            <small>Last checked: {layer.lastChecked ?? "unknown"}</small>
          </article>
        ))}
      </section>

      <section className="public-library-explain" aria-label="Result explanation policy">
        <article>
          <span>Freshness warnings</span>
          <p>Every source should be treated as current, stale, blocked, or needing review before public reliance.</p>
        </article>
        <article>
          <span>Why this result</span>
          <p>Search results should explain whether they matched a citation, agency, topic, or relationship.</p>
        </article>
        <article>
          <span>Source cards</span>
          <p>Each legal layer shows what it contains, how fresh it is, and where the official source comes from.</p>
        </article>
      </section>
    </main>
  );
}
