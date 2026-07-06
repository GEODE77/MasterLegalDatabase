import { listPersonalizationSnapshots } from "@/lib/personalization/server";
import type { PersonalizationBehaviorEvent } from "@/lib/personalization/types";

export type OnboardingAnalytics = {
  analyzedDocuments: number;
  analysisRate: number;
  analysisToConfirmRate: number;
  averageCompletionSeconds: number | null;
  averageParseSeconds: number | null;
  confirmedProfiles: number;
  conversionRate: number;
  droppedFiles: number;
  failedParses: number;
  pastedDocuments: number;
  promptAnswerRate: number;
  promptAnswers: number;
  promptDismissals: number;
  promptShows: number;
  skipRate: number;
  skippedProfiles: number;
  startedSessions: number;
  totalProfiles: number;
};

export function readOnboardingAnalytics(): OnboardingAnalytics {
  const snapshots = listPersonalizationSnapshots();
  const events = snapshots.flatMap((snapshot) => snapshot.behaviorEvents);
  const startedSessions = countEvents(events, "onboarding_entry_viewed");
  const analyzedDocuments = countEvents(events, "onboarding_document_analyzed");
  const confirmedProfiles = countEvents(events, "onboarding_confirmed");
  const skippedProfiles = countEvents(events, "onboarding_skipped");
  const promptShows = countEvents(events, "progressive_prompt_shown");

  return {
    analyzedDocuments,
    analysisRate: rate(analyzedDocuments, startedSessions),
    analysisToConfirmRate: rate(confirmedProfiles, analyzedDocuments),
    averageCompletionSeconds: averagePayloadNumber(events, "onboarding_confirmed", "secondsToComplete"),
    averageParseSeconds: averagePayloadNumber(events, "onboarding_document_analyzed", "parseSeconds"),
    confirmedProfiles,
    conversionRate: rate(confirmedProfiles, confirmedProfiles + skippedProfiles),
    droppedFiles: events.filter((event) => event.type === "onboarding_document_started" && event.payload.source === "file").length,
    failedParses: countEvents(events, "onboarding_parse_failed"),
    pastedDocuments: events.filter((event) => event.type === "onboarding_document_started" && event.payload.source === "paste").length,
    promptAnswerRate: rate(countEvents(events, "progressive_prompt_answered"), promptShows),
    promptAnswers: countEvents(events, "progressive_prompt_answered"),
    promptDismissals: countEvents(events, "progressive_prompt_dismissed"),
    promptShows,
    skipRate: rate(skippedProfiles, startedSessions),
    skippedProfiles,
    startedSessions,
    totalProfiles: snapshots.length,
  };
}

function countEvents(events: PersonalizationBehaviorEvent[], type: string): number {
  return events.filter((event) => event.type === type).length;
}

function averagePayloadNumber(
  events: PersonalizationBehaviorEvent[],
  type: string,
  key: string,
): number | null {
  const values = events
    .filter((event) => event.type === type)
    .map((event) => event.payload[key])
    .filter((value): value is number => typeof value === "number");

  if (values.length === 0) {
    return null;
  }

  return Math.round(values.reduce((sum, value) => sum + value, 0) / values.length);
}

function rate(part: number, whole: number): number {
  if (whole <= 0) {
    return 0;
  }

  return Number((part / whole).toFixed(2));
}
