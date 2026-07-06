import type { JsonValue, PersonalizationPreferenceUpdate } from "@/lib/personalization/types";

export type ProgressivePromptAction =
  | "first_query_completed"
  | "regulation_opened"
  | "forum_thread_created"
  | "forum_reply_created"
  | "forum_vote_cast";

export type ProgressivePromptPlacement =
  | "query-results"
  | "regulation-detail"
  | "forum-feed"
  | "forum-thread";

export type ProgressivePromptAnswer = {
  id: string;
  label: string;
  writes: Array<{
    key: string;
    value: JsonValue;
  }>;
};

export type ProgressivePromptDefinition = {
  action: ProgressivePromptAction;
  answers: ProgressivePromptAnswer[];
  id: string;
  maxDismissals: number;
  maxShows: number;
  placement: ProgressivePromptPlacement;
  question: string;
  skipIfAnsweredKeys?: string[];
  teachingLine: string;
};

export type ProgressivePromptContextValue = {
  activePrompt: ProgressivePromptDefinition | null;
  answerPrompt: (answer: ProgressivePromptAnswer) => Promise<void>;
  dismissPrompt: () => Promise<void>;
  promptsEnabled: boolean;
  setPromptsEnabled: (enabled: boolean) => Promise<void>;
  triggerPrompt: (action: ProgressivePromptAction) => Promise<void>;
};

export type PromptPreferenceUpdate = PersonalizationPreferenceUpdate["answers"][number];
