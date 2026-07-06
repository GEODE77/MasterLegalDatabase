"use client";

import { useCallback, useEffect, useState } from "react";

export type RecentItem = {
  detail?: string;
  href: string;
  id: string;
  label: string;
};

export const RECENT_QUERIES_KEY = "geode.recent.queries";
export const RECENT_THREADS_KEY = "geode.recent.threads";
export const RECENT_REGULATIONS_KEY = "geode.recent.regulations";

const RECENT_EVENT = "geode:recent-items";

export function useRecentItems(key: string, limit = 5): {
  addItem: (item: RecentItem) => void;
  items: RecentItem[];
} {
  const [items, setItems] = useState<RecentItem[]>([]);

  useEffect(() => {
    setItems(readRecentItems(key));

    function syncItems(event: Event): void {
      const detail = (event as CustomEvent<{ key: string }>).detail;

      if (!detail || detail.key === key) {
        setItems(readRecentItems(key));
      }
    }

    window.addEventListener(RECENT_EVENT, syncItems);
    window.addEventListener("storage", syncItems);
    return () => {
      window.removeEventListener(RECENT_EVENT, syncItems);
      window.removeEventListener("storage", syncItems);
    };
  }, [key]);

  const addItem = useCallback(
    (item: RecentItem): void => {
      const next = [
        item,
        ...readRecentItems(key).filter((current) => current.id !== item.id),
      ].slice(0, limit);

      window.localStorage.setItem(key, JSON.stringify(next));
      setItems(next);
      window.dispatchEvent(new CustomEvent(RECENT_EVENT, { detail: { key } }));
    },
    [key, limit],
  );

  return { addItem, items };
}

export function readRecentItems(key: string): RecentItem[] {
  if (typeof window === "undefined") {
    return [];
  }

  const raw = window.localStorage.getItem(key);

  if (!raw) {
    return [];
  }

  try {
    const parsed = JSON.parse(raw) as RecentItem[];
    return Array.isArray(parsed)
      ? parsed.filter(isRecentItem)
      : [];
  } catch {
    return [];
  }
}

function isRecentItem(value: RecentItem): value is RecentItem {
  return Boolean(
    value
      && typeof value.id === "string"
      && typeof value.href === "string"
      && typeof value.label === "string",
  );
}
