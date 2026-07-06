"use client";

import { useContext } from "react";

import { PersonalizationContext } from "@/providers/PersonalizationProvider";

export function usePersonalization() {
  const context = useContext(PersonalizationContext);

  if (!context) {
    throw new Error("usePersonalization must be used within PersonalizationProvider");
  }

  return context;
}
