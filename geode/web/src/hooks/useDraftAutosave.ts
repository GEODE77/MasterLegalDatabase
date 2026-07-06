"use client";

import { useEffect, useState } from "react";

const DRAFT_SAVE_MS = 5_000;

export function useDraftAutosave(key: string, value: unknown): string {
  const [savedAt, setSavedAt] = useState("");

  useEffect(() => {
    const serialized = JSON.stringify(value);

    function saveDraft(): void {
      window.localStorage.setItem(key, serialized);
      setSavedAt(formatDraftTime(new Date()));
    }

    const timer = window.setInterval(saveDraft, DRAFT_SAVE_MS);
    return () => window.clearInterval(timer);
  }, [key, value]);

  return savedAt;
}

export function readDraft<T>(key: string, fallback: T): T {
  if (typeof window === "undefined") {
    return fallback;
  }

  const raw = window.localStorage.getItem(key);

  if (!raw) {
    return fallback;
  }

  try {
    return JSON.parse(raw) as T;
  } catch {
    return fallback;
  }
}

function formatDraftTime(value: Date): string {
  return new Intl.DateTimeFormat("en-US", {
    hour: "2-digit",
    hour12: false,
    minute: "2-digit",
    timeZone: "America/Denver",
  }).format(value);
}
