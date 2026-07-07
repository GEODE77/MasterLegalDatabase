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
const MANAGER_ROLES = ["admin", "manager", "reviewer"] as const;

type ManagerRegistry = {
  managers: ManagerRecord[];
  schemaVersion: number;
};

export type ManagerRole = (typeof MANAGER_ROLES)[number];

export type ManagerRecord = {
  createdAt: string;
  email: string;
  id: string;
  inviteCodeHash: string;
  inviteCodeSalt: string;
  invitedBy: string;
  name: string;
  revokedAt?: string;
  role: ManagerRole;
  status: "active" | "revoked";
};

export type ManagerSession = {
  email: string;
  id: string;
  issuedAt: number;
  name: string;
  role: ManagerRole;
};

export type ManagerAccountSummary = {
  createdAt: string;
  email: string;
  eventCount: number;
  id: string;
  invitedBy: string;
  lastEventAt: string | null;
  name: string;
  revokedAt?: string;
  role: ManagerRole;
  status: ManagerRecord["status"];
};

type ManagerHistoryEvent = {
  action: string;
  actorEmail?: string;
  actorId?: string;
  actorName?: string;
  managerEmail: string;
  managerId: string;
  managerName: string;
  occurredAt: string;
};

export type ManagerAuditEvent = ManagerHistoryEvent;

type CreateManagerInviteInput = {
  email: string;
  name: string;
  role: ManagerRole;
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

export function listManagerAccounts(): ManagerAccountSummary[] {
  const events = readManagerHistory();
  return readManagerRegistry()
    .managers.map((manager) => {
      const managerEvents = events.filter((event) => event.managerId === manager.id);
      const lastEvent = managerEvents.at(-1);
      return {
        createdAt: manager.createdAt,
        email: manager.email,
        eventCount: managerEvents.length,
        id: manager.id,
        invitedBy: manager.invitedBy,
        lastEventAt: lastEvent?.occurredAt ?? null,
        name: manager.name,
        revokedAt: manager.revokedAt,
        role: manager.role,
        status: manager.status,
      };
    })
    .sort((left, right) => left.email.localeCompare(right.email));
}

export function listManagerAuditEvents(limit = 20): ManagerAuditEvent[] {
  return readManagerHistory().slice(-limit).reverse();
}

export function createManagerInvite(
  input: CreateManagerInviteInput,
  actor: ManagerSession,
): { inviteCode: string; manager: ManagerAccountSummary } {
  const email = normalizeEmail(input.email);
  const name = input.name.trim();
  if (!email || !name || !isManagerRole(input.role)) {
    throw new Error("A manager invite needs a name, email, and valid role.");
  }

  const registry = readManagerRegistry();
  if (registry.managers.some((manager) => normalizeEmail(manager.email) === email)) {
    throw new Error("A manager account already exists for that email.");
  }

  const inviteCode = randomBytes(18).toString("base64url");
  const { hash, salt } = hashInviteCode(inviteCode);
  const occurredAt = new Date().toISOString();
  const manager: ManagerRecord = {
    createdAt: occurredAt,
    email,
    id: `mgr_${randomBytes(8).toString("hex")}`,
    inviteCodeHash: hash,
    inviteCodeSalt: salt,
    invitedBy: actor.email,
    name,
    role: input.role,
    status: "active",
  };

  registry.managers.push(manager);
  writeManagerRegistry(registry);
  appendManagerHistory({
    action: "manager_invited",
    actorEmail: actor.email,
    actorId: actor.id,
    actorName: actor.name,
    managerEmail: manager.email,
    managerId: manager.id,
    managerName: manager.name,
    occurredAt,
  });

  return {
    inviteCode,
    manager: toManagerSummary(manager, 1, occurredAt),
  };
}

export function revokeManagerAccount(managerId: string, actor: ManagerSession): ManagerAccountSummary {
  const registry = readManagerRegistry();
  const manager = registry.managers.find((record) => record.id === managerId);
  if (!manager) {
    throw new Error("Manager account was not found.");
  }
  if (manager.id === actor.id) {
    throw new Error("Admins cannot revoke their own active session.");
  }
  if (manager.status === "revoked") {
    return toManagerSummary(manager);
  }

  manager.status = "revoked";
  manager.revokedAt = new Date().toISOString();
  writeManagerRegistry(registry);
  appendManagerHistory({
    action: "manager_revoked",
    actorEmail: actor.email,
    actorId: actor.id,
    actorName: actor.name,
    managerEmail: manager.email,
    managerId: manager.id,
    managerName: manager.name,
    occurredAt: manager.revokedAt,
  });

  return toManagerSummary(manager, undefined, manager.revokedAt);
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

function writeManagerRegistry(registry: ManagerRegistry): void {
  fs.mkdirSync(MANAGER_DATA_DIR, { recursive: true });
  const temporaryPath = `${MANAGER_REGISTRY_PATH}.tmp`;
  fs.writeFileSync(
    temporaryPath,
    `${JSON.stringify({ managers: registry.managers, schemaVersion: 1 }, null, 2)}\n`,
    "utf8",
  );
  fs.renameSync(temporaryPath, MANAGER_REGISTRY_PATH);
}

function readManagerHistory(): ManagerAuditEvent[] {
  if (!fs.existsSync(MANAGER_HISTORY_PATH)) {
    return [];
  }

  return fs
    .readFileSync(MANAGER_HISTORY_PATH, "utf8")
    .split(/\r?\n/)
    .filter(Boolean)
    .flatMap((line) => {
      try {
        return [JSON.parse(line) as ManagerAuditEvent];
      } catch {
        return [];
      }
    });
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
      isManagerRole(parsed.role)
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

function isManagerRole(value: unknown): value is ManagerRole {
  return typeof value === "string" && MANAGER_ROLES.includes(value as ManagerRole);
}

function toManagerSummary(
  manager: ManagerRecord,
  eventCount = 0,
  lastEventAt: string | null = null,
): ManagerAccountSummary {
  return {
    createdAt: manager.createdAt,
    email: manager.email,
    eventCount,
    id: manager.id,
    invitedBy: manager.invitedBy,
    lastEventAt,
    name: manager.name,
    revokedAt: manager.revokedAt,
    role: manager.role,
    status: manager.status,
  };
}
