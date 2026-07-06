"use client";

import Link from "next/link";
import { useState, type ReactElement } from "react";

import { readDraft, useDraftAutosave } from "@/hooks/useDraftAutosave";
import { usePersonalization } from "@/hooks/usePersonalization";
import { useProgressivePrompts } from "@/hooks/useProgressivePrompts";
import type { JsonValue } from "@/lib/personalization/types";
import { useUndoToast } from "@/providers/UndoToastProvider";

const SETTINGS_DRAFT_KEY = "geode.draft.settings";

export default function SettingsPage(): ReactElement {
  const { deletePersonalization, profile, setPreferences } = usePersonalization();
  const { promptsEnabled, setPromptsEnabled } = useProgressivePrompts();
  const { showToast, showUndoToast } = useUndoToast();
  const settingsDraft = readDraft(SETTINGS_DRAFT_KEY, defaultSettings(profile));
  const [displayName, setDisplayName] = useState(settingsDraft.displayName);
  const [email, setEmail] = useState(settingsDraft.email);
  const [role, setRole] = useState(settingsDraft.role);
  const [jurisdictions, setJurisdictions] = useState(settingsDraft.jurisdictions);
  const [industries, setIndustries] = useState(settingsDraft.industries);
  const [touched, setTouched] = useState<Record<string, boolean>>({});
  const [dataState, setDataState] = useState("Stored locally");
  const draftSavedAt = useDraftAutosave(SETTINGS_DRAFT_KEY, {
    displayName,
    email,
    industries,
    jurisdictions,
    role,
  });
  const errors = {
    displayName: displayName.trim() ? "" : "Add a display name.",
    email: !email.trim() || isEmail(email) ? "" : "Use a valid email address.",
    industries: splitList(industries).length > 0 ? "" : "Add at least one industry.",
    jurisdictions: splitList(jurisdictions).length > 0 ? "" : "Add at least one jurisdiction.",
    role: role.trim() ? "" : "Add your role.",
  };

  async function saveProfile(showAllValidation = false): Promise<void> {
    if (showAllValidation) {
      setTouched({ displayName: true, email: true, industries: true, jurisdictions: true, role: true });
    }

    if (Object.values(errors).some(Boolean)) {
      return;
    }

    const jurisdictionList = splitList(jurisdictions);
    const industryList = splitList(industries);

    await setPreferences({
      answers: [
        { key: "displayName", value: displayName.trim() || "Geode user" },
        { key: "email", sensitivity: "private", value: email.trim() },
        { key: "role", value: role.trim() || "Executive" },
        { key: "jurisdiction", value: jurisdictionList[0] ?? "Colorado" },
        { key: "jurisdictions", value: jurisdictionList },
        { key: "industries", value: industryList },
      ],
    });
    window.localStorage.removeItem(SETTINGS_DRAFT_KEY);
    showToast({ message: "Settings saved." });
  }

  function downloadData(): void {
    const blob = new Blob([JSON.stringify(profile, null, 2)], { type: "application/json" });
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "geode-personalization-profile.json";
    link.click();
    window.URL.revokeObjectURL(url);
    setDataState("Downloaded");
    showToast({ message: "Data downloaded." });
  }

  async function updatePrompts(enabled: boolean): Promise<void> {
    await setPromptsEnabled(enabled);
    showToast({ message: enabled ? "Prompts enabled." : "Prompts disabled." });
  }

  async function clearData(): Promise<void> {
    setDataState("Deletion scheduled");
    showUndoToast({
      message: "Account deletion scheduled.",
      onExpire: async () => {
        await deletePersonalization();
        setDataState("Cleared");
      },
      onUndo: () => setDataState("Stored locally"),
    });
  }

  async function signOut(): Promise<void> {
    setDataState("Sign out scheduled");
    showUndoToast({
      message: "Sign out scheduled.",
      onExpire: async () => {
        await deletePersonalization();
        window.location.href = "/sign-in";
      },
      onUndo: () => setDataState("Stored locally"),
    });
  }

  return (
    <main className="functional-page settings-page">
      <div className="settings-list" aria-label="Settings">
        <section className="settings-section" aria-label="Profile">
          <h1>Profile</h1>
          <div className="settings-row">
            <label htmlFor="display-name">Display name</label>
            <input
              id="display-name"
              aria-describedby="display-name-validation"
              aria-invalid={touched.displayName && Boolean(errors.displayName)}
              aria-label="Display name"
              onBlur={() => {
                setTouched((current) => ({ ...current, displayName: true }));
                void saveProfile();
              }}
              onChange={(event) => setDisplayName(event.target.value)}
              value={displayName}
            />
            <FieldValidation id="display-name-validation" isVisible={Boolean(touched.displayName)} message={errors.displayName} />
          </div>
          <div className="settings-row">
            <label htmlFor="settings-email">Email</label>
            <input
              id="settings-email"
              aria-describedby="settings-email-validation"
              aria-invalid={touched.email && Boolean(errors.email)}
              aria-label="Email"
              inputMode="email"
              onBlur={() => {
                setTouched((current) => ({ ...current, email: true }));
                void saveProfile();
              }}
              onChange={(event) => setEmail(event.target.value)}
              placeholder="name@company.com"
              type="email"
              value={email}
            />
            <FieldValidation id="settings-email-validation" isVisible={Boolean(touched.email)} message={errors.email} />
          </div>
          <div className="settings-row">
            <label htmlFor="settings-role">Role</label>
            <input
              id="settings-role"
              aria-describedby="settings-role-validation"
              aria-invalid={touched.role && Boolean(errors.role)}
              aria-label="Role"
              onBlur={() => {
                setTouched((current) => ({ ...current, role: true }));
                void saveProfile();
              }}
              onChange={(event) => setRole(event.target.value)}
              value={role}
            />
            <FieldValidation id="settings-role-validation" isVisible={Boolean(touched.role)} message={errors.role} />
          </div>
          <div className="settings-row">
            <label htmlFor="settings-jurisdictions">Jurisdictions</label>
            <input
              id="settings-jurisdictions"
              aria-describedby="settings-jurisdictions-validation"
              aria-invalid={touched.jurisdictions && Boolean(errors.jurisdictions)}
              aria-label="Jurisdictions"
              onBlur={() => {
                setTouched((current) => ({ ...current, jurisdictions: true }));
                void saveProfile();
              }}
              onChange={(event) => setJurisdictions(event.target.value)}
              value={jurisdictions}
            />
            <FieldValidation id="settings-jurisdictions-validation" isVisible={Boolean(touched.jurisdictions)} message={errors.jurisdictions} />
          </div>
          <div className="settings-row">
            <label htmlFor="settings-industries">Industries followed</label>
            <input
              id="settings-industries"
              aria-describedby="settings-industries-validation settings-draft-status"
              aria-invalid={touched.industries && Boolean(errors.industries)}
              aria-label="Industries followed"
              onBlur={() => {
                setTouched((current) => ({ ...current, industries: true }));
                void saveProfile();
              }}
              onChange={(event) => setIndustries(event.target.value)}
              value={industries}
            />
            <FieldValidation id="settings-industries-validation" isVisible={Boolean(touched.industries)} message={errors.industries} />
          </div>
          {draftSavedAt ? <span className="draft-status" id="settings-draft-status">Draft saved {draftSavedAt}</span> : null}
        </section>

        <section className="settings-section" aria-label="Notifications">
          <h2>Notifications</h2>
          <div className="settings-row">
            <span>Progressive prompts</span>
            <button onClick={() => void updatePrompts(!promptsEnabled)} type="button">
              {promptsEnabled ? "On" : "Off"}
            </button>
          </div>
        </section>

        <section className="settings-section" aria-label="Data">
          <h2>Data</h2>
          <div className="settings-row">
            <span>Personalization profile</span>
            <Link href="/debug/personalization">View</Link>
          </div>
          <div className="settings-row">
            <span>Download data</span>
            <button onClick={downloadData} type="button">
              {dataState === "Downloaded" ? "Downloaded" : "Download"}
            </button>
          </div>
          <div className="settings-row">
            <span>Delete account</span>
            <button className="destructive-action" onClick={() => void clearData()} type="button">
              {dataState === "Cleared" ? "Cleared" : dataState === "Deletion scheduled" ? "Scheduled" : "Delete"}
            </button>
          </div>
        </section>

        <button className="settings-sign-out destructive-action" onClick={() => void signOut()} type="button">
          Sign out
        </button>
      </div>
    </main>
  );
}

