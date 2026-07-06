import Link from "next/link";
import type { ReactElement } from "react";

export const dynamic = "force-dynamic";

export default function AppSettingsPage(): ReactElement {
  return (
    <main className="app-product-page">
      <section className="app-hero compact">
        <p>Settings</p>
        <h2>Product settings remain connected to the existing workspace controls.</h2>
        <span>
          This route reserves the internal product settings location while preserving the current
          settings page.
        </span>
      </section>

      <section className="app-list-panel">
        <article>
          <span>Current settings</span>
          <strong>Workspace controls</strong>
          <p>The existing settings page remains available during route migration.</p>
          <Link href="/settings">Open current settings</Link>
        </article>
      </section>
    </main>
  );
}
