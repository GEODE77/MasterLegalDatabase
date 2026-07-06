"use client";

import { useEffect, useState, type ReactElement } from "react";

import type { RegulationSearchResult } from "@/lib/search/types";

type StreamMessage = RegulationSearchResult | { error: string };

const SAMPLE_QUERY = "What Colorado air pollution emissions permit rule should leadership review?";

export function LandingProductSample(): ReactElement {
  const [answer, setAnswer] = useState<RegulationSearchResult | null>(null);
  const [references, setReferences] = useState<RegulationSearchResult[]>([]);
  const [status, setStatus] = useState("We're reading the Colorado corpus.");

  useEffect(() => {
    const controller = new AbortController();

    async function streamSample(): Promise<void> {
      try {
        const response = await fetch("/api/query", {
          body: JSON.stringify({ query: SAMPLE_QUERY }),
          headers: { "Content-Type": "application/json" },
          method: "POST",
          signal: controller.signal,
        });

        if (!response.body) {
          setStatus("We could not render the sample.");
          return;
        }

        await readResultStream(response.body, (message) => {
          if ("error" in message) {
            setStatus("We could not stream the sample answer.");
            return;
          }

          setReferences((current) => {
            const next = [...current, message].slice(0, 3);
            setAnswer(next[0] ?? null);
            return next;
          });
          setStatus("We're streaming the cited answer.");
        });

        setStatus("The cited answer is ready.");
      } catch {
        if (!controller.signal.aborted) {
          setStatus("We could not render the sample.");
        }
      }
    }

    void streamSample();

    return () => controller.abort();
  }, []);

  return (
    <section className="landing-section landing-product-sample" aria-label="Live product sample">
      <p className="landing-sample-label">Live product sample</p>
      <h2>{SAMPLE_QUERY}</h2>
      <article className="landing-sample-answer" aria-live="polite">
        <p className="landing-sample-status">{status}</p>
        {answer ? (
          <>
            <p>
              The first authority to review is <span>{answer.citation}</span>, which places the
              question inside {answer.title.toLowerCase()}
              <sup>1</sup>. The operative language begins around: <q>{cleanExcerpt(answer.excerpt)}</q>
            </p>
            <ol>
              {references.map((reference, index) => (
                <li key={reference.id}>
                  <span>{index + 1}.</span> {reference.citation}. {reference.title}
                </li>
              ))}
            </ol>
          </>
        ) : (
          <LandingSampleSkeleton />
        )}
      </article>
    </section>
  );
}

function LandingSampleSkeleton(): ReactElement {
  return (
    <div className="landing-sample-skeleton" aria-hidden="true">
      <span className="skeleton-line skeleton-paragraph" />
      <span className="skeleton-line skeleton-paragraph medium" />
      <span className="skeleton-line skeleton-paragraph short" />
      <ol>
        <li>
          <span className="skeleton-line skeleton-copy" />
        </li>
        <li>
          <span className="skeleton-line skeleton-copy short" />
        </li>
      </ol>
    </div>
  );
}

function cleanExcerpt(value: string): string {
  return value
    .replace(/#+/g, "")
    .replace(/\bCODE OF COLORADO REGULATIONS\b/gi, "")
    .replace(/\s+/g, " ")
    .trim();
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
