const colorTokens = [
  { name: "Ink", value: "#10110f", className: "token-ink" },
  { name: "Canvas", value: "#f6f6f3", className: "token-bg" },
  { name: "Surface", value: "#fbfbf8", className: "token-surface" },
  { name: "Line", value: "#dadbd5", className: "token-line" },
  { name: "Accent", value: "#746336", className: "token-accent" }
];

const spaceTokens = [
  ["04", "4px"],
  ["08", "8px"],
  ["12", "12px"],
  ["16", "16px"],
  ["24", "24px"],
  ["32", "32px"],
  ["48", "48px"],
  ["72", "72px"],
  ["104", "104px"]
];

const motionTokens = [
  ["Short", "180ms"],
  ["Medium", "360ms"],
  ["Long", "640ms"]
];

export default function TokensPage() {
  return (
    <div className="page token-page">
      <header className="token-hero">
        <p className="eyebrow">Visual foundation</p>
        <h1>Authority before ornament.</h1>
        <p className="token-context">
          Geode now begins with typography, silence, and one restrained signal color.
        </p>
      </header>

      <section className="token-section">
        <h2>Color</h2>
        <div className="token-grid">
          {colorTokens.map((token) => (
            <article className="token-card" key={token.name}>
              <div className={`token-swatch ${token.className}`} />
              <strong>{token.name}</strong>
              <span>{token.value}</span>
            </article>
          ))}
        </div>
      </section>

      <section className="token-section">
        <h2>Type</h2>
        <div className="type-stack">
          <article className="type-specimen">
            <strong>Display</strong>
            <div className="type-display">Colorado law, structured for machines.</div>
          </article>
          <article className="type-specimen">
            <strong>Body</strong>
            <div className="type-body">
              Legal authority is separated from commentary, cross-linked by source, and held in
              formats that agents can inspect without translation.
            </div>
          </article>
          <article className="type-specimen">
            <strong>Metadata</strong>
            <div className="type-meta">CRS-25-7-109 / CURRENT / 0.94 CONFIDENCE</div>
          </article>
        </div>
      </section>

      <section className="token-section">
        <h2>Space</h2>
        <div className="space-rhythm">
          {spaceTokens.map(([label, value]) => (
            <div className="space-row" key={label}>
              <span className="type-meta">{label}</span>
              <div className="space-rule" style={{ width: value }} />
            </div>
          ))}
        </div>
      </section>

      <section className="token-section">
        <h2>Motion</h2>
        <div className="motion-list">
          {motionTokens.map(([label, value]) => (
            <div className="motion-row" key={label}>
              <strong>{label}</strong>
              <div className="motion-line" />
              <span>{value}</span>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
