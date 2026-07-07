"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  useMemo,
  useState,
  type FormEvent,
  type ReactElement,
  type ReactNode,
} from "react";

import { CommandPalette } from "@/components/navigation/CommandPalette";
import { usePersonalization } from "@/hooks/usePersonalization";

type ProductChromeProps = {
  children: ReactNode;
};

type Destination = {
  href: string;
  icon: string;
  key: string;
  label: string;
};

type PageMeta = {
  action?: { href: string; label: string };
  description?: string;
  title: string;
};

const EXEMPT_ROUTES = [
  "/",
  "/about",
  "/pricing",
  "/trust",
  "/library",
  "/sign-in",
  "/onboarding",
  "/query",
  "/regulations",
  "/authorities",
  "/forum",
  "/manager/verify",
];

const DESTINATIONS: Destination[] = [
  { href: "/manager/dashboard", icon: "home", key: "dashboard", label: "Home" },
  { href: "/manager/sources", icon: "sources", key: "sources", label: "Sources" },
  { href: "/manager/review-queue", icon: "queue", key: "review-queue", label: "Review Queue" },
  { href: "/manager/explore", icon: "search", key: "explore", label: "Explorer" },
  { href: "/manager/relationships", icon: "links", key: "relationships", label: "Relationships" },
  { href: "/manager/timeline", icon: "timeline", key: "timeline", label: "Timeline" },
  { href: "/manager/ask", icon: "ask", key: "ask", label: "Ask Geode" },
  { href: "/manager/publish", icon: "publish", key: "publish", label: "Publish" },
];

const PAGE_META: Record<string, PageMeta> = {
  about: {
    description: "Who is behind Geode.",
    title: "About",
  },
  activity: {
    description: "Recent regulatory work and profile signals.",
    title: "Activity",
  },
  dashboard: {
    action: { href: "/manager/sources", label: "Check sources" },
    description: "Source status, review work, search, relationships, and publication readiness.",
    title: "Manager Home",
  },
  ask: {
    action: { href: "/manager/ask", label: "Ask" },
    description: "Question surface grounded in citations and freshness warnings.",
    title: "Ask Geode",
  },
  "compliance-paths": {
    action: { href: "/manager/compliance-paths", label: "Build path" },
    description: "Source-backed review steps for operational follow-up.",
    title: "Compliance Paths",
  },
  explore: {
    action: { href: "/manager/explore", label: "Browse" },
    description: "Search and browse the legal corpus by layer, citation, agency, and topic.",
    title: "Explorer",
  },
  forum: {
    action: { href: "/forum", label: "Start a thread" },
    description: "Executive regulatory judgment in public record form.",
    title: "Forum",
  },
  internal: {
    description: "Development-only verification surfaces.",
    title: "Heuristics audit",
  },
  impact: {
    action: { href: "/manager/impact", label: "Review impact" },
    description: "Profile-based relevance with evidence and uncertainty.",
    title: "Impact Lens",
  },
  review: {
    action: { href: "/manager/review", label: "Open queue" },
    description: "Needs-review rule units, source evidence, and allowed outcomes.",
    title: "Rule-Unit Review",
  },
  "review-packets": {
    action: { href: "/manager/review-packets", label: "Open packets" },
    description: "Formal review handoff packets for source-backed rule units.",
    title: "Review Packets",
  },
  "reliance-policy": {
    action: { href: "/manager/reliance-policy", label: "Open policy" },
    description: "Reviewer roles, approval criteria, and external-use limits.",
    title: "Reliance Policy",
  },
  "reviewer-operations": {
    action: { href: "/manager/reviewer-operations", label: "Open ops" },
    description: "Reviewer assignment slots and operating instructions.",
    title: "Reviewer Operations",
  },
  pricing: {
    action: { href: "mailto:sales@geode.local", label: "Talk to us" },
    description: "A path to purchase for executive regulatory intelligence.",
    title: "Pricing",
  },
  profiles: {
    description: "Public contribution record and role.",
    title: "Profile",
  },
  query: {
    action: { href: "/query", label: "Ask" },
    description: "Search the corpus and receive a cited research note.",
    title: "Query",
  },
  regulations: {
    description: "Source documents, citations, and related authority.",
    title: "Regulations",
  },
  requirements: {
    action: { href: "/manager/requirements", label: "Search" },
    description: "Operational duties and candidate requirements from the corpus.",
    title: "Requirements",
  },
  relationships: {
    action: { href: "/manager/relationships", label: "Check health" },
    description: "Crosswalks, maps, and connected legal authority.",
    title: "Relationships",
  },
  "review-queue": {
    action: { href: "/manager/review-queue", label: "Open queue" },
    description: "Blocked source files, repair work, and human review.",
    title: "Review Queue",
  },
  settings: {
    description: "Profile, notifications, data, and account controls.",
    title: "Settings",
  },
  system: {
    action: { href: "/manager/system", label: "Check system" },
    description: "Retrieval, freshness, diff, production controls, and remaining work.",
    title: "System Readiness",
  },
  publish: {
    action: { href: "/manager/publish", label: "Check release" },
    description: "Git, safety checks, blockers, and public release readiness.",
    title: "Publish",
  },
  sources: {
    action: { href: "/manager/sources", label: "Check sources" },
    description: "Official source freshness, live probes, and guarded downloads.",
    title: "Sources",
  },
  timeline: {
    action: { href: "/manager/timeline", label: "View timeline" },
    description: "Source checks, downloads, audits, and publication events.",
    title: "Timeline",
  },
  trust: {
    description: "Security, privacy, data handling, and compliance posture.",
    title: "Trust",
  },
  updates: {
    action: { href: "/manager/updates", label: "View updates" },
    description: "Corpus freshness and future regulation change tracking.",
    title: "Updates",
  },
};

