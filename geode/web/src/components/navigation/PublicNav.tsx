"use client";

import Link from "next/link";
import type { ReactElement } from "react";

type PublicNavProps = {
  current?: "about" | "forum" | "home" | "library" | "pricing" | "query" | "trust";
};

const PUBLIC_LINKS = [
  { href: "/query", key: "query", label: "Search" },
  { href: "/library", key: "library", label: "Library" },
  { href: "/forum", key: "forum", label: "Forum" },
  { href: "/trust", key: "trust", label: "Trust" },
] as const;

export function PublicNav({ current = "home" }: PublicNavProps): ReactElement {
  return (
    <header className="public-nav" aria-label="Public navigation">
      <Link
        aria-current={current === "home" ? "page" : undefined}
        className="public-nav-brand"
        href="/"
      >
        Geode
      </Link>
      <nav aria-label="Public resources">
        {PUBLIC_LINKS.map((link) => (
          <Link
            aria-current={current === link.key ? "page" : undefined}
            className={current === link.key ? "is-active" : ""}
            href={link.href}
            key={link.key}
          >
            {link.label}
          </Link>
        ))}
      </nav>
      <Link className="public-nav-manager" href="/manager/verify">
        Manager verification
      </Link>
    </header>
  );
}
