import type {
  JsonValue,
  PersonalizationBehaviorEvent,
  PersonalizationDerivedProfile,
  PersonalizationExplicitAnswer,
  PersonalizationSnapshot,
} from "./types";

type Vector = Array<{ key: string; weight: number }>;

const DEFAULT_DISPLAY_NAME = "JP";
const DEFAULT_INITIALS = "JP";
const MAX_VECTOR_ITEMS = 6;

const INDUSTRY_TERMS = {
  "advanced ceramics": ["ceramic", "silica", "kiln", "powder", "dust", "technical-ceramics"],
  environment: ["environment", "water", "wastewater", "air", "emissions", "discharge", "ehs"],
  manufacturing: ["manufacturing", "plant", "factory", "production", "facility"],
  "supply chain": ["supplier", "procurement", "vendor", "flowdown", "supply"],
  "worker safety": ["osha", "worker", "safety", "injury", "exposure"],
};

const AGENCY_TERMS = {
  cdphe: ["cdphe", "public health", "environment", "air quality", "water quality"],
  cdle: ["labor", "employment", "worker", "wage", "safety"],
  dora: ["regulatory agencies", "license", "licensing", "professional"],
  cdnr: ["natural resources", "energy", "oil", "gas", "water"],
  cdot: ["transportation", "carrier", "freight", "road"],
};

export function derivePersonalizationProfile(snapshot: {
  behaviorEvents: PersonalizationBehaviorEvent[];
  explicitAnswers: PersonalizationExplicitAnswer[];
  updatedAt: string;
  userId: string;
}): PersonalizationDerivedProfile {
  const explicitName = readStringAnswer(snapshot.explicitAnswers, "displayName") ?? DEFAULT_DISPLAY_NAME;
  const industryVector = normalizeVector(deriveIndustryVector(snapshot.explicitAnswers, snapshot.behaviorEvents));
  const agencyVector = normalizeVector(deriveAgencyVector(snapshot.behaviorEvents));
  const surfaceVector = normalizeVector(deriveSurfaceVector(snapshot.behaviorEvents));
  const roleVector = normalizeVector(deriveRoleVector(snapshot.explicitAnswers, snapshot.behaviorEvents));
  const topicSignals = mergeTopicSignals(industryVector, surfaceVector);
  const behaviorScore = Math.round(
    snapshot.behaviorEvents.length + topicSignals.reduce((sum, signal) => sum + signal.weight * 10, 0),
  );

  return {
    agencyVector,
    behaviorScore,
    confidence: deriveConfidence(snapshot.behaviorEvents),
    displayName: explicitName,
    initials: deriveInitials(explicitName),
    industryVector,
    lastActiveAt: lastActiveAt(snapshot.behaviorEvents, snapshot.updatedAt),
    modelVersion: 2,
    preferredTone: deriveTone(snapshot.behaviorEvents),
    primaryInterest: industryVector[0]?.key ?? topicSignals[0]?.key ?? null,
    readingDensity: deriveReadingDensity(snapshot.behaviorEvents),
    recomputedAt: new Date().toISOString(),
    roleVector,
    surfaceVector,
    topicSignals,
  };
}

export function normalizePersonalizationSnapshot(snapshot: PersonalizationSnapshot): PersonalizationSnapshot {
  return {
    ...snapshot,
    derived: derivePersonalizationProfile(snapshot),
    explicitAnswers: snapshot.explicitAnswers.filter((answer) => answer.key && answer.value !== undefined),
  };
}

