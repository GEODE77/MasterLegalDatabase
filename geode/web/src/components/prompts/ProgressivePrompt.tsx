"use client";

import type { ReactElement } from "react";

import { useProgressivePrompts } from "@/hooks/useProgressivePrompts";

export function ProgressivePrompt(): ReactElement | null {
  const { activePrompt, answerPrompt, dismissPrompt } = useProgressivePrompts();

  if (!activePrompt) {
    return null;
  }

  const primaryAnswer = activePrompt.answers[0];

  return (
    <aside
      aria-live="polite"
      className={`progressive-prompt prompt-placement-${activePrompt.placement}`}
    >
      <p>
        {activePrompt.teachingLine} {activePrompt.question}
      </p>
      <div className="progressive-prompt-options">
        <button onClick={() => void answerPrompt(primaryAnswer)} type="button">
          {primaryAnswer.label}
        </button>
        <button onClick={dismissPrompt} type="button">
          Later
        </button>
      </div>
    </aside>
  );
}
