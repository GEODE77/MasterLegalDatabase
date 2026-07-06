"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef, useState, type DragEvent, type ReactElement } from "react";

import { usePersonalization } from "@/hooks/usePersonalization";
import type { OnboardingAnalysis, OnboardingParseResponse } from "@/lib/onboarding/types";
type Stage = "entry" | "parsing" | "analysis" | "handoff";

const PARSING_LINES = [
  "We're identifying citations.",
  "We're matching Colorado statutes.",
  "We're separating source text from context.",
  "We're inferring industry context.",
  "We're reading the seat this was written for.",
  "We're selecting the first authorities to watch.",
];

const MAX_CLIENT_FILE_SIZE = 4 * 1024 * 1024;

const INDUSTRY_OPTIONS = [
  "advanced ceramics",
  "manufacturing",
  "environment",
  "worker safety",
  "supply chain",
  "energy",
  "general compliance",
];

const JURISDICTION_OPTIONS = ["Colorado", "Colorado and federal", "Federal", "Multistate"];
const PRIMARY_ROLE_OPTIONS = [
  "Compliance",
  "Legal operations",
  "Government affairs",
  "Regulatory intelligence",
];
const SECONDARY_ROLE_OPTIONS = ["Executive", "Operations leader"];
const ROLE_OPTIONS = [...PRIMARY_ROLE_OPTIONS, ...SECONDARY_ROLE_OPTIONS];

