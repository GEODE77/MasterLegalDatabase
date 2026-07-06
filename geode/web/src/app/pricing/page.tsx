import type { ReactElement } from "react";

const CTA_LABEL = "Talk to us";

export default function PricingPage(): ReactElement {
  return (
    <main className="pricing-page">
      <article className="pricing-document">
        <header className="pricing-hero">
          <h1>Pricing begins with the operating problem.</h1>
          <p>Geode is sold for teams that need regulatory intelligence tied to decisions, source material, and accountable workflows.</p>
        </header>

        <section className="pricing-tier" aria-label="Pricing">
          <div>
            <span>Enterprise</span>
            <p>One deployment shaped around corpus scope, workflow depth, and the number of teams using Geode.</p>
          </div>
          <a href="mailto:sales@geode.local">{CTA_LABEL}</a>
        </section>

        <section className="pricing-close" aria-label="Contact sales">
          <h2>Bring Geode to the regulatory work that cannot wait.</h2>
          <a href="mailto:sales@geode.local">{CTA_LABEL}</a>
        </section>
      </article>
    </main>
  );
}
