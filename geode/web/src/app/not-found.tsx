import Link from "next/link";
import type { ReactElement } from "react";

export default function NotFound(): ReactElement {
  return (
    <main className="app-product-page not-found-page">
      <section className="app-hero compact">
        <p>Page Not Found</p>
        <h2>This route is not part of the current Geode surface.</h2>
        <span>
          Return to a known product area before continuing review or source-backed research.
        </span>
        <div className="hero-actions">
          <Link className="primary-action" href="/query">
            Search public resources
          </Link>
          <Link className="secondary-action" href="/manager/dashboard">
            Manager workspace
          </Link>
        </div>
      </section>
    </main>
  );
}
