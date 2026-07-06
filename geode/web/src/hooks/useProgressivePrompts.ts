"use client";

import { useContext } from "react";

import { ProgressivePromptContext } from "@/lib/progressivePrompts/context";
import type { ProgressivePromptContextValue } from "@/lib/progressivePrompts/types";

export function useProgressivePrompts(): ProgressivePromptContextValue {
  const context = useContext(ProgressivePromptContext);

  if (!context) {
    throw new Error("useProgressivePrompts must be used inside ProgressivePromptProvider.");
  }

  return context;
}
