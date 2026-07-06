"use client";

import { useEffect, useState, type ReactElement } from "react";

import { NewThreadComposer } from "@/components/forum/NewThreadComposer";
import { ThreadRow } from "@/components/forum/ThreadRow";
import { RECENT_THREADS_KEY, useRecentItems } from "@/hooks/useRecentItems";
import type { ForumSort, ForumThreadSummary } from "@/lib/forum/types";

const SORTS: ForumSort[] = ["hot", "new", "top", "unanswered"];
const FORUM_POLL_MS = 30_000;
const SORT_LABELS: Record<ForumSort, string> = {
  hot: "Hot",
  new: "New",
  top: "Top",
  unanswered: "Unanswered",
};

export function ForumFeed(): ReactElement {
  const [isComposerOpen, setIsComposerOpen] = useState(false);
  const [sort, setSort] = useState<ForumSort>("hot");
  const [threads, setThreads] = useState<ForumThreadSummary[]>([]);
  const [activeNow, setActiveNow] = useState(47);
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
      stats?: { activeNow?: number; memberCount?: number };
      threads: ForumThreadSummary[];
    };

    setThreads(data.threads);
    setActiveNow(data.stats?.activeNow ?? data.stats?.memberCount ?? 47);

    if (!options?.quiet) {
      setIsLoading(false);
    }
  }

  function handleCreated(): void {
    setSort("new");
    void loadThreads("new");
  }

  return (
    <main className="forum-page">
      <header className="forum-header">
        <div>
          <p className="forum-section-label">Forum</p>
          <nav className="forum-sort-controls" aria-label="Sort threads">
            {SORTS.map((item) => (
              <button
                className={sort === item ? "is-active" : ""}
                key={item}
                onClick={() => setSort(item)}
                type="button"
              >
                {SORT_LABELS[item]}
              </button>
            ))}
          </nav>
        </div>
        <span className="forum-active-count">{activeNow.toLocaleString("en-US")} active now</span>
        <button
          className="new-thread-button"
          data-tooltip="Start a thread (Cmd+N)"
          onClick={() => setIsComposerOpen(true)}
          title="Start a thread (Cmd+N)"
          type="button"
        >
          Start a thread
        </button>
      </header>

      <form className="forum-search" onSubmit={(event) => event.preventDefault()}>
        <label htmlFor="forum-thread-search">Search threads</label>
        <input
          id="forum-thread-search"
          onChange={(event) => setThreadSearch(event.target.value)}
          placeholder="Search by title, author, or tag"
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

      <section className="forum-feed" aria-label="Forum threads">
        {isLoading ? <ForumFeedSkeleton /> : null}
        {!isLoading && threads.length === 0 ? (
          <div className="forum-empty recovery-state">
            <span className="recovery-illustration" aria-hidden="true" />
            <p>No threads in your feed yet. Follow some tags to get started.</p>
            <button onClick={() => setIsComposerOpen(true)} type="button">
              Browse tags
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
                detail: `${thread.author} · ${thread.replyCount} replies`,
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
  const haystack = `${thread.title} ${thread.excerpt} ${thread.author} ${thread.tags.join(" ")}`.toLowerCase();
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
