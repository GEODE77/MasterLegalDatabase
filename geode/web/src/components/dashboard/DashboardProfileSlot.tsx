"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import type { ReactElement } from "react";

import { usePersonalization } from "@/hooks/usePersonalization";
import { useProgressivePrompts } from "@/hooks/useProgressivePrompts";
import { useUndoToast } from "@/providers/UndoToastProvider";

export function DashboardProfileSlot(): ReactElement {
  const { deletePersonalization, profile } = usePersonalization();
  const { promptsEnabled, setPromptsEnabled } = useProgressivePrompts();
  const { showUndoToast } = useUndoToast();
  const [isOpen, setIsOpen] = useState(false);

  useEffect(() => {
    if (!isOpen) {
      return;
    }

    function closeOnEscape(event: KeyboardEvent): void {
      if (event.key === "Escape") {
        setIsOpen(false);
      }
    }

    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [isOpen]);

  function resetDemo(): void {
    setIsOpen(false);
    showUndoToast({
      message: "Demo reset scheduled.",
      onExpire: async () => {
        await deletePersonalization();
        window.location.href = "/onboarding";
      },
    });
  }

  return (
    <div className="dashboard-profile-shell">
      <button
        aria-expanded={isOpen}
        aria-label="Profile settings"
        className="dashboard-profile"
        onClick={() => setIsOpen((value) => !value)}
        type="button"
      >
        {profile.derived.initials}
      </button>
      {isOpen ? (
        <div className="profile-settings-card">
          <span>Profile settings</span>
          <button onClick={() => void setPromptsEnabled(!promptsEnabled)} type="button">
            Progressive prompts {promptsEnabled ? "on" : "off"}
          </button>
          <Link href="/debug/personalization">View derived model</Link>
          <Link href="/debug/onboarding">View onboarding analytics</Link>
          <button className="destructive-action" onClick={resetDemo} type="button">
            Reset demo
          </button>
        </div>
      ) : null}
    </div>
  );
}
