import fs from "node:fs";
import path from "node:path";

import { REPOSITORY_ROOT } from "@/lib/paths";
import type { ManagerSession } from "@/lib/manager/store";

const MANAGER_DATA_DIR = path.join(REPOSITORY_ROOT, "geode", "web", "data", "manager");
const OVERRIDE_PATH = path.join(MANAGER_DATA_DIR, "operation_overrides.json");

export type QueueOverride = {
  completedAt?: string;
  officialSourceConfirmation?: string;
  owner?: string;
  managerNote?: string;
  queueId: string;
  status?: string;
  updatedAt: string;
  updatedByEmail: string;
  updatedByName: string;
};

type OperationOverrides = {
  queue: Record<string, QueueOverride>;
  schemaVersion: number;
};

export function readQueueOverrides(): Record<string, QueueOverride> {
  return readOperationOverrides().queue;
}

export function updateQueueOverride(
  queueId: string,
  input: {
    officialSourceConfirmation?: string;
    owner?: string;
    managerNote?: string;
    status?: string;
  },
  manager: ManagerSession,
): QueueOverride {
  const overrides = readOperationOverrides();
  const status = cleanValue(input.status);
  const next: QueueOverride = {
    ...overrides.queue[queueId],
    officialSourceConfirmation: cleanValue(input.officialSourceConfirmation),
    owner: cleanValue(input.owner),
    managerNote: cleanValue(input.managerNote),
    queueId,
    status,
    updatedAt: new Date().toISOString(),
    updatedByEmail: manager.email,
    updatedByName: manager.name,
  };

  if (status === "complete") {
    next.completedAt = next.updatedAt;
  }

  overrides.queue[queueId] = next;
  writeOperationOverrides(overrides);
  return next;
}

function readOperationOverrides(): OperationOverrides {
  if (!fs.existsSync(OVERRIDE_PATH)) {
    return { queue: {}, schemaVersion: 1 };
  }

  try {
    const parsed = JSON.parse(fs.readFileSync(OVERRIDE_PATH, "utf8")) as Partial<OperationOverrides>;
    return {
      queue: parsed.queue && typeof parsed.queue === "object" ? parsed.queue : {},
      schemaVersion: 1,
    };
  } catch {
    return { queue: {}, schemaVersion: 1 };
  }
}

function writeOperationOverrides(overrides: OperationOverrides): void {
  fs.mkdirSync(MANAGER_DATA_DIR, { recursive: true });
  const temporaryPath = `${OVERRIDE_PATH}.tmp`;
  fs.writeFileSync(
    temporaryPath,
    `${JSON.stringify({ queue: overrides.queue, schemaVersion: 1 }, null, 2)}\n`,
    "utf8",
  );
  fs.renameSync(temporaryPath, OVERRIDE_PATH);
}

function cleanValue(value: string | undefined): string | undefined {
  const cleaned = value?.trim();
  return cleaned ? cleaned : undefined;
}