export function ProductChrome({ children }: ProductChromeProps): ReactElement {
  const pathname = usePathname();
  const router = useRouter();
  const { profile } = usePersonalization();
  const [collapsed, setCollapsed] = useState(false);
  const [search, setSearch] = useState("");
  const isExempt = EXEMPT_ROUTES.some((route) => pathname === route || pathname.startsWith(`${route}/`));
  const activeKey = routeKey(pathname);
  const meta = pageMeta(pathname);
  const breadcrumbs = useMemo(() => buildBreadcrumbs(pathname, meta.title), [meta.title, pathname]);
  const firstName = firstNameFrom(profile.derived.displayName);

  if (isExempt) {
    return <>{children}</>;
  }

  function submitSearch(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    const query = search.trim();
    router.push(query ? `/manager/explore?q=${encodeURIComponent(query)}` : "/manager/explore");
  }

  function goBack(): void {
    startRouteTransition(() => {
      if (window.history.length > 1) {
        router.back();
        return;
      }

      router.push("/manager/dashboard");
    });
  }

  function startThread(): void {
    if (pathname.startsWith("/forum")) {
      window.dispatchEvent(new CustomEvent("geode:start-thread"));
      return;
    }

    window.sessionStorage.setItem("geode.pendingStartThread", "true");
    router.push("/forum");
  }

  return (
    <div className={collapsed ? "product-shell is-collapsed" : "product-shell"}>
      <CommandPalette />
      <aside className="product-sidebar" aria-label="Primary navigation">
        <div className="product-sidebar-account">
          <span className="product-avatar" aria-hidden="true">
            {profile.derived.initials}
          </span>
          <span className="product-sidebar-account-text">
            <strong>{profile.derived.displayName}</strong>
            <span>Manager workspace</span>
          </span>
        </div>

        <nav className="product-sidebar-nav" aria-label="Primary destinations">
          {DESTINATIONS.map((destination) => (
            <Link
              aria-current={activeKey === destination.key ? "page" : undefined}
              className={activeKey === destination.key ? "is-active" : ""}
              data-tooltip={`Open ${destination.label}`}
              href={destination.href}
              key={destination.key}
              title={`Open ${destination.label}`}
            >
              <span aria-hidden="true" className="product-nav-icon" data-icon={destination.icon} />
              <span>{destination.label}</span>
            </Link>
          ))}
        </nav>

        <button
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          className="product-sidebar-toggle"
          data-tooltip={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          onClick={() => setCollapsed((current) => !current)}
          title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          type="button"
          >
            <span aria-hidden="true" className="product-topbar-icon chevron" data-direction={collapsed ? "right" : "left"} />
            <span>{collapsed ? "Expand" : "Collapse"}</span>
          </button>
      </aside>

      <div className="product-main-frame">
        <header className="product-topbar">
          <button
            aria-label="Go back"
            className="product-back-button"
            data-tooltip="Go back"
            onClick={goBack}
            title="Go back"
            type="button"
          >
            <span aria-hidden="true" className="product-topbar-icon chevron" data-direction="left" />
          </button>

          <nav className="product-breadcrumb" aria-label="Breadcrumb">
            {breadcrumbs.map((crumb, index) => (
              <span key={`${crumb.href}-${crumb.label}`}>
                {index > 0 ? <span aria-hidden="true">/</span> : null}
                <Link aria-current={index === breadcrumbs.length - 1 ? "page" : undefined} href={crumb.href}>
                  {crumb.label}
                </Link>
              </span>
            ))}
          </nav>

          <form className="product-search" data-tooltip="Search Geode (Cmd+K)" onSubmit={submitSearch} title="Search Geode (Cmd+K)">
            <label htmlFor="product-search">Search</label>
            <input
              id="product-search"
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Search Geode"
              value={search}
            />
            <kbd>Cmd K</kbd>
          </form>

          <div className="product-topbar-actions">
            <button aria-label="Notifications" data-tooltip="Notifications" title="Notifications" type="button">
              <span aria-hidden="true" className="product-topbar-icon bell" />
            </button>
            <button aria-label="Help" data-tooltip="Help" title="Help" type="button">
              <span aria-hidden="true" className="product-topbar-icon help" />
            </button>
            <Link
              aria-label="Open settings"
              className="product-topbar-avatar"
              data-tooltip="Open settings (Cmd+,)"
              href="/settings"
              title="Open settings (Cmd+,)"
            >
              {profile.derived.initials}
            </Link>
          </div>
        </header>

        <main className="product-content-shell">
          <header className="product-page-header">
            <div>
              <p>{routeLabel(activeKey)}</p>
              <h1>{activeKey === "dashboard" ? `${localizedGreeting()}, ${firstName}` : meta.title}</h1>
              {meta.description ? <span>{meta.description}</span> : null}
            </div>
            {meta.action?.label === "Start a thread" ? (
              <button
                className="product-page-action"
                data-tooltip="Start a thread (Cmd+N)"
                onClick={startThread}
                title="Start a thread (Cmd+N)"
                type="button"
              >
                {meta.action.label}
              </button>
            ) : meta.action ? (
              <Link
                className="product-page-action"
                data-tooltip={meta.action.label === "Ask" ? "Ask a question (Cmd+/)" : meta.action.label}
                href={meta.action.href}
                title={meta.action.label === "Ask" ? "Ask a question (Cmd+/)" : meta.action.label}
              >
                {meta.action.label}
              </Link>
            ) : null}
          </header>
          {children}
        </main>
      </div>
    </div>
  );
}

function routeKey(pathname: string): string {
  const segments = pathname.split("/").filter(Boolean);
  const segment =
    segments[0] === "app" || segments[0] === "manager"
      ? segments[1] ?? "dashboard"
      : segments[0] ?? "dashboard";

  if (segment === "debug") {
    return "updates";
  }

  if (segment === "internal") {
    return "internal";
  }

  if (segment === "regulations") {
    return "explore";
  }

  return PAGE_META[segment] ? segment : "dashboard";
}

function pageMeta(pathname: string): PageMeta {
  const key = routeKey(pathname);

  if (pathname.startsWith("/forum/")) {
    return {
      action: { href: "/forum", label: "All threads" },
      description: "A single discussion, replies, and voting record.",
      title: "Forum record",
    };
  }

  if (pathname.startsWith("/regulations/")) {
    return {
      description: "A source document with citations, notes, and related authority.",
      title: "Regulation detail",
    };
  }

  return PAGE_META[key] ?? PAGE_META.dashboard;
}

function buildBreadcrumbs(pathname: string, title: string): Array<{ href: string; label: string }> {
  const key = routeKey(pathname);

  if (key === "dashboard") {
    return [{ href: "/manager/dashboard", label: "Manager" }];
  }

  if (key === "internal") {
    return [
      { href: "/manager/dashboard", label: "Manager" },
      { href: pathname, label: title },
    ];
  }

  if (pathname.startsWith("/forum/")) {
    return [
      { href: "/manager/dashboard", label: "Manager" },
      { href: "/forum", label: "Forum" },
      { href: pathname, label: title },
    ];
  }

  if (pathname.startsWith("/regulations/")) {
    return [
      { href: "/manager/dashboard", label: "Manager" },
      { href: "/manager/explore", label: "Explore" },
      { href: pathname, label: title },
    ];
  }

  return [
    { href: "/manager/dashboard", label: "Manager" },
    { href: `/manager/${key}`, label: title },
  ];
}

function firstNameFrom(value: string): string {
  return value.trim().split(/\s+/)[0] || "there";
}

function localizedGreeting(date = new Date()): string {
  const hourText = new Intl.DateTimeFormat("en-US", {
    hour: "numeric",
    hour12: false,
    timeZone: "America/Denver",
  }).format(date);
  const hour = Number(hourText);

  if (hour < 12) {
    return "Good morning";
  }

  if (hour < 17) {
    return "Good afternoon";
  }

  return "Good evening";
}

function routeLabel(key: string): string {
  return PAGE_META[key]?.title ?? "Dashboard";
}

function startRouteTransition(action: () => void): void {
  const viewTransition = (document as Document & {
    startViewTransition?: (callback: () => void) => void;
  }).startViewTransition;

  if (window.matchMedia("(prefers-reduced-motion: reduce)").matches || !viewTransition) {
    action();
    return;
  }

  viewTransition.call(document, action);
}
