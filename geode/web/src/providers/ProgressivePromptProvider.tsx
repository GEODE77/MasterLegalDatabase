"use client";

import {
  useCallback,
  useMemo,
  useRef,
  useState,
  type ReactElement,
  type ReactNode,
} from "react";

import { ProgressivePrompt } from "@/components/prompts/ProgressivePrompt";
import { usePersonalization } from "@/hooks/usePersonalization";
import { ProgressivePromptContext } from "@/lib/progressivePrompts/context";
import { PROGRESSIVE_PROMPTS } from "@/lib/progressivePrompts/registry";
import type {
  ProgressivePromptAction,
  ProgressivePromptAnswer,
  ProgressivePromptDefinition,
  PromptPreferenceUpdate,
} from "@/lib/progressivePrompts/types";
import type { JsonValue, PersonalizationExplicitAnswer } from "@/lib/personalization/types";

const PROMPT_RETRY_MS = 7 * 24 * 60 * 60 * 1000;

type ProgressivePromptProviderProps = {
  children: ReactNode;
};

export function ProgressivePromptProvider({
  children,
}: ProgressivePromptProviderProps): ReactElement {
  const { logEvent, profile, setPreferences } = usePersonalization();
  const [activePrompt, setActivePrompt] = useState<ProgressivePromptDefinition | null>(null);
  const activeRef = useRef<ProgressivePromptDefinition | null>(null);
  const promptValues = useMemo(() => toAnswerMap(profile.explicitAnswers), [profile.explicitAnswers]);
  const promptsEnabled = promptValues.get("progressivePrompts.disabled") !== true;

  const triggerPrompt = useCallback(
    async (action: ProgressivePromptAction): Promise<void> => {
      if (!promptsEnabled || activeRef.current) {
        return;
      }

      const prompt = PROGRESSIVE_PROMPTS.find((candidate) =>
        candidate.action === action && isPromptEligible(candidate, promptValues),
      );

      if (!prompt) {
        return;
      }

      markShownThisSession(prompt.id);
      activeRef.current = prompt;
      setActivePrompt(prompt);
      await setPreferences({
        answers: [
          {
            key: promptKey(prompt.id, "shownCount"),
            value: readNumber(promptValues, promptKey(prompt.id, "shownCount")) + 1,
          },
          {
            key: promptKey(prompt.id, "lastShownAt"),
            value: new Date().toISOString(),
          },
        ],
      });
      void logEvent("progressive_prompt_shown", {
        action,
        promptId: prompt.id,
      });
    },
    [logEvent, promptValues, promptsEnabled, setPreferences],
  );

  const dismissPrompt = useCallback(async (): Promise<void> => {
    const prompt = activeRef.current;

    if (!prompt) {
      return;
    }

    const dismissedCount = readNumber(promptValues, promptKey(prompt.id, "dismissedCount")) + 1;
    const answers: PromptPreferenceUpdate[] = [
      {
        key: promptKey(prompt.id, "dismissedCount"),
        value: dismissedCount,
      },
      {
        key: promptKey(prompt.id, "lastDismissedAt"),
        value: new Date().toISOString(),
      },
    ];

    if (dismissedCount >= prompt.maxDismissals) {
      answers.push({ key: promptKey(prompt.id, "retired"), value: true });
    }

    activeRef.current = null;
    setActivePrompt(null);
    await setPreferences({ answers });
    void logEvent("progressive_prompt_dismissed", {
      dismissedCount,
      promptId: prompt.id,
    });
  }, [logEvent, promptValues, setPreferences]);

  const answerPrompt = useCallback(
    async (answer: ProgressivePromptAnswer): Promise<void> => {
      const prompt = activeRef.current;

      if (!prompt) {
        return;
      }

      activeRef.current = null;
      setActivePrompt(null);
      await setPreferences({
        answers: [
          ...answer.writes,
          { key: promptKey(prompt.id, "answered"), value: true },
          { key: promptKey(prompt.id, "answeredAt"), value: new Date().toISOString() },
          { key: promptKey(prompt.id, "answerId"), value: answer.id },
        ],
      });
      void logEvent("progressive_prompt_answered", {
        answerId: answer.id,
        promptId: prompt.id,
      });
    },
    [logEvent, setPreferences],
  );

  const setPromptsEnabled = useCallback(
    async (enabled: boolean): Promise<void> => {
      activeRef.current = null;
      setActivePrompt(null);
      await setPreferences({
        answers: [{ key: "progressivePrompts.disabled", value: !enabled }],
      });
      void logEvent(enabled ? "progressive_prompts_enabled" : "progressive_prompts_disabled");
    },
    [logEvent, setPreferences],
  );

  return (
    <ProgressivePromptContext.Provider
      value={{
        activePrompt,
        answerPrompt,
        dismissPrompt,
        promptsEnabled,
        setPromptsEnabled,
        triggerPrompt,
      }}
    >
      {children}
      <ProgressivePrompt />
    </ProgressivePromptContext.Provider>
  );
}

function isPromptEligible(
  prompt: ProgressivePromptDefinition,
  values: Map<string, JsonValue>,
): boolean {
  if (values.get(promptKey(prompt.id, "answered")) === true) {
    return false;
  }

  if (values.get(promptKey(prompt.id, "retired")) === true) {
    return false;
  }

  if (wasShownThisSession(prompt.id)) {
    return false;
  }

  if (readNumber(values, promptKey(prompt.id, "shownCount")) >= prompt.maxShows) {
    return false;
  }

  if (readNumber(values, promptKey(prompt.id, "dismissedCount")) >= prompt.maxDismissals) {
    return false;
  }

  if (wasRecentlyDismissed(values, prompt.id)) {
    return false;
  }

  if (prompt.skipIfAnsweredKeys?.some((key) => values.has(key))) {
    return false;
  }

  return true;
}

function toAnswerMap(answers: PersonalizationExplicitAnswer[]): Map<string, JsonValue> {
  return new Map(answers.map((answer) => [answer.key, answer.value]));
}

function readNumber(values: Map<string, JsonValue>, key: string): number {
  const value = values.get(key);
  return typeof value === "number" ? value : 0;
}

function wasRecentlyDismissed(values: Map<string, JsonValue>, promptId: string): boolean {
  const value = values.get(promptKey(promptId, "lastDismissedAt"));

  if (typeof value !== "string") {
    return false;
  }

  return Date.now() - Date.parse(value) < PROMPT_RETRY_MS;
}

function promptKey(promptId: string, field: string): string {
  return `progressivePrompts.${promptId}.${field}`;
}

function wasShownThisSession(promptId: string): boolean {
  return sessionStorage.getItem(sessionPromptKey(promptId)) === "1";
}

function markShownThisSession(promptId: string): void {
  sessionStorage.setItem(sessionPromptKey(promptId), "1");
}

function sessionPromptKey(promptId: string): string {
  return `geode.progressivePrompt.session.${promptId}`;
}