export function OnboardingSurface(): ReactElement {
  const router = useRouter();
  const { logEvent, setPreferences } = usePersonalization();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const onboardingStartedAt = useRef<number>(Date.now());
  const analysisStartedAt = useRef<number>(0);
  const [stage, setStage] = useState<Stage>("entry");
  const [isDragging, setIsDragging] = useState(false);
  const [statusIndex, setStatusIndex] = useState(0);
  const [analysis, setAnalysis] = useState<OnboardingAnalysis | null>(null);
  const [industries, setIndustries] = useState<string[]>([]);
  const [jurisdiction, setJurisdiction] = useState("Colorado");
  const [role, setRole] = useState("Compliance");
  const [error, setError] = useState<string | null>(null);
  const [sourceName, setSourceName] = useState("Source");
  const [skipped, setSkipped] = useState(false);

  useEffect(() => {
    logEvent("onboarding_entry_viewed", { surface: "document_drop" });
  }, [logEvent]);

  useEffect(() => {
    if (stage !== "parsing") {
      return;
    }

    const interval = window.setInterval(() => {
      const elapsedSeconds = Math.round((Date.now() - analysisStartedAt.current) / 1000);
      const timedIndex = Math.min(PARSING_LINES.length - 1, Math.floor(elapsedSeconds / 2));
      setStatusIndex((current) => Math.max(current, timedIndex));
    }, 450);

    return () => window.clearInterval(interval);
  }, [stage]);

  async function analyzeFile(file: File): Promise<void> {
    if (file.size > MAX_CLIENT_FILE_SIZE) {
      setError("That file is larger than this first-read surface allows. Paste the relevant pages or enter with defaults.");
      logEvent("onboarding_file_rejected", { fileName: file.name, reason: "size" });
      return;
    }

    const formData = new FormData();
    formData.set("file", file);
    setSourceName(file.name);
    await analyze(formData, { fileName: file.name, fileType: file.type || "unknown", source: "file" });
  }

  async function analyze(body: BodyInit, eventPayload: Record<string, string>): Promise<void> {
    setError(null);
    setStatusIndex(0);
    analysisStartedAt.current = Date.now();
    setStage("parsing");
    logEvent("onboarding_document_started", eventPayload);

    try {
      const controller = new AbortController();
      const timeout = window.setTimeout(() => controller.abort(), 28_000);
      const [response] = await Promise.all([
        fetch("/api/onboarding/parse", {
          body,
          headers: typeof body === "string" ? { "Content-Type": "application/json" } : undefined,
          method: "POST",
          signal: controller.signal,
        }),
        wait(minimumTheatreMs()),
      ]);
      window.clearTimeout(timeout);

      const payload = (await response.json()) as OnboardingParseResponse | { error?: string };

      if (!response.ok || !("analysis" in payload)) {
        const message = "error" in payload ? payload.error : null;
        throw new Error(message ?? "We could not read that source.");
      }

      setAnalysis(payload.analysis);
      setIndustries(payload.analysis.industries);
      setJurisdiction(payload.analysis.jurisdiction);
      setRole(payload.analysis.role);
      setStage("analysis");
      logEvent("onboarding_document_analyzed", {
        industries: payload.analysis.industries.join(", "),
        jurisdiction: payload.analysis.jurisdiction,
        parseSeconds: Math.round((Date.now() - analysisStartedAt.current) / 1000),
        role: payload.analysis.role,
      });
    } catch (caughtError) {
      const message = caughtError instanceof Error && caughtError.name === "AbortError"
        ? "That took longer than expected. Paste the key pages, or skip with defaults and return later."
        : caughtError instanceof Error
          ? caughtError.message
        : "We could not analyze the source. Entering with defaults is still a complete path into Geode.";
      setError(message);
      logEvent("onboarding_parse_failed", {
        message,
        parseSeconds: Math.round((Date.now() - analysisStartedAt.current) / 1000),
      });
      setStage("entry");
    }
  }

  async function confirmSuggestions(): Promise<void> {
    if (!analysis) {
      return;
    }

    await setPreferences({
      answers: [
        { key: "industry", value: industries[0] ?? "general compliance" },
        { key: "industries", value: industries },
        { key: "jurisdiction", value: jurisdiction },
        { key: "role", value: role },
        { key: "documentSummary", sensitivity: "private", value: analysis.summary },
        { key: "modelE.industry", value: "answered_by_onboarding_document" },
        { key: "modelE.jurisdiction", value: "answered_by_onboarding_document" },
        { key: "modelE.role", value: "answered_by_onboarding_document" },
        { key: "onboardingStatus", value: "completed_with_document" },
      ],
    });
    logEvent("onboarding_confirmed", {
      correctedIndustryCount: industries.length,
      jurisdiction,
      role,
      secondsToComplete: Math.round((Date.now() - onboardingStartedAt.current) / 1000),
    });
    setSkipped(false);
    setStage("handoff");
  }

  async function skipOnboarding(): Promise<void> {
    logEvent("onboarding_skipped", {
      path: "document_drop",
      secondsToSkip: Math.round((Date.now() - onboardingStartedAt.current) / 1000),
    });
    await setPreferences({
      answers: [{ key: "onboardingStatus", value: "skipped_without_document" }],
    });
    setSkipped(true);
    setStage("handoff");
  }

  function handleDrop(event: DragEvent<HTMLDivElement>): void {
    event.preventDefault();
    setIsDragging(false);
    const file = event.dataTransfer.files.item(0);

    if (file) {
      void analyzeFile(file);
    }
  }

  return (
    <main className="onboarding-page">
      {stage === "entry" && (
        <section className="onboarding-entry" aria-labelledby="onboarding-title">
          <button className="onboarding-skip" onClick={skipOnboarding} type="button">
            Enter with defaults
          </button>
          <p className="onboarding-kicker">Set up Geode</p>
          <div
            className={isDragging ? "document-drop-zone is-dragging" : "document-drop-zone"}
            onDragEnter={() => {
              setIsDragging(true);
              logEvent("onboarding_drop_zone_engaged", { method: "drag" });
            }}
            onDragLeave={() => setIsDragging(false)}
            onDragOver={(event) => event.preventDefault()}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
            role="button"
            tabIndex={0}
            onKeyDown={(event) => {
              if (event.key === "Enter" || event.key === " ") {
                fileInputRef.current?.click();
              }
            }}
          >
            <input
              accept=".txt,.md,.rtf,.csv,.json,.pdf,.docx"
              className="document-file-input"
              onChange={(event) => {
                const file = event.target.files?.item(0);
                if (file) {
                  void analyzeFile(file);
                }
              }}
              ref={fileInputRef}
              type="file"
            />
            <h1 id="onboarding-title">Drop one source.</h1>
          </div>
          {error ? (
            <div className="onboarding-error recovery-state">
              <span className="recovery-illustration" aria-hidden="true" />
              <p>{error}</p>
              <button onClick={() => void skipOnboarding()} type="button">
                Enter with defaults
              </button>
            </div>
          ) : null}
        </section>
      )}

      {stage === "parsing" && (
        <section className="parsing-stage onboarding-screen-enter" aria-live="polite">
          <p className="onboarding-kicker">Set up Geode</p>
          <span className="activity-dot" aria-hidden="true" />
          <h1>{PARSING_LINES[statusIndex]}</h1>
          <span className="parsing-source">{sourceName}</span>
        </section>
      )}

      {stage === "analysis" && analysis && (
        <section className="onboarding-analysis onboarding-screen-enter" aria-labelledby="analysis-title">
          <p className="onboarding-kicker">Set up Geode</p>
          <h1 id="analysis-title">We formed this initial picture.</h1>
          <div className="analysis-lines">
            <InferenceLine label="Read" value={analysis.summary} />
            <InferenceLine
              label="Industries"
              onToggle={(value) => toggleIndustry(value)}
              options={INDUSTRY_OPTIONS}
              values={industries}
            />
            <InferenceLine
              label="Jurisdiction"
              onToggle={(value) => {
                logEvent("onboarding_suggestion_corrected", { field: "jurisdiction", value });
                setJurisdiction(value);
              }}
              options={JURISDICTION_OPTIONS}
              values={[jurisdiction]}
            />
            <InferenceLine
              label="Seat"
              onToggle={(value) => {
                logEvent("onboarding_suggestion_corrected", { field: "role", value });
                setRole(value);
              }}
              options={ROLE_OPTIONS}
              values={[role]}
            />
            {analysis.relatedRegulations.length > 0 ? (
              <InferenceLine
                label="Watch first"
                value={analysis.relatedRegulations
                  .map((result) => `${result.citation} ${result.title}`)
                  .join("; ")}
              />
            ) : (
              <InferenceLine label="Watch first" value="No close match surfaced yet." />
            )}
          </div>
          <div className="analysis-actions">
            <button className="confirm-analysis" onClick={confirmSuggestions} type="button">
              Confirm this reading
            </button>
          </div>
        </section>
      )}

      {stage === "handoff" && (
        <section className="onboarding-handoff onboarding-screen-enter" aria-labelledby="handoff-title">
          <p className="onboarding-kicker">Set up Geode</p>
          <h1 id="handoff-title">
            {skipped
              ? "You can personalize Geode later in settings."
              : "We have enough context to begin."}
          </h1>
          <button className="confirm-analysis" onClick={() => router.push("/app/dashboard")} type="button">
            Enter Geode
          </button>
        </section>
      )}
    </main>
  );

  function toggleIndustry(value: string): void {
    logEvent("onboarding_suggestion_corrected", { field: "industries", value });
    setIndustries((current) => {
      if (current.includes(value)) {
        return current.filter((item) => item !== value);
      }

      return [...current, value].slice(0, 4);
    });
  }
}

function minimumTheatreMs(): number {
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches ? 900 : 4200;
}

type InferenceLineProps = {
  label: string;
  onToggle: (value: string) => void;
  options: string[];
  value?: never;
  values: string[];
} | {
  label: string;
  onToggle?: never;
  options?: never;
  value: string;
  values?: never;
};

function InferenceLine({
  label,
  onToggle,
  options,
  value,
  values,
}: InferenceLineProps): ReactElement {
  if (value !== undefined) {
    return (
      <div className="inference-line">
        <span>{label}</span>
        <p>{value}</p>
      </div>
    );
  }

  return (
    <div className="inference-line">
      <span>{label}</span>
      <div>
        {options.map((option) => {
          const selected = values.includes(option);

          return (
            <button
              aria-pressed={selected}
              className={selected ? "is-selected" : ""}
              key={option}
              onClick={() => onToggle(option)}
              type="button"
            >
              {selected ? "Confirm " : "Correct to "}
              {option}
            </button>
          );
        })}
      </div>
    </div>
  );
}

function wait(ms: number): Promise<void> {
  return new Promise((resolve) => {
    window.setTimeout(resolve, ms);
  });
}
