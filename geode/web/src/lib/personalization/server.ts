import fs from "node:fs";
import path from "node:path";
import { randomUUID } from "node:crypto";

import { REPOSITORY_ROOT } from "@/lib/paths";
import { derivePersonalizationProfile, normalizePersonalizationSnapshot } from "./shared";
import type {
  JsonObject,
  PersonalizationDeleteResponse,
  PersonalizationExplicitAnswer,
  PersonalizationEventInput,
  PersonalizationPreferenceUpdate,
  PersonalizationSnapshot,
} from "./types";

const PERSONALIZATION_DIR = path.join(REPOSITORY_ROOT, "geode", "web", "data", "personalization", "users");
const PROFILE_SCHEMA_VERSION = 1;
const MAX_BEHAVIOR_EVENTS = 250;

export function resolveUserId(value: string | null | undefined): string {
  const raw = value?.trim();

  if (!raw) {
    return `anon-${randomUUID()}`;
  }

  return raw.replace(/[^a-zA-Z0-9_-]/g, "-");
}

export function readOrCreateSnapshot(userId: string): PersonalizationSnapshot {
  const filePath = profileFilePath(userId);

  if (!fs.existsSync(filePath)) {
    const snapshot = createDefaultSnapshot(userId);
    writeSnapshot(snapshot);
    return snapshot;
  }

  const raw = JSON.parse(fs.readFileSync(filePath, "utf8")) as PersonalizationSnapshot;
  return migrateSnapshot(raw, userId);
}

export function createTransientSnapshot(userId: string): PersonalizationSnapshot {
  return createDefaultSnapshot(userId);
}

export function updatePreferences(
  userId: string,
  update: PersonalizationPreferenceUpdate,
): PersonalizationSnapshot {
  const snapshot = readOrCreateSnapshot(userId);
  const nextExplicit = upsertAnswers(snapshot.explicitAnswers, update.answers);
  const nextSnapshot = finalizeSnapshot({
    ...snapshot,
    explicitAnswers: nextExplicit,
    updatedAt: new Date().toISOString(),
  });

  writeSnapshot(nextSnapshot);
  return nextSnapshot;
}

export function appendBehaviorEvents(userId: string, events: PersonalizationEventInput[]): PersonalizationSnapshot {
  const snapshot = readOrCreateSnapshot(userId);
  const nextEvents = [
    ...snapshot.behaviorEvents,
    ...events.map((event) => ({
      eventId: randomUUID(),
      payload: sanitizePayload(event.payload),
      recordedAt: new Date().toISOString(),
      source: "behavior" as const,
      type: event.type,
    })),
  ].slice(-MAX_BEHAVIOR_EVENTS);

  const nextSnapshot = finalizeSnapshot({
    ...snapshot,
    behaviorEvents: nextEvents,
    updatedAt: new Date().toISOString(),
  });

  writeSnapshot(nextSnapshot);
  return nextSnapshot;
}

export function deleteSnapshot(userId: string): PersonalizationDeleteResponse {
  const snapshot = readOrCreateSnapshot(userId);
  const filePath = profileFilePath(userId);

  if (fs.existsSync(filePath)) {
    fs.unlinkSync(filePath);
  }

  return {
    deleted: true,
    snapshot,
  };
}

export function createPublicSnapshot(snapshot: PersonalizationSnapshot): PersonalizationSnapshot {
  return {
    ...snapshot,
    explicitAnswers: snapshot.explicitAnswers.filter((answer) => answer.sensitivity === "public"),
  };
}

export function listPersonalizationSnapshots(): PersonalizationSnapshot[] {
  if (!fs.existsSync(PERSONALIZATION_DIR)) {
    return [];
  }

  return fs
    .readdirSync(PERSONALIZATION_DIR)
    .filter((fileName) => fileName.endsWith(".json"))
    .flatMap((fileName) => {
      try {
        const userId = fileName.replace(/\.json$/, "");
        const raw = JSON.parse(fs.readFileSync(profileFilePath(userId), "utf8")) as PersonalizationSnapshot;
        return [migrateSnapshot(raw, userId)];
      } catch {
        return [];
      }
    });
}

function finalizeSnapshot(snapshot: Omit<PersonalizationSnapshot, "derived">): PersonalizationSnapshot {
  return {
    ...snapshot,
    derived: derivePersonalizationProfile(snapshot),
  };
}

function createDefaultSnapshot(userId: string): PersonalizationSnapshot {
  const now = new Date().toISOString();
  const explicitAnswers: PersonalizationExplicitAnswer[] = [
    {
      answeredAt: now,
      key: "displayName",
      sensitivity: "public",
      source: "explicit",
      value: "JP",
    },
  ];

  return finalizeSnapshot({
    behaviorEvents: [],
    explicitAnswers,
    schemaVersion: PROFILE_SCHEMA_VERSION,
    updatedAt: now,
    userId,
  });
}

function migrateSnapshot(snapshot: PersonalizationSnapshot, userId: string): PersonalizationSnapshot {
  const safeSnapshot: PersonalizationSnapshot = normalizePersonalizationSnapshot({
    behaviorEvents: Array.isArray(snapshot.behaviorEvents) ? snapshot.behaviorEvents : [],
    derived: snapshot.derived,
    explicitAnswers: Array.isArray(snapshot.explicitAnswers) ? snapshot.explicitAnswers : [],
    schemaVersion: PROFILE_SCHEMA_VERSION,
    updatedAt: snapshot.updatedAt ?? new Date().toISOString(),
    userId: snapshot.userId ?? userId,
  });

  if (!safeSnapshot.explicitAnswers.some((answer) => answer.key === "displayName")) {
    safeSnapshot.explicitAnswers = [
      ...safeSnapshot.explicitAnswers,
      {
        answeredAt: safeSnapshot.updatedAt,
        key: "displayName",
        sensitivity: "public",
        source: "explicit",
        value: "JP",
      },
    ];
  }

  return finalizeSnapshot(safeSnapshot);
}

function sanitizePayload(payload: JsonObject | undefined): JsonObject {
  if (!payload) {
    return {};
  }

  return JSON.parse(JSON.stringify(payload)) as JsonObject;
}

function profileFilePath(userId: string): string {
  return path.join(PERSONALIZATION_DIR, `${userId}.json`);
}

function writeSnapshot(snapshot: PersonalizationSnapshot): void {
  fs.mkdirSync(PERSONALIZATION_DIR, { recursive: true });
  fs.writeFileSync(profileFilePath(snapshot.userId), `${JSON.stringify(snapshot, null, 2)}\n`, "utf8");
}

function upsertAnswers(
  existing: PersonalizationExplicitAnswer[],
  updates: PersonalizationPreferenceUpdate["answers"],
): PersonalizationExplicitAnswer[] {
  const byKey = new Map(existing.map((answer) => [answer.key, answer]));
  const now = new Date().toISOString();

  for (const update of updates) {
    byKey.set(update.key, {
      answeredAt: now,
      key: update.key,
      sensitivity: update.sensitivity ?? "public",
      source: "explicit",
      value: update.value,
    });
  }

  return Array.from(byKey.values());
}
