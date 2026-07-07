import Link from "next/link";
import type { ReactElement } from "react";

import { PublicNav } from "@/components/navigation/PublicNav";
import { getGeodeIndexStats } from "@/lib/index/geodeIndexStats";
import { getRegulationCorpusStats } from "@/lib/search/searchRegulations";

const PUBLIC_ACTIONS = [
  {
    body: "Ask a question and open a cited research note.",
    href: "/query",
    label: "Search legal data",
  },
  {
    body: "Browse statutes, rules, legislation, rulemaking, orders, and supplementary records.",
    href: "/library",
    label: "Browse the library",
  },
  {
    body: "Read public discussion tied to legal and regulatory work.",
    href: "/forum",
    label: "Open the forum",
  },
];

export function LandingPage(): ReactElement {
  const stats = getRegulationCorpusStats();
  const indexStats = getGeodeIndexStats();

  return (
    <main className="public-resource-page" id="top">
      <PublicNav current="home" />

      <section className="public-home-hero" aria-labelledby="landing-title">
        <p>Colorado legal data, open for use</p>
        <h1 id="landing-title">Search, browse, and review Geode without creating an account.</h1>
        <div className="public-home-actions">
          <Link href="/query">Search Geode</Link>
          <Link href="/library">Browse library</Link>
        </div>
      </section>

      <section className="public-home-grid" aria-label="Primary public actions">
        {PUBLIC_ACTIONS.map((action) => (
          <Link href={action.href} key={action.href}>
            <span>{action.label}</span>
            <p>{action.body}</p>
          </Link>
        ))}
      </section>

      <section className="public-home-status" aria-label="Corpus status">
        <article>
          <span>Indexed authorities</span>
          <strong>{indexStats.count.toLocaleString("en-US")}</strong>
        </article>
        <article>
          <span>Agencies</span>
          <strong>{stats.agencyCount.toLocaleString("en-US")}</strong>
        </article>
        <article>
          <span>Public access</span>
          <strong>No sign-in</strong>
        </article>
        <article>
          <span>Manager tools</span>
          <strong>Invite only</strong>
        </article>
      </section>

      <section className="public-home-manager-note" aria-label="Manager boundary">
        <div>
          <span>Separate manager workspace</span>
          <h2>Source operations, repairs, and publication controls require verified manager access.</h2>
          <p>
            Regular Geode users can read and search the public resources directly. Managers use a named
            invite so source changes, review actions, and publication decisions have a clear record.
          </p>
        </div>
        <Link href="/manager/verify">Open manager verification</Link>
      </section>

      <footer className="public-footer" aria-label="Footer">
        <Link href="/about">About</Link>
        <Link href="/trust">Trust</Link>
        <Link href="/pricing">Pricing</Link>
        <a href="mailto:contact@geode.local">Contact</a>
      </footer>
    </main>
  );
}