function deriveIndustryVector(
  explicitAnswers: PersonalizationExplicitAnswer[],
  behaviorEvents: PersonalizationBehaviorEvent[],
): Map<string, number> {
  const scores = new Map<string, number>();
  const explicitIndustry = readStringAnswer(explicitAnswers, "industry");
  const explicitIndustries = readStringArrayAnswer(explicitAnswers, "industries");

  if (explicitIndustry) {
    incrementSignal(scores, normalizeSignal(explicitIndustry), 0.42);
  }

  for (const industry of explicitIndustries) {
    incrementSignal(scores, normalizeSignal(industry), 0.32);
  }

  for (const event of behaviorEvents) {
    const weight = eventWeight(event);
    const text = eventText(event);

    for (const [industry, terms] of Object.entries(INDUSTRY_TERMS)) {
      if (terms.some((term) => text.includes(term))) {
        incrementSignal(scores, industry, weight);
      }
    }

    const directIndustry = readPayloadString(event, "industry");
    if (directIndustry) {
      incrementSignal(scores, normalizeSignal(directIndustry), weight);
    }
  }

  return scores;
}

function deriveAgencyVector(behaviorEvents: PersonalizationBehaviorEvent[]): Map<string, number> {
  const scores = new Map<string, number>();

  for (const event of behaviorEvents) {
    const text = eventText(event);

    for (const [agency, terms] of Object.entries(AGENCY_TERMS)) {
      if (terms.some((term) => text.includes(term))) {
        incrementSignal(scores, agency, eventWeight(event));
      }
    }
  }

  return scores;
}

function deriveSurfaceVector(behaviorEvents: PersonalizationBehaviorEvent[]): Map<string, number> {
  const scores = new Map<string, number>();

  for (const event of behaviorEvents) {
    incrementSignal(scores, surfaceForEvent(event), eventWeight(event));
  }

  return scores;
}

function deriveRoleVector(
  explicitAnswers: PersonalizationExplicitAnswer[],
  behaviorEvents: PersonalizationBehaviorEvent[],
): Map<string, number> {
  const scores = new Map<string, number>();
  const explicitRole = readStringAnswer(explicitAnswers, "role");

  if (explicitRole) {
    incrementSignal(scores, normalizeSignal(explicitRole), 0.45);
  }

  for (const event of behaviorEvents) {
    const text = eventText(event);
    const weight = eventWeight(event);

    if (/counsel|legal|attorney/.test(text)) {
      incrementSignal(scores, "legal-counsel", weight);
    }

    if (/plant|facility|operations|production/.test(text)) {
      incrementSignal(scores, "operations-leader", weight);
    }

    if (/compliance|permit|audit|reporting/.test(text)) {
      incrementSignal(scores, "compliance-lead", weight);
    }

    if (/board|ceo|executive|enterprise/.test(text)) {
      incrementSignal(scores, "executive", weight);
    }
  }

  return scores;
}

function normalizeVector(scores: Map<string, number>): Vector {
  const total = Array.from(scores.values()).reduce((sum, value) => sum + value, 0);

  if (total <= 0) {
    return [];
  }

  return Array.from(scores.entries())
    .map(([key, value]) => ({ key, weight: Number((value / total).toFixed(3)) }))
    .sort((a, b) => b.weight - a.weight)
    .slice(0, MAX_VECTOR_ITEMS);
}

function mergeTopicSignals(industryVector: Vector, surfaceVector: Vector): Vector {
  const scores = new Map<string, number>();

  for (const item of industryVector) {
    incrementSignal(scores, item.key, item.weight * 0.68);
  }

  for (const item of surfaceVector) {
    incrementSignal(scores, item.key, item.weight * 0.32);
  }

  return normalizeVector(scores);
}

function eventWeight(event: PersonalizationBehaviorEvent): number {
  const base = baseWeight(event.type);
  const age = Date.now() - Date.parse(event.recordedAt);
  const recency = Number.isFinite(age) ? Math.max(0.35, 1 - age / (30 * 24 * 60 * 60 * 1000)) : 0.7;
  return base * recency;
}

