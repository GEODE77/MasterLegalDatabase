import type { ReactElement } from "react";

import { PublicNav } from "@/components/navigation/PublicNav";

const SECURITY_PRACTICES = [
  {
    label: "Encryption",
    text: "Geode is designed to run over HTTPS in production; local development data remains in the workspace filesystem.",
  },
  {
    label: "Access control",
    text: "User identity is scoped through the existing Geode user id and personalization profile boundary.",
  },
  {
    label: "Audit logging",
    text: "The product records limited behavior events for personalization and keeps query content out of that profile.",
  },
  {
    label: "Infrastructure",
    text: "The application is organized around isolated frontend routes, API handlers, and read-only legal source layers.",
  },
];

const DATA_HANDLING = [
  {
    label: "Uploaded files",
    text: "Uploaded onboarding files are parsed for inference and are not written to the local corpus by the parsing route.",
  },
  {
    label: "Queries",
    text: "Questions are used to search the regulation index and stream results; full query text is not stored in the personalization file.",
  },
  {
    label: "Retention",
    text: "Personalization data is retained in the local user profile until the user clears it or calls the deletion endpoint.",
  },
  {
    label: "Disposal",
    text: "Deleting personalization removes the stored profile file and clears the personalization cookie.",
  },
];

const COMPLIANCE = [
  {
    label: "SOC 2",
    text: "Planned. No report is available yet.",
  },
  {
    label: "ISO 27001",
    text: "Planned. No certificate is available yet.",
  },
  {
    label: "Security review",
    text: "Planned. Independent assessment will be listed here when complete.",
  },
];

export default function TrustPage(): ReactElement {
  return (
    <main className="trust-page">
      <PublicNav current="trust" />
      <article className="trust-document">
        <header className="trust-hero public-page-hero">
          <h1>Geode treats regulatory intelligence as sensitive infrastructure.</h1>
          <p>Security, privacy, and data handling are documented here so executive and legal teams can review the product posture before adoption.</p>
        </header>

        <TrustSection title="Security posture" rows={SECURITY_PRACTICES} />
        <TrustSection title="Data handling" rows={DATA_HANDLING} />

        <section className="trust-section" aria-labelledby="trust-privacy">
          <h2 id="trust-privacy">Privacy</h2>
          <div className="trust-row" id="privacy-policy">
            <span>Privacy policy</span>
            <a href="#privacy-policy">Current privacy posture</a>
          </div>
          <div className="trust-row" id="terms-of-service">
            <span>Terms of service</span>
            <a href="#terms-of-service">Current terms posture</a>
          </div>
          <div className="trust-row" id="data-deletion">
            <span>Data deletion endpoint</span>
            <a href="/api/personalization">DELETE /api/personalization</a>
          </div>
        </section>

        <TrustSection title="Audit and compliance" rows={COMPLIANCE} />

        <section className="trust-section trust-contact" aria-labelledby="trust-contact">
          <h2 id="trust-contact">Contact</h2>
          <div className="trust-row">
            <span>Security inquiries</span>
            <a href="mailto:security@geode.local">security@geode.local</a>
          </div>
        </section>
      </article>
    </main>
  );
}

function TrustSection({
  rows,
  title,
}: {
  rows: Array<{ label: string; text: string }>;
  title: string;
}): ReactElement {
  return (
    <section className="trust-section" aria-labelledby={`trust-${slug(title)}`}>
      <h2 id={`trust-${slug(title)}`}>{title}</h2>
      <div>
        {rows.map((row) => (
          <div className="trust-row" key={row.label}>
            <span>{row.label}</span>
            <p>{row.text}</p>
          </div>
        ))}
      </div>
    </section>
  );
}

function slug(value: string): string {
  return value.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "");
}