function FieldValidation({
  id,
  isVisible,
  message,
}: {
  id: string;
  isVisible: boolean;
  message: string;
}): ReactElement | null {
  if (!isVisible) {
    return null;
  }

  return (
    <span className={message ? "field-validation is-error" : "field-validation is-valid"} id={id}>
      {message || "Looks good."}
    </span>
  );
}

function defaultSettings(profile: ReturnType<typeof usePersonalization>["profile"]): {
  displayName: string;
  email: string;
  industries: string;
  jurisdictions: string;
  role: string;
} {
  return {
    displayName: profile.derived.displayName,
    email: readAnswer(profile.explicitAnswers, "email"),
    industries:
      readListAnswer(profile.explicitAnswers, "industries")
      || formatList(profile.derived.industryVector.map((item) => item.key))
      || "General compliance",
    jurisdictions:
      readListAnswer(profile.explicitAnswers, "jurisdictions")
      || readAnswer(profile.explicitAnswers, "jurisdiction")
      || "Colorado",
    role: readAnswer(profile.explicitAnswers, "role") || formatLabel(profile.derived.roleVector[0]?.key),
  };
}

function isEmail(value: string): boolean {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value.trim());
}

function readAnswer(
  answers: Array<{ key: string; value: JsonValue }>,
  key: string,
): string {
  const answer = answers.find((item) => item.key === key);
  return typeof answer?.value === "string" ? answer.value : "";
}

function readListAnswer(
  answers: Array<{ key: string; value: JsonValue }>,
  key: string,
): string {
  const answer = answers.find((item) => item.key === key);

  if (!Array.isArray(answer?.value)) {
    return "";
  }

  return answer.value.filter((item): item is string => typeof item === "string").join(", ");
}

function splitList(value: string): string[] {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function formatList(values: string[]): string {
  return values.map(formatLabel).filter(Boolean).join(", ");
}

function formatLabel(value?: string): string {
  if (!value) {
    return "";
  }

  return value
    .split(/[-_\s]+/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}
