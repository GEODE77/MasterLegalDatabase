"use client";

import { useEffect, useState, type ReactElement } from "react";

import { NewThreadComposer } from "@/components/forum/NewThreadComposer";
import { ThreadRow } from "@/components/forum/ThreadRow";
import { PublicNav } from "@/components/navigation/PublicNav";
import { RECENT_THREADS_KEY, useRecentItems } from "@/hooks/useRecentItems";
import type { ForumSort, ForumThreadSummary } from "@/lib/forum/types";

type ForumStats = {
  activeActions?: number;
  activeNow?: number;
  billActions?: number;
  memberCount?: number;
  needsReview?: number;
  openIssues?: number;
  petitions?: number;
  riskItems?: number;
  rulemakingActions?: number;
  sourceLinked?: number;
};

type ForumFilter = {
  description: string;
  key: ForumSort;
  label: string;
};

const SORTS: ForumFilter[] = [
  { description: "Live issues with current action paths.", key: "active", label: "Active" },
  { description: "Public support or signature efforts.", key: "petitions", label: "Petitions" },
  { description: "Support, oppose, or monitor legislation.", key: "bills", label: "Bills" },
  { description: "Open agency rulemaking comment work.", key: "rulemaking", label: "Rulemaking" },
  { description: "Board-level or operating risk.", key: "risk", label: "Risk" },
  { description: "Items that need a source or expert review.", key: "needs-review", label: "Needs review" },
];
const FORUM_POLL_MS = 30_000;

