"use client";

import { createContext } from "react";

import type { ProgressivePromptContextValue } from "./types";

export const ProgressivePromptContext = createContext<ProgressivePromptContextValue | null>(null);
