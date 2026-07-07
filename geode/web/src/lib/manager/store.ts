import { createHash, createHmac, pbkdf2Sync, randomBytes, timingSafeEqual } from "node:crypto";
import fs from "node:fs";
import path from "node:path";

import { REPOSITORY_ROOT } from "@/lib/paths";

const MANAGER_DATA_DIR = path.join(REPOSITORY_ROOT, "geode", "web", "data", "manager");
const MANAGER_REGISTRY_PATH = path.join(MANAGER_DATA_DIR, "managers.json");
const MANAGER_HISTORY_PATH = path.join(MANAGER_DATA_DIR, "review_history.jsonl");
const SESSION_TTL_SECONDS = 60 * 60 * 8;
const INVITE_HASH_ITERATIONS = 120_000;
const INVITE_HASH_BYTES = 32;

type ManagerRegistry = {
  managers: ManagerRecord[];
  schemaVersion: number;
};

export type ManagerRecord = {
  createdAt: string;
  email: string;
  id: string;
  inviteCodeHash: string;
  inviteCodeSalt: string;
  invitedBy: string;
  name: string;
  revokedAt?: string;
  role: "admin" | "manager" | "reviewer";
  status: "active" | "revoked";
};

export type ManagerSession = {
  email: string;
  id: string;
  issuedAt: number;
  name: string;
  role: ManagerRecord["role"];
};

type ManagerHistoryEvent = {
  action: string;
  managerEmail: string;
  managerId: string;
  managerName: string;
  occurredAt: string;
};

export function verifyManagerInvite(email: string, inviteCode: string): ManagerRecord | null {
  const normalizedEmail = normalizeEmail(email);
  const registry = readManagerRegistry();
  const manager = registry.managers.find(
    (record) => normalizeEmail(record.email) === normalizedEmail && record.status === "active",
  );

  if (!manager || !isInviteCodeMatch(inviteCode, manager)) {
    return null;
  }

  appendManagerHistory({
    action: "manager_verified",
    managerEmail: manager.email,
    managerId: manager.id,
    managerName: manager.name,
    occurredAt: new Date().toISOString(),
  });
  return manager;
}

export function createManagerSession(manager: ManagerRecord): string {
  const session: ManagerSession = {
    email: manager.email,
    id: manager.id,
    issuedAt: Math.floor(Date.now() / 1000),
    name: manager.name,
    role: manager.role,
  };
  const payload = Buffer.from(JSON.stringify(session), "utf8").toString("base64url");
  const signature = signSessionPayload(payload);
  return `${payload}.${signature}`;
}

export function readManagerSession(value: string | undefined): ManagerSession | null {
  if (!value) {
    return null;
  }

  const [payload, signature] = value.split(".");
  if (!payload || !signature || !isSameValue(signature, signSessionPayload(payload))) {
    return null;
  }

  const session = parseSessionPayload(payload);
  if (!session || isExpired(session.issuedAt)) {
    return null;
  }

  const manager = readManagerRegistry().managers.find(
    (record) => record.id === session.id && record.status === "active",
  );
  if (!manager) {
    return null;
  }

  return {
    email: manager.email,
    id: manager.id,
    issuedAt: session.issuedAt,
    name: manager.name,
    role: manager.role,
  };
}

export function hashInviteCode(inviteCode: string, salt = randomBytes(16).toString("hex")): {
  hash: string;
  salt: string;
} {
  const hash = pbkdf2Sync(inviteCode, salt, INVITE_HASH_ITERATIONS, INVITE_HASH_BYTES, "sha256");
  return {
    hash: hash.toString("hex"),
    salt,
  };
}

function readManagerRegistry(): ManagerRegistry {
  if (!fs.existsSync(MANAGER_REGISTRY_PATH)) {
    return { managers: [], schemaVersion: 1 };
  }

  const payload = JSON.parse(fs.readFileSync(MANAGER_REGISTRY_PATH, "utf8")) as Partial<ManagerRegistry>;
  return {
    managers: Array.isArray(payload.managers) ? payload.managers : [],
    schemaVersion: 1,
  };
}

function appendManagerHistory(event: ManagerHistoryEvent): void {
  fs.mkdirSync(MANAGER_DATA_DIR, { recursive: true });
  fs.appendFileSync(MANAGER_HISTORY_PATH, `${JSON.stringify(event)}\n`, "utf8");
}

function isInviteCodeMatch(inviteCode: string, manager: ManagerRecord): boolean {
  const { hash } = hashInviteCode(inviteCode, manager.inviteCodeSalt);
  return isSameValue(hash, manager.inviteCodeHash);
}

function signSessionPayload(payload: string): string {
  return createHmac("sha256", managerSessionSecret()).update(payload).digest("base64url");
}

function managerSessionSecret(): string {
  const secret = process.env.GEODE_MANAGER_SESSION_SECRET?.trim();
  if (secret) {
    return secret;
  }

  if (process.env.NODE_ENV === "production") {
    throw new Error("GEODE_MANAGER_SESSION_SECRET is required for manager sessions.");
  }

  return "dev-manager-session";
}

function parseSessionPayload(payload: string): ManagerSession | null {
  try {
    const parsed = JSON.parse(Buffer.from(payload, "base64url").toString("utf8")) as ManagerSession;
    if (
      typeof parsed.email === "string" &&
      typeof parsed.id === "string" &&
      typeof parsed.issuedAt === "number" &&
      typeof parsed.name === "string" &&
      ["admin", "manager", "reviewer"].includes(parsed.role)
    ) {
      return parsed;
    }
  } catch {
    return null;
  }

  return null;
}

function isExpired(issuedAt: number): boolean {
  const now = Math.floor(Date.now() / 1000);
  return now - issuedAt > SESSION_TTL_SECONDS;
}

function isSameValue(value: string, expected: string): boolean {
  const valueHash = createHash("sha256").update(value).digest();
  const expectedHash = createHash("sha256").update(expected).digest();
  return timingSafeEqual(valueHash, expectedHash);
}

function normalizeEmail(value: string): string {
  return value.trim().toLowerCase();
}