function baseWeight(type: string): number {
  if (type === "regulation_read_full") {
    return 1.6;
  }

  if (type === "query_submitted" || type === "query_result_opened") {
    return 1.2;
  }

  if (type === "forum_thread_created" || type === "forum_reply_created") {
    return 1.15;
  }

  if (type === "page_engagement") {
    return 0.8;
  }

  if (type === "forum_vote") {
    return 0.55;
  }

  return 0.35;
}

function surfaceForEvent(event: PersonalizationBehaviorEvent): string {
  if (event.type.startsWith("forum_")) {
    return "community";
  }

  if (event.type.startsWith("query_")) {
    return "query";
  }

  if (event.type.startsWith("onboarding_")) {
    return "onboarding";
  }

  const pathname = readPayloadString(event, "pathname");

  if (pathname?.startsWith("/forum")) {
    return "community";
  }

  if (pathname?.startsWith("/query")) {
    return "query";
  }

  return "dashboard";
}

function deriveTone(
  behaviorEvents: PersonalizationBehaviorEvent[],
): PersonalizationDerivedProfile["preferredTone"] {
  const surfaces = normalizeVector(deriveSurfaceVector(behaviorEvents));
  const topSurface = surfaces[0]?.key;

  if (topSurface === "query") {
    return "analytical";
  }

  if (topSurface === "community") {
    return "collaborative";
  }

  return "direct";
}

function deriveReadingDensity(
  behaviorEvents: PersonalizationBehaviorEvent[],
): PersonalizationDerivedProfile["readingDensity"] {
  const engagementSeconds = behaviorEvents.reduce((sum, event) => {
    if (event.type !== "page_engagement") {
      return sum;
    }

    const seconds = event.payload.secondsOnPage;
    return sum + (typeof seconds === "number" ? seconds : 0);
  }, 0);
  const fullReads = behaviorEvents.filter((event) => event.type === "regulation_read_full").length;

  if (fullReads >= 3 || engagementSeconds > 900) {
    return "deep";
  }

  if (fullReads >= 1 || engagementSeconds > 180) {
    return "focused";
  }

  return "light";
}

function deriveConfidence(behaviorEvents: PersonalizationBehaviorEvent[]): number {
  return Number(Math.min(0.95, behaviorEvents.length / 40 + 0.15).toFixed(2));
}

function eventText(event: PersonalizationBehaviorEvent): string {
  return `${event.type} ${JSON.stringify(event.payload)}`.toLowerCase().replace(/_/g, " ");
}

function deriveInitials(displayName: string): string {
  const tokens = displayName
    .trim()
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2);

  if (tokens.length === 0) {
    return DEFAULT_INITIALS;
  }

  return tokens
    .map((token) => token[0] ?? "")
    .join("")
    .toUpperCase()
    .slice(0, 2);
}

function lastActiveAt(
  behaviorEvents: PersonalizationBehaviorEvent[],
  updatedAt: string,
): string {
  const lastEvent = behaviorEvents[behaviorEvents.length - 1];
  return lastEvent?.recordedAt ?? updatedAt;
}

function readStringAnswer(
  answers: PersonalizationExplicitAnswer[],
  key: string,
): string | null {
  const answer = answers.find((item) => item.key === key);
  return typeof answer?.value === "string" ? answer.value : null;
}

function readStringArrayAnswer(
  answers: PersonalizationExplicitAnswer[],
  key: string,
): string[] {
  const answer = answers.find((item) => item.key === key);

  if (!Array.isArray(answer?.value)) {
    return [];
  }

  return answer.value.filter((item): item is string => typeof item === "string");
}

function readPayloadString(event: PersonalizationBehaviorEvent, key: string): string | null {
  const value: JsonValue | undefined = event.payload[key];
  return typeof value === "string" ? value.toLowerCase() : null;
}

function incrementSignal(signals: Map<string, number>, key: string, weight: number): void {
  signals.set(key, (signals.get(key) ?? 0) + weight);
}

function normalizeSignal(value: string): string {
  return value.trim().toLowerCase().replace(/[^a-z0-9]+/g, "-");
}
