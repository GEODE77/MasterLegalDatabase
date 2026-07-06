"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect, useMemo, useState, type KeyboardEvent, type ReactElement } from "react";

import {
  RECENT_QUERIES_KEY,
  RECENT_REGULATIONS_KEY,
  RECENT_THREADS_KEY,
  useRecentItems,
  type RecentItem,
} from "@/hooks/useRecentItems";

type CommandAction = {
  detail: string;
  href?: string;
  id: string;
  keywords: string[];
  label: string;
  run?: () => void;
  shortcut?: string;
};

export function CommandPalette(): ReactElement {
  const pathname = usePathname();
  const router = useRouter();
  const [isOpen, setIsOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [activeIndex, setActiveIndex] = useState(0);
  const { items: recentQueries } = useRecentItems(RECENT_QUERIES_KEY);
  const { items: recentThreads } = useRecentItems(RECENT_THREADS_KEY);
  const { items: recentRegulations } = useRecentItems(RECENT_REGULATIONS_KEY);

  const actions = useMemo(
    () => buildActions({
      focusQuery: () => focusQuery(router, pathname),
      openSettings: () => router.push("/settings"),
      startThread: () => startThread(router, pathname),
    }),
    [pathname, router],
  );
  const recentActions = useMemo(
    () => [
      ...recentQueries.map((item) => recentToAction(item, "Recent query")),
      ...recentThreads.map((item) => recentToAction(item, "Recent thread")),
      ...recentRegulations.map((item) => recentToAction(item, "Recent regulation")),
    ],
    [recentQueries, recentRegulations, recentThreads],
  );
  const results = useMemo(() => {
    const allActions = [...actions, ...recentActions];
    const normalizedQuery = query.trim().toLowerCase();

    if (!normalizedQuery) {
      return allActions;
    }

    return allActions
      .map((action) => ({ action, score: fuzzyScore(action, normalizedQuery) }))
      .filter((result) => result.score > 0)
      .sort((a, b) => b.score - a.score)
      .map((result) => result.action);
  }, [actions, query, recentActions]);

  useEffect(() => {
    setActiveIndex(0);
  }, [query, isOpen]);

  useEffect(() => {
    function handleShortcut(event: globalThis.KeyboardEvent): void {
      const hasCommand = event.metaKey || event.ctrlKey;

      if (!hasCommand) {
        if (event.key === "Escape" && isOpen) {
          setIsOpen(false);
        }
        return;
      }

      const key = event.key.toLowerCase();

      if (key === "k") {
        event.preventDefault();
        setIsOpen(true);
        return;
      }

      if (key === "n") {
        event.preventDefault();
        startThread(router, pathname);
        return;
      }

      if (event.key === "/") {
        event.preventDefault();
        focusQuery(router, pathname);
        return;
      }

      if (key === ",") {
        event.preventDefault();
        router.push("/settings");
      }
    }

    window.addEventListener("keydown", handleShortcut);
    return () => window.removeEventListener("keydown", handleShortcut);
  }, [isOpen, pathname, router]);

  function runAction(action: CommandAction): void {
    setIsOpen(false);
    setQuery("");

    if (action.run) {
      action.run();
      return;
    }

    if (action.href) {
      router.push(action.href);
    }
  }

  function handleKeyDown(event: KeyboardEvent<HTMLInputElement>): void {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setActiveIndex((current) => (current + 1) % Math.max(results.length, 1));
      return;
    }

    if (event.key === "ArrowUp") {
      event.preventDefault();
      setActiveIndex((current) => (current - 1 + Math.max(results.length, 1)) % Math.max(results.length, 1));
      return;
    }

    if (event.key === "Enter") {
      event.preventDefault();
      const action = results[activeIndex];

      if (action) {
        runAction(action);
      }
      return;
    }

    if (event.key === "Escape") {
      event.preventDefault();
      setIsOpen(false);
    }
  }

  return (
    <>
      <button
        aria-label="Open command palette"
        className="command-palette-trigger"
        data-tooltip="Open command palette (Cmd+K)"
        onClick={() => setIsOpen(true)}
        title="Open command palette (Cmd+K)"
        type="button"
      >
        <span>Command</span>
        <kbd>Cmd K</kbd>
      </button>

      {isOpen ? (
        <div className="command-palette-backdrop" role="presentation" onMouseDown={() => setIsOpen(false)}>
          <section
            aria-label="Command palette"
            aria-modal="true"
            className="command-palette"
            onMouseDown={(event) => event.stopPropagation()}
            role="dialog"
          >
            <label htmlFor="command-palette-input">Command</label>
            <input
              autoFocus
              id="command-palette-input"
              onChange={(event) => setQuery(event.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Type an action, thread, query, or regulation"
              value={query}
            />
            <div className="command-palette-list" role="listbox">
              {results.length > 0 ? (
                results.map((action, index) => (
                  <button
                    aria-selected={index === activeIndex}
                    className={index === activeIndex ? "is-active" : ""}
                    key={action.id}
                    onClick={() => runAction(action)}
                    role="option"
                    type="button"
                  >
                    <span>
                      <strong>{action.label}</strong>
                      <small>{action.detail}</small>
                    </span>
                    {action.shortcut ? <kbd>{action.shortcut}</kbd> : null}
                  </button>
                ))
              ) : (
                <p>No command found. Try Forum, Query, Regulations, or Settings.</p>
              )}
            </div>
          </section>
        </div>
      ) : null}
    </>
  );
}

export function ShortcutHint({ children, shortcut }: { children: string; shortcut: string }): ReactElement {
  return (
    <span className="shortcut-hint">
      {children}
      <kbd>{shortcut}</kbd>
    </span>
  );
}

function buildActions({
  focusQuery,
  openSettings,
  startThread,
}: {
  focusQuery: () => void;
  openSettings: () => void;
  startThread: () => void;
}): CommandAction[] {
  return [
    {
      detail: "Open the forum index.",
      href: "/forum",
      id: "open-forum",
      keywords: ["forum", "threads", "discussion"],
      label: "Open the forum",
    },
    {
      detail: "Write a public regulatory question.",
      id: "start-thread",
      keywords: ["new", "thread", "forum", "compose"],
      label: "Start a thread",
      run: startThread,
      shortcut: "Cmd N",
    },
    {
      detail: "Focus the cited research prompt.",
      id: "ask-question",
      keywords: ["query", "ask", "question", "search"],
      label: "Ask a question",
      run: focusQuery,
      shortcut: "Cmd /",
    },
    {
      detail: "Open the regulation index.",
      href: "/regulations",
      id: "review-regulations",
      keywords: ["regulations", "rules", "citations"],
      label: "Review regulations",
    },
    {
      detail: "Return to current signals and workflows.",
      href: "/app/dashboard",
      id: "open-dashboard",
      keywords: ["dashboard", "home", "activity"],
      label: "Open dashboard",
    },
    {
      detail: "Jump to recent work and profile signals.",
      href: "/app/dashboard#recent-activity",
      id: "review-activity",
      keywords: ["activity", "recent", "history"],
      label: "Review activity",
    },
    {
      detail: "Open profile, notifications, and data controls.",
      id: "open-settings",
      keywords: ["settings", "preferences", "profile"],
      label: "Open settings",
      run: openSettings,
      shortcut: "Cmd ,",
    },
    {
      detail: "Read security, privacy, and data handling.",
      href: "/trust",
      id: "open-trust",
      keywords: ["trust", "security", "privacy"],
      label: "Open trust center",
    },
    {
      detail: "Read who is behind Geode.",
      href: "/about",
      id: "open-about",
      keywords: ["about", "team", "contact"],
      label: "Open about",
    },
    {
      detail: "Open the path to purchase.",
      href: "/pricing",
      id: "open-pricing",
      keywords: ["pricing", "sales", "buy"],
      label: "Open pricing",
    },
  ];
}

function focusQuery(router: ReturnType<typeof useRouter>, pathname: string): void {
  if (pathname.startsWith("/query")) {
    window.dispatchEvent(new CustomEvent("geode:focus-query"));
    return;
  }

  window.sessionStorage.setItem("geode.pendingFocusQuery", "true");
  router.push("/query");
}

function startThread(router: ReturnType<typeof useRouter>, pathname: string): void {
  if (pathname.startsWith("/forum")) {
    window.dispatchEvent(new CustomEvent("geode:start-thread"));
    return;
  }

  window.sessionStorage.setItem("geode.pendingStartThread", "true");
  router.push("/forum");
}

function recentToAction(item: RecentItem, detail: string): CommandAction {
  return {
    detail: item.detail || detail,
    href: item.href,
    id: `${detail}-${item.id}`,
    keywords: [item.label, item.detail ?? detail],
    label: item.label,
  };
}

function fuzzyScore(action: CommandAction, query: string): number {
  const haystack = `${action.label} ${action.detail} ${action.keywords.join(" ")}`.toLowerCase();

  if (haystack.includes(query)) {
    return query.length + 20;
  }

  let score = 0;
  let cursor = 0;

  for (const character of query) {
    const index = haystack.indexOf(character, cursor);

    if (index === -1) {
      return 0;
    }

    score += index === cursor ? 2 : 1;
    cursor = index + 1;
  }

  return score;
}
