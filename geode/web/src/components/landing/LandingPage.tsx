import Link from "next/link";
import type { ReactElement } from "react";

import { LiveDataCenterpiece } from "@/components/index/LiveDataCenterpiece";
import { LiveIndexChart } from "@/components/index/LiveIndexChart";
import { LandingProductSample } from "@/components/landing/LandingProductSample";
import { getForumStats } from "@/lib/forum/store";
import { getGeodeIndexStats } from "@/lib/index/geodeIndexStats";
import { getRegulationCorpusStats } from "@/lib/search/searchRegulations";

const CTA_LABEL = "Search Geode";
const HERO_HEADLINE = "Geode makes regulation readable as infrastructure.";

export function LandingPage(): ReactElement {
  const stats = getRegulationCorpusStats();
  const indexStats = getGeodeIndexStats();
  const forumStats = getForumStats();

  return (
    <main className="landing-page landing-document" id="top">
      <header className="landing-header" aria-label="Geode">
        <div className="landing-header-left">
          <Link className="landing-brand" href="/" aria-label="Geode home">
            Geode
          </Link>
          <nav className="landing-nav" aria-label="Landing navigation">
            <a href="#product">Product</a>
            <Link href="/library">Library</Link>
            <Link href="/about">About</Link>
            <Link href="/forum">Forum</Link>
            <Link href="/pricing">Pricing</Link>
          </nav>
        </div>
        <div className="landing-header-actions">
          <Link href="/manager/verify">Managers</Link>
          <Link className="landing-cta" href="/query">
            {CTA_LABEL}
          </Link>
        </div>
      </header>

      <section className="landing-section landing-hero" aria-labelledby="landing-title">
        <LiveDataCenterpiece initialStats={indexStats} />
        <h1 id="landing-title">{HERO_HEADLINE}</h1>
        <div className="landing-public-actions">
          <Link className="landing-cta" href="/query">
            {CTA_LABEL}
          </Link>
          <Link className="landing-cta landing-cta-secondary" href="/library">
            Browse Library
          </Link>
        </div>
      </section>

      <section className="landing-section landing-index-chart" aria-label="Regulatory velocity">
        <LiveIndexChart initialStats={indexStats} />
      </section>

      <section className="landing-section landing-trust" aria-label="Customer trust">
        <h2>Built for the teams who turn regulation into operating decisions.</h2>
        <div>
          <span>Operator</span>
          <span>Counsel</span>
          <span>Policy</span>
        </div>
      </section>

      <section className="landing-section landing-pillars" id="product" aria-label="Geode capabilities">
        <div>
          <h2>Built to find authority</h2>
          <p>Ask a question and Geode returns the rules, citations, and agencies that govern the decision.</p>
        </div>
        <div>
          <h2>Built for executive context</h2>
          <p>Read regulatory exposure in the language of operations, risk, finance, and legal review.</p>
        </div>
        <div>
          <h2>Built at statutory scale</h2>
          <p>Search across the regulatory corpus without reducing source law to summaries alone.</p>
        </div>
      </section>

      <LandingProductSample />

      <section className="landing-section landing-outcomes" id="about" aria-label="Quantified outcomes">
        <div>
          <strong>{indexStats.count.toLocaleString("en-US")}</strong>
          <span>Authorities</span>
        </div>
        <div>
          <strong>{stats.agencyCount.toLocaleString("en-US")}</strong>
          <span>Agencies</span>
        </div>
        <div>
          <strong>{forumStats.memberCount.toLocaleString("en-US")}</strong>
          <span>Members</span>
        </div>
      </section>

      <section className="landing-section landing-press" aria-label="Press">
        <h2>Geode in the Record</h2>
        <div>
          <a href="https://www.sos.state.co.us/CCR/RegisterHome.do">
            <span>Colorado Register</span>
            <strong>Rulemaking record indexed for executive review</strong>
          </a>
          <a href="https://leg.colorado.gov/">
            <span>Colorado General Assembly</span>
            <strong>Legislative source layer connected to Geode</strong>
          </a>
          <a href="https://legiscan.com/CO">
            <span>LegiScan</span>
            <strong>Bill activity available for regulatory context</strong>
          </a>
        </div>
      </section>

      <section className="landing-section landing-testimonial" aria-label="Executive testimonial">
        <blockquote>
          <p>Geode turns a regulatory search into an executive record.</p>
          <footer>
            <span>Jordan Ellis</span>
            <span>Chief Operating Officer, placeholder customer</span>
          </footer>
        </blockquote>
      </section>

      <section className="landing-section landing-close" id="pricing" aria-label="Search Geode">
        <h2>Make regulation readable before the next operating decision.</h2>
        <Link className="landing-cta" href="/query">
          {CTA_LABEL}
        </Link>
      </section>

      <footer className="landing-footer" aria-label="Footer">
        <Link href="/about">About</Link>
        <Link href="/library">Library</Link>
        <Link href="/trust">Trust</Link>
        <Link href="/pricing">Pricing</Link>
        <Link href="/manager/verify">Managers</Link>
        <a href="mailto:contact@geode.local">Contact</a>
      </footer>
    </main>
  );
}
