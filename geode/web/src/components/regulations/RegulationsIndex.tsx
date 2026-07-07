"use client";

import Link from "next/link";
import { useMemo, useState, type ReactElement } from "react";

import { PublicNav } from "@/components/navigation/PublicNav";
import { RECENT_REGULATIONS_KEY, useRecentItems } from "@/hooks/useRecentItems";
import type { RegulationSearchResult } from "@/lib/search/types";

type RegulationsIndexProps = {
  regulations: RegulationSearchResult[];
  stats: {
    agencyCount: number;
    count: number;
    lastUpdated: string | null;
  };
};

export function RegulationsIndex({ regulations, stats }: RegulationsIndexProps): ReactElement {
  const [search, setSearch] = useState("");
  const { addItem: addRecentRegulation, items: recentRegulations } = useRecentItems(RECENT_REGULATIONS_KEY);
  const visibleRegulations = useMemo(() => {
    const query = search.trim().toLowerCase();

    if (!query) {
      return regulations;
    }

    return regulations.filter((regulation) => {
      const haystack = `${regulation.title} ${regulation.citation} ${regulation.excerpt}`.toLowerCase();
      return haystack.includes(query);
    });
  }, [regulations, search]);

  return (
    <main className="regulations-index-page">
      <PublicNav current="library" />
      <section className="public-page-hero regulations-index-hero" aria-labelledby="regulations-title">
        <p>Code of Colorado Regulations</p>
        <h1 id="regulations-title">Browse Colorado regulation records from the public legal library.</h1>
        <span>
          {stats.count.toLocaleString("en-US")} indexed records across{" "}
          {stats.agencyCount.toLocaleString("en-US")} agencies. Last checked:{" "}
          {stats.lastUpdated ?? "unknown"}.
        </span>
      </section>
      <form className="regulation-search" onSubmit={(event) => event.preventDefault()}>
        <label htmlFor="regulation-index-search">Search regulations</label>
        <input
          id="regulation-index-search"
          onChange={(event) => setSearch(event.target.value)}
          placeholder="Search by citation, agency, or rule"
          value={search}
        />
        {search.trim().length === 0 && recentRegulations.length > 0 ? (
          <div className="recent-inline-list" aria-label="Recent regulations">
            {recentRegulations.map((item) => (
              <Link href={item.href} key={item.id}>
                {item.label}
              </Link>
            ))}
          </div>
        ) : null}
      </form>

      <section className="regulations-index-list" aria-label="Regulations">
        {visibleRegulations.length > 0 ? (
          visibleRegulations.map((regulation) => (
            <Link
              href={`/regulations/${encodeURIComponent(regulation.id)}`}
              key={regulation.id}
              onClick={() => addRecentRegulation({
                detail: regulation.citation,
                href: `/regulations/${encodeURIComponent(regulation.id)}`,
                id: regulation.id,
                label: regulation.title,
              })}
            >
              <span>{regulation.citation}</span>
              <strong>{regulation.title}</strong>
              <p>{regulation.excerpt || "Source text available in Geode."}</p>
              <small>Open record</small>
            </Link>
          ))
        ) : (
          <div className="recovery-state compact">
            <span className="recovery-illustration" aria-hidden="true" />
            <p>No regulations match that search. Clear the field to return to the index.</p>
            <button onClick={() => setSearch("")} type="button">
              Clear search
            </button>
          </div>
        )}
      </section>
    </main>
  );
}
