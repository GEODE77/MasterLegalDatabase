"use client";

import Link from "next/link";
import { useMemo, useState, type ReactElement } from "react";

import { RECENT_REGULATIONS_KEY, useRecentItems } from "@/hooks/useRecentItems";
import type { RegulationSearchResult } from "@/lib/search/types";

type RegulationsIndexProps = {
  regulations: RegulationSearchResult[];
};

export function RegulationsIndex({ regulations }: RegulationsIndexProps): ReactElement {
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
