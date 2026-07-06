"use client";

import { useEffect, useRef, type ReactElement, type UIEvent } from "react";

import { usePersonalization } from "@/hooks/usePersonalization";
import type { RegulationSearchResult } from "@/lib/search/types";

type RegulationDetailProps = {
  result: RegulationSearchResult | null;
  onClose: () => void;
};

export function RegulationDetail({ result, onClose }: RegulationDetailProps): ReactElement | null {
  const { logEvent } = usePersonalization();
  const hasLoggedFullRead = useRef(false);

  useEffect(() => {
    hasLoggedFullRead.current = false;
  }, [result?.id]);

  useEffect(() => {
    if (!result) {
      return;
    }

    function closeOnEscape(event: KeyboardEvent): void {
      if (event.key === "Escape") {
        onClose();
      }
    }

    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [onClose, result]);

  if (!result) {
    return null;
  }

  function handleReadProgress(event: UIEvent<HTMLDivElement>): void {
    if (!result) {
      return;
    }

    const element = event.currentTarget;
    const scrollable = Math.max(1, element.scrollHeight - element.clientHeight);
    const depth = element.scrollTop / scrollable;

    if (depth >= 0.7 && !hasLoggedFullRead.current) {
      hasLoggedFullRead.current = true;
      logEvent("regulation_read_full", {
        citation: result.citation,
        resultId: result.id,
        title: result.title,
      });
    }
  }

  return (
    <aside className="query-detail" aria-label="Regulation detail">
      <div className="query-detail-panel">
        <div className="query-detail-header">
          <div>
            <p className="query-detail-citation">{result.citation}</p>
            <h2>{result.title}</h2>
            <p className="query-detail-excerpt">{result.excerpt}</p>
          </div>
          <button className="query-detail-close" onClick={onClose} type="button">
            Close
          </button>
        </div>
        <div className="query-detail-body" onScroll={handleReadProgress}>{result.body}</div>
        {result.sourceUrl ? (
          <a className="query-detail-source" href={result.sourceUrl} rel="noreferrer" target="_blank">
            View official source
          </a>
        ) : null}
      </div>
    </aside>
  );
}
