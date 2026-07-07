import type { ReactElement } from "react";

import { PublicNav } from "@/components/navigation/PublicNav";

const TEAM = [
  {
    context: "Building the regulatory intelligence corpus, product surface, and executive workflow system.",
    name: "JP Pfeifer",
    role: "Founder",
  },
];

const INVESTORS_AND_ADVISORS: string[] = [];

export default function AboutPage(): ReactElement {
  return (
    <main className="about-page">
      <PublicNav current="about" />
      <article className="about-document">
        <header className="about-hero public-page-hero">
          <p>About Geode</p>
          <h1>Geode exists to make Colorado regulation legible to the people who must act on it.</h1>
        </header>

        <section className="about-section" aria-labelledby="about-team">
          <h2 id="about-team">Team</h2>
          <div>
            {TEAM.map((member) => (
              <div className="about-row" key={member.name}>
                <span>{member.name}</span>
                <p>
                  <strong>{member.role}</strong>
                  {member.context}
                </p>
              </div>
            ))}
          </div>
        </section>

        <section className="about-section" aria-labelledby="about-investors">
          <h2 id="about-investors">Investors and advisors</h2>
          {INVESTORS_AND_ADVISORS.length > 0 ? (
            <div className="about-entity-row">
              {INVESTORS_AND_ADVISORS.map((entity) => (
                <span key={entity}>{entity}</span>
              ))}
            </div>
          ) : (
            <div className="about-empty recovery-state">
              <span className="recovery-illustration" aria-hidden="true" />
              <p>No investors or advisors are publicly listed yet. Contact Geode to start that conversation.</p>
              <a href="mailto:contact@geode.local">Contact Geode</a>
            </div>
          )}
        </section>

        <section className="about-section" aria-labelledby="about-contact">
          <h2 id="about-contact">Contact</h2>
          <div className="about-row">
            <span>Email</span>
            <a href="mailto:contact@geode.local">contact@geode.local</a>
          </div>
        </section>
      </article>
    </main>
  );
}
