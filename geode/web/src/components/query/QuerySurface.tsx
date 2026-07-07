"use client";

import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type FormEvent,
  type KeyboardEvent,
  type ReactElement,
} from "react";

import { PublicNav } from "@/components/navigation/PublicNav";
import { RECENT_QUERIES_KEY, useRecentItems } from "@/hooks/useRecentItems";
import { usePersonalization } from "@/hooks/usePersonalization";
import { useProgressivePrompts } from "@/hooks/useProgressivePrompts";
import type { RegulationSearchResult } from "@/lib/search/types";

type StreamMessage = RegulationSearchResult | { error: string };
type SearchPhase = "idle" | "reading" | "answering" | "complete" | "empty" | "error";

const EXAMPLE_QUESTIONS = [
  "Which Colorado rules should leadership review before expanding a manufacturing line?",
  "What air quality obligations apply before changing production capacity?",
  "Which supplier compliance duties should flow down into operating agreements?",
  "Where do Colorado rules create reporting exposure for a regulated facility?",
];

export function QuerySurface(): ReactElement {
  const [query, setQuery] = useState("");
  const [submittedQuery, setSubmittedQuery] = useState("");
  const [placeholderIndex, setPlaceholderIndex] = useState(0);
  const [results, setResults] = useState<RegulationSearchResult[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [touched, setTouched] = useState(false);
  const [phase, setPhase] = useState<SearchPhase>("idle");
  const [status, setStatus] = useState("");
  const { logEvent, profile } = usePersonalization();
  const { triggerPrompt } = useProgressivePrompts();
  const hasLoadedInitialQuery = useRef(false);
  const queryInputRef = useRef<HTMLTextAreaElement | null>(null);
  const { addItem: addRecentQuery, items: recentQueries } = useRecentItems(RECENT_QUERIES_KEY);
  const primaryInterest = profile.derived.primaryInterest ?? "general compliance";
  const rankedResults = useMemo(
    () => personalizeResults(results, profile.derived.industryVector[0]?.key ?? primaryInterest),
    [primaryInterest, profile.derived.industryVector, results],
  );
  const exampleQuestions = useMemo(() => exampleQuestionsFor(primaryInterest), [primaryInterest]);

  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      return;
    }

    const interval = window.setInterval(() => {
      setPlaceholderIndex((current) => (current + 1) % exampleQuestions.length);
    }, 4200);

    return () => window.clearInterval(interval);
  }, [exampleQuestions.length]);

  const runSearch = useCallback(async (overrideQuery?: string) => {
    const trimmedQuery = (overrideQuery ?? query).trim();

    if (trimmedQuery.length < 3 || isSearching) {
      return;
    }

    setResults([]);
    setSubmittedQuery(trimmedQuery);
    setIsSearching(true);
    setPhase("reading");
    setStatus("We're reading Colorado authority.");
    addRecentQuery({
      detail: "Recent query",
      href: `/query?q=${encodeURIComponent(trimmedQuery)}`,
      id: trimmedQuery.toLowerCase(),
      label: trimmedQuery,
    });
    void logEvent("query_submitted", { queryLength: trimmedQuery.length });

    try {
      let receivedCount = 0;
      const response = await fetch("/api/query", {
        body: JSON.stringify({ query: trimmedQuery }),
        headers: { "Content-Type": "application/json" },
        method: "POST",
      });

      if (!response.ok || !response.body) {
        setPhase("error");
        setStatus("We could not reach the corpus. Ask again with an agency, citation, or operating fact.");
        return;
      }

      await readResultStream(response.body, (message) => {
        if ("error" in message) {
          setPhase("error");
          setStatus("We could not complete the search. Ask again with an agency, citation, or operating fact.");
          return;
        }

        receivedCount += 1;
        setResults((current) => [...current, message]);
        setPhase("answering");
        setStatus("We're writing the note.");
      });

      setPhase(receivedCount > 0 ? "complete" : "empty");
      setStatus(receivedCount > 0 ? "Your note is ready." : "No close match surfaced.");
      void triggerPrompt("first_query_completed");
    } catch {
      setPhase("error");
      setStatus("We could not reach the corpus. Ask again with an agency, citation, or operating fact.");
    } finally {
      setIsSearching(false);
    }
  }, [addRecentQuery, isSearching, logEvent, query, triggerPrompt]);

  useEffect(() => {
    function focusQuery(): void {
      queryInputRef.current?.focus();
    }

    window.addEventListener("geode:focus-query", focusQuery);

    const initialQuery = new URLSearchParams(window.location.search).get("q");
    const shouldFocus = window.sessionStorage.getItem("geode.pendingFocusQuery") === "true";

    if (shouldFocus) {
      window.sessionStorage.removeItem("geode.pendingFocusQuery");
      window.setTimeout(focusQuery, 80);
    }

    if (!hasLoadedInitialQuery.current && initialQuery && initialQuery.trim().length >= 3) {
      hasLoadedInitialQuery.current = true;
      setQuery(initialQuery);
      void runSearch(initialQuery);
    }

    return () => window.removeEventListener("geode:focus-query", focusQuery);
  }, [runSearch]);

  function handleSubmit(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    setTouched(true);
    void runSearch();
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>): void {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void runSearch();
    }
  }

  return (
    <main className={phase === "idle" ? "query-page is-idle" : "query-page has-answer"}>
      <PublicNav current="query" />
      <form className="query-form" onSubmit={handleSubmit}>
        <label className="query-field" htmlFor="regulation-query">
          <span className="query-field-label">Ask a question</span>
          <textarea
            aria-describedby="query-validation"
            aria-invalid={touched && query.trim().length > 0 && query.trim().length < 3}
            aria-label="Ask a question"
            id="regulation-query"
            onBlur={() => setTouched(true)}
            onChange={(event) => setQuery(event.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={exampleQuestions[placeholderIndex]}
            ref={queryInputRef}
            rows={phase === "idle" ? 2 : 1}
            value={query}
          />
        </label>
        <button
          aria-label="Submit question"
          className="query-submit query-submit-hidden"
          disabled={isSearching || query.trim().length < 3}
          type="submit"
        >
          {isSearching ? "Reading" : "Ask"}
        </button>
        {touched && query.trim().length > 0 && query.trim().length < 3 ? (
          <span className="field-validation is-error" id="query-validation">
            Ask with at least three characters.
          </span>
        ) : null}
        {phase === "idle" && query.trim().length === 0 && recentQueries.length > 0 ? (
          <div className="query-recent-list" aria-label="Recent queries">
            {recentQueries.map((item) => (
              <button
                key={item.id}
                onClick={() => {
                  setQuery(item.label);
                  queryInputRef.current?.focus();
                }}
                type="button"
              >
                {item.label}
              </button>
            ))}
          </div>
        ) : null}
      </form>

      {phase !== "idle" ? (
        <section
          aria-busy={isSearching}
          aria-label="Research note"
          aria-live="polite"
          className="query-note"
        >
          {isSearching ? <p className="query-status">{status}</p> : null}
          {isSearching && rankedResults.length === 0 ? (
            <ResearchNoteSkeleton query={submittedQuery} />
          ) : (
            <ResearchNote phase={phase} query={submittedQuery} results={rankedResults} />
          )}
        </section>
      ) : null}
    </main>
  );
}

type PersonalizedResult = RegulationSearchResult & {
  personalized: boolean;
};

type ResearchNoteProps = {
  phase: SearchPhase;
  query: string;
  results: PersonalizedResult[];
};

function ResearchNote({ phase, query, results }: ResearchNoteProps): ReactElement {
  if (phase === "error") {
    return (
      <article className="research-note recovery-state">
        <span className="recovery-illustration" aria-hidden="true" />
        <h1>{query}</h1>
        <p>We could not return a usable answer. Ask again with an agency, citation, or operating fact.</p>
        <a href="/query">Ask another question</a>
      </article>
    );
  }

  if (phase === "empty") {
    return (
      <article className="research-note recovery-state">
        <span className="recovery-illustration" aria-hidden="true" />
        <h1>{query}</h1>
        <p>No close match surfaced in the current index. Name an agency, regulated activity, or citation range.</p>
        <a href="/query">Ask another question</a>
      </article>
    );
  }

  const primary = results[0];
  const secondary = results[1];
  const primaryExcerpt = cleanExcerpt(primary?.excerpt);
  const secondaryExcerpt = cleanExcerpt(secondary?.excerpt);
  const citations = results.slice(0, 5);

  return (
    <article className="research-note">
      <h1>{query}</h1>
      {primary ? (
        <>
          <p>
            Geode reads this first through <span>{primary.citation}</span> in{" "}
            {layerLabel(primary.layer)}, the authority that most closely places the
            question inside {primary.title}
            <CitationMark index={1} result={primary} />. {resultReason(primary)}
          </p>
          <p>
            The useful language begins: <q>{primaryExcerpt}</q>
            <CitationMark index={1} result={primary} />.
            {secondary ? (
              <>
                {" "}The next authority, <span>{secondary.citation}</span> in{" "}
                {layerLabel(secondary.layer)}, defines the adjacent reading
                <CitationMark index={2} result={secondary} />.
              </>
            ) : null}
          </p>
          <p>
            The immediate conclusion is narrow: these sources establish where review
            should begin before the issue becomes an operating decision.
            {secondaryExcerpt ? (
              <>
                {" "}The nearby language begins: <q>{secondaryExcerpt}</q>
                {secondary ? <CitationMark index={2} result={secondary} /> : null}.
              </>
            ) : null}
          </p>
        </>
      ) : (
        <p>We&apos;re reading the index and assembling the authority set.</p>
      )}

      {citations.length > 0 ? (
        <section className="reference-list" aria-label="References">
          <h2>References</h2>
          <ol>
            {citations.map((result) => (
              <li key={result.id}>
                <span>{result.citation}.</span> {layerLabel(result.layer)}.{" "}
                {detailHref(result) ? (
                  <a href={detailHref(result) ?? undefined}>{result.title}</a>
                ) : (
                  <span>{result.title}</span>
                )}
                .{" "}
                <span className="reference-reasons">
                  {result.explanation ?? result.matchReasons?.join(" ") ?? "Matched the local Geode index."}
                  {" "}Freshness: {result.freshnessStatus?.replaceAll("_", " ") ?? "unknown"}.
                  {result.freshnessDetail ? ` ${result.freshnessDetail}` : ""}
                </span>{" "}
                {result.sourceUrl ? <a href={result.sourceUrl}>Official source.</a> : "Source archived in Geode."}
              </li>
            ))}
          </ol>
        </section>
      ) : null}
    </article>
  );
}

function ResearchNoteSkeleton({ query }: { query: string }): ReactElement {
  return (
    <article className="research-note research-note-skeleton" aria-hidden="true">
      <h1>{query}</h1>
      <span className="skeleton-line skeleton-paragraph" />
      <span className="skeleton-line skeleton-paragraph medium" />
      <span className="skeleton-line skeleton-paragraph" />
      <span className="skeleton-line skeleton-paragraph short" />
      <section className="reference-list" aria-label="References">
        <span className="skeleton-line skeleton-meta" />
        <ol>
          <li>
            <span className="skeleton-line skeleton-copy" />
          </li>
          <li>
            <span className="skeleton-line skeleton-copy short" />
          </li>
        </ol>
      </section>
    </article>
  );
}

function CitationMark({ index, result }: { index: number; result: RegulationSearchResult }): ReactElement {
  return (
    <sup className="citation-mark">
      <button type="button" aria-label={`Preview ${result.citation}`}>
        {index}
        <span className="citation-preview">
          <strong>{result.citation}</strong>
          <em>{layerLabel(result.layer)}</em>
          <span>{result.title}</span>
          <small>{cleanExcerpt(result.excerpt)}</small>
          {result.relationshipCount ? <small>{result.relationshipCount} related links</small> : null}
          {result.freshnessStatus ? <small>Freshness: {result.freshnessStatus.replaceAll("_", " ")}</small> : null}
          {result.matchReasons?.length ? <small>{result.matchReasons[0]}</small> : null}
        </span>
      </button>
    </sup>
  );
}

function detailHref(result: RegulationSearchResult): string | null {
  if (result.layer === "01_Statutes_CRS") {
    return `/authorities/${encodeURIComponent(result.id)}`;
  }

  if (result.layer === "02_Regulations_CCR") {
    return `/regulations/${encodeURIComponent(result.id)}`;
  }

  return `/authorities/${encodeURIComponent(result.id)}`;
}

function layerLabel(layer?: string): string {
  if (layer === "01_Statutes_CRS") {
    return "CRS";
  }

  if (layer === "02_Regulations_CCR") {
    return "CCR";
  }

  if (layer === "03_Legislation") {
    return "Legislation";
  }

  if (layer === "04_Rulemaking") {
    return "Rulemaking";
  }

  if (layer === "05_Executive_Orders") {
    return "Executive Orders";
  }

  if (layer === "06_Session_Laws") {
    return "Session Laws";
  }

  if (layer === "07_Supplementary") {
    return "Supplementary";
  }

  return "Geode";
}

function cleanExcerpt(excerpt?: string): string {
  if (!excerpt) {
    return "";
  }

  const normalized = excerpt
    .replace(/^---[\s\S]*?---/u, "")
    .replace(/#+\s*/gu, "")
    .replace(/\s+/gu, " ")
    .trim();

  if (normalized.length <= 260) {
    return normalized;
  }

  return `${normalized.slice(0, 257).trim()}...`;
}

function resultReason(result: RegulationSearchResult): string {
  const reason = result.matchReasons?.[0];

  if (!reason) {
    return "It matched the local Geode index.";
  }

  return reason;
}

function personalizeResults(results: RegulationSearchResult[], interest: string): PersonalizedResult[] {
  const tokens = interestTokens(interest);

  return results
    .map((result) => {
      const text = `${result.title} ${result.excerpt} ${result.body}`.toLowerCase();
      const boost = tokens.some((token) => text.includes(token));

      return {
        ...result,
        personalized: boost,
        score: boost ? result.score + 18 : result.score,
      };
    })
    .sort((a, b) => b.score - a.score);
}

function interestTokens(interest: string): string[] {
  if (interest === "environment") {
    return ["water", "waste", "air", "emission", "discharge", "environment"];
  }

  if (interest === "worker-safety" || interest === "worker safety") {
    return ["worker", "safety", "osha", "exposure", "injury"];
  }

  if (interest === "advanced-ceramics" || interest === "advanced ceramics") {
    return ["ceramic", "silica", "dust", "powder", "kiln"];
  }

  if (interest === "supply-chain" || interest === "supply chain") {
    return ["supplier", "vendor", "procurement", "contract", "materials"];
  }

  return interest.split(/[\s-]+/).filter(Boolean);
}

function exampleQuestionsFor(interest: string): string[] {
  if (interest === "environment") {
    return [
      "Which Colorado environmental rules affect our operations?",
      "What air permitting obligations should we review first?",
      "Where do Colorado rules create reporting exposure for emissions?",
      "Which agency actions should an environmental lead monitor?",
    ];
  }

  if (interest === "worker-safety" || interest === "worker safety") {
    return [
      "Which worker safety obligations should we review first?",
      "What exposure rules apply before changing a production process?",
      "Which Colorado labor requirements matter to facility leadership?",
      "Where should compliance look for safety reporting duties?",
    ];
  }

  return EXAMPLE_QUESTIONS;
}

async function readResultStream(
  body: ReadableStream<Uint8Array>,
  onMessage: (message: StreamMessage) => void,
): Promise<void> {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();

    if (done) {
      break;
    }

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() ?? "";

    for (const line of lines) {
      const trimmedLine = line.trim();

      if (trimmedLine.length > 0) {
        onMessage(JSON.parse(trimmedLine) as StreamMessage);
      }
    }
  }

  if (buffer.trim().length > 0) {
    onMessage(JSON.parse(buffer) as StreamMessage);
  }
}
