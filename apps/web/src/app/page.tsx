import Link from "next/link";
import { getDashboardData } from "@/lib/data";

const pillars = [
  {
    name: "Regulatory Discovery",
    description: "Official law, rules, notices, and orders resolved into source-backed objects."
  },
  {
    name: "Market Intelligence",
    description: "Agency activity, amendments, and obligations tracked across time."
  },
  {
    name: "Decision Infrastructure",
    description: "Structured records that let teams compare exposure before they act."
  }
];

const validationSources = ["General Assembly", "Secretary of State", "Colorado Register"];

function latestDate(dates: string[]) {
  return dates
    .filter(Boolean)
    .sort((left, right) => new Date(right).getTime() - new Date(left).getTime())[0];
}

function formatDate(date: string | undefined) {
  if (!date) {
    return "No timestamp";
  }

  return new Intl.DateTimeFormat("en", {
    month: "short",
    day: "numeric",
    year: "numeric",
    timeZone: "UTC"
  }).format(new Date(date));
}

export default async function LandingPage() {
  const { entities, timelineEvents, agencies } = await getDashboardData();
  const latestUpdate = latestDate([
    ...timelineEvents.map((event) => event.date),
    ...entities.map((entity) => entity.effectiveDate)
  ]);

  return (
    <div className="landing-page">
      <header className="landing-nav" aria-label="Geode">
        <Link href="/">Geode</Link>
        <Link href="/search">Corpus</Link>
      </header>

      <main>
        <section className="landing-section landing-hero">
          <div>
            <p className="landing-kicker">Colorado regulatory intelligence</p>
            <h1>The foundation of the regulatory market.</h1>
          </div>
          <Link className="landing-cta" href="/search">
            Inspect the corpus
          </Link>
        </section>

        <section className="landing-section landing-statement">
          <h2>Regulation is one of the largest opaque markets in the economy.</h2>
        </section>

        <section className="landing-section landing-pillars" aria-label="Geode pillars">
          {pillars.map((pillar) => (
            <article className="landing-pillar" key={pillar.name}>
              <h2>{pillar.name}</h2>
              <p>{pillar.description}</p>
            </article>
          ))}
        </section>

        <section className="landing-section landing-index" aria-label="Live data anchor">
          <p className="landing-kicker">Geode Colorado Index</p>
          <div className="landing-index-line">
            <span>{entities.length} live objects</span>
            <span>
              {agencies.length} {agencies.length === 1 ? "agency" : "agencies"} tracked
            </span>
            <span>{timelineEvents.length} dated events</span>
          </div>
          <p>Updated {formatDate(latestUpdate)}</p>
        </section>

        <section className="landing-section landing-press" aria-label="Validation sources">
          <p className="landing-kicker">Validated against</p>
          <div>
            {validationSources.map((source) => (
              <span key={source}>{source}</span>
            ))}
          </div>
        </section>

        <section className="landing-section landing-close">
          <h2>The regulatory economy is here. Geode makes it legible.</h2>
          <Link className="landing-cta" href="/search">
            Inspect the corpus
          </Link>
        </section>
      </main>
    </div>
  );
}