export function ForumFeed(): ReactElement {
  const [isComposerOpen, setIsComposerOpen] = useState(false);
  const [sort, setSort] = useState<ForumSort>("active");
  const [threads, setThreads] = useState<ForumThreadSummary[]>([]);
  const [stats, setStats] = useState<ForumStats>({});
  const [isLoading, setIsLoading] = useState(true);
  const [threadSearch, setThreadSearch] = useState("");
  const { addItem: addRecentThread, items: recentThreads } = useRecentItems(RECENT_THREADS_KEY);
  const visibleThreads = threadSearch.trim()
    ? threads.filter((thread) => matchesThread(thread, threadSearch))
    : threads;

  useEffect(() => {
    void loadThreads(sort);
  }, [sort]);

  useEffect(() => {
    const interval = window.setInterval(() => {
      void loadThreads(sort, { quiet: true });
    }, FORUM_POLL_MS);

    return () => window.clearInterval(interval);
  }, [sort]);

  useEffect(() => {
    if (!isComposerOpen) {
      return;
    }

    function closeOnEscape(event: KeyboardEvent): void {
      if (event.key === "Escape") {
        setIsComposerOpen(false);
      }
    }

    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [isComposerOpen]);

  useEffect(() => {
    function openComposer(): void {
      setIsComposerOpen(true);
    }

    window.addEventListener("geode:start-thread", openComposer);

    if (window.sessionStorage.getItem("geode.pendingStartThread") === "true") {
      window.sessionStorage.removeItem("geode.pendingStartThread");
      window.setTimeout(openComposer, 80);
    }

    return () => window.removeEventListener("geode:start-thread", openComposer);
  }, []);

  async function loadThreads(nextSort: ForumSort, options?: { quiet?: boolean }): Promise<void> {
    if (!options?.quiet) {
      setIsLoading(true);
    }

    const response = await fetch(`/api/forum?sort=${nextSort}`, { cache: "no-store" });
    const data = (await response.json()) as {
      stats?: ForumStats;
      threads: ForumThreadSummary[];
    };

    setThreads(data.threads);
    setStats(data.stats ?? {});

    if (!options?.quiet) {
      setIsLoading(false);
    }
  }

  function handleCreated(): void {
    setSort("active");
    void loadThreads("active");
  }

  const actionCards = [
    {
      count: stats.petitions ?? 0,
      description: "Signature, coalition, and public support efforts.",
      filter: "petitions" as ForumSort,
      label: "Petitions",
    },
    {
      count: stats.billActions ?? 0,
      description: "Bills that need support, opposition, or monitoring.",
      filter: "bills" as ForumSort,
      label: "Bill positions",
    },
    {
      count: stats.rulemakingActions ?? 0,
      description: "Open agency comment and rule review work.",
      filter: "rulemaking" as ForumSort,
      label: "Rulemaking",
    },
    {
      count: stats.riskItems ?? 0,
      description: "Issues that may affect executives, boards, or operations.",
      filter: "risk" as ForumSort,
      label: "Executive risk",
    },
  ];

  const activeFilter = SORTS.find((item) => item.key === sort) ?? SORTS[0];
  const visibleActionCards = actionCards.filter((card) => card.count > 0);

  return (
    <main className="forum-page">
      <PublicNav current="forum" />
      <header className="forum-command public-page-hero">
        <div>
          <p className="forum-section-label">Policy action board</p>
          <h1>Track Colorado legal issues by decision, source, and next action.</h1>
          <span>
            Use this board to find open petitions, bill positions, rulemaking work, and
            executive-level compliance risks.
          </span>
        </div>
        <button
          className="new-thread-button"
          data-tooltip="Create issue (Cmd+N)"
          onClick={() => setIsComposerOpen(true)}
          title="Create issue (Cmd+N)"
          type="button"
        >
          Create issue
        </button>
      </header>

      <section className="forum-status-row" aria-label="Forum summary">
        <span>
          <strong>{stats.openIssues ?? threads.length}</strong>
          Open issues
        </span>
        <span>
          <strong>{stats.activeActions ?? threads.length}</strong>
          Active actions
        </span>
        <span>
          <strong>{stats.needsReview ?? 0}</strong>
          Need review
        </span>
        <span>
          <strong>{stats.sourceLinked ?? 0}</strong>
          Source linked
        </span>
      </section>

      {visibleActionCards.length > 0 ? (
        <section className="forum-action-board" aria-label="Action areas">
          {visibleActionCards.map((card) => (
          <button
            className={sort === card.filter ? "is-active" : ""}
            key={card.label}
            onClick={() => setSort(card.filter)}
            type="button"
          >
            <span>{card.label}</span>
            <strong>{card.count}</strong>
            <small>{card.description}</small>
          </button>
          ))}
        </section>
      ) : null}

      <form className="forum-search" onSubmit={(event) => event.preventDefault()}>
        <label htmlFor="forum-thread-search">Search issue board</label>
        <input
          id="forum-thread-search"
          onChange={(event) => setThreadSearch(event.target.value)}
          placeholder="Search by issue, source, audience, action, author, or tag"
          value={threadSearch}
        />
        {threadSearch.trim().length === 0 && recentThreads.length > 0 ? (
          <div className="recent-inline-list" aria-label="Recent threads">
            {recentThreads.map((item) => (
              <a href={item.href} key={item.id}>
                {item.label}
              </a>
            ))}
          </div>
        ) : null}
      </form>

      <NewThreadComposer
        isOpen={isComposerOpen}
        onClose={() => setIsComposerOpen(false)}
        onCreated={handleCreated}
      />

      <section className="forum-feed" aria-label="Policy issue briefs">
        <div className="forum-feed-header">
          <div>
            <p className="forum-section-label">Issue briefs</p>
            <h2>{activeFilter.label}</h2>
            <span>{activeFilter.description}</span>
          </div>
        </div>
        <nav className="forum-sort-controls" aria-label="Filter issues">
          {SORTS.map((item) => (
            <button
              className={sort === item.key ? "is-active" : ""}
              key={item.key}
              onClick={() => setSort(item.key)}
              type="button"
            >
              {item.label}
            </button>
          ))}
        </nav>
        {isLoading ? <ForumFeedSkeleton /> : null}
        {!isLoading && threads.length === 0 ? (
          <div className="forum-empty recovery-state">
            <span className="recovery-illustration" aria-hidden="true" />
            <p>No issue briefs match this board view yet. Create one when an action needs a record.</p>
            <button onClick={() => setIsComposerOpen(true)} type="button">
              Create issue
            </button>
          </div>
        ) : null}
        {!isLoading && threads.length > 0 && visibleThreads.length === 0 ? (
          <div className="forum-empty compact recovery-state">
            <span className="recovery-illustration" aria-hidden="true" />
            <p>No threads match that search. Clear the field to return to the forum.</p>
            <button onClick={() => setThreadSearch("")} type="button">
              Clear search
            </button>
          </div>
        ) : null}
        {!isLoading
          ? visibleThreads.map((thread) => (
            <ThreadRow
              key={thread.id}
              onOpen={() => addRecentThread({
                detail: `${thread.author} - ${thread.replyCount} replies`,
                href: `/forum/${thread.id}`,
                id: thread.id,
                label: thread.title,
              })}
              thread={thread}
            />
          ))
          : null}
      </section>
    </main>
  );
}

function matchesThread(thread: ForumThreadSummary, query: string): boolean {
  const needle = query.trim().toLowerCase();
  const haystack = [
    thread.title,
    thread.excerpt,
    thread.author,
    thread.actionLabel,
    thread.affectedAudience,
    thread.legalSource,
    thread.issueType,
    thread.status,
    thread.tags.join(" "),
  ].join(" ").toLowerCase();
  return haystack.includes(needle);
}

function ForumFeedSkeleton(): ReactElement {
  return (
    <div className="forum-skeleton" aria-hidden="true">
      {Array.from({ length: 5 }, (_, index) => (
        <div className="thread-row thread-row-skeleton" key={index}>
          <div>
            <span className="skeleton-line skeleton-title" />
            <span className="skeleton-line skeleton-copy" />
          </div>
          <div className="thread-row-meta">
            <span className="skeleton-line skeleton-meta" />
            <span className="skeleton-line skeleton-meta" />
            <span className="skeleton-line skeleton-meta" />
          </div>
        </div>
      ))}
    </div>
  );
}
