import { randomBytes, pbkdf2Sync } from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const scriptPath = fileURLToPath(import.meta.url);
const webRoot = path.resolve(path.dirname(scriptPath), "..");
const registryPath = path.join(webRoot, "data", "manager", "managers.json");
const INVITE_HASH_ITERATIONS = 120_000;
const INVITE_HASH_BYTES = 32;

const args = parseArgs(process.argv.slice(2));
const email = args.email?.trim().toLowerCase();
const name = args.name?.trim();
const role = args.role?.trim() || "manager";
const invitedBy = args.invitedBy?.trim() || "project-owner";

if (!email || !name || !["admin", "manager", "reviewer"].includes(role)) {
  console.error("Usage: node scripts/create-manager-invite.mjs --email name@example.com --name \"Name\" [--role manager]");
  process.exit(1);
}

const registry = readRegistry();
if (registry.managers.some((manager) => manager.email.toLowerCase() === email)) {
  console.error(`A manager invite already exists for ${email}. Revoke or edit that record before creating another.`);
  process.exit(1);
}

const inviteCode = randomBytes(18).toString("base64url");
const salt = randomBytes(16).toString("hex");
const inviteCodeHash = pbkdf2Sync(inviteCode, salt, INVITE_HASH_ITERATIONS, INVITE_HASH_BYTES, "sha256").toString("hex");
const manager = {
  createdAt: new Date().toISOString(),
  email,
  id: `mgr_${randomBytes(8).toString("hex")}`,
  inviteCodeHash,
  inviteCodeSalt: salt,
  invitedBy,
  name,
  role,
  status: "active",
};

registry.managers.push(manager);
writeRegistry(registry);

console.log(`Manager invite created for ${name} <${email}>.`);
console.log(`Invite code: ${inviteCode}`);
console.log("Send this code privately. It is not stored in managers.json.");

function readRegistry() {
  if (!fs.existsSync(registryPath)) {
    return { managers: [], schemaVersion: 1 };
  }

  const payload = JSON.parse(fs.readFileSync(registryPath, "utf8"));
  return {
    managers: Array.isArray(payload.managers) ? payload.managers : [],
    schemaVersion: 1,
  };
}

function writeRegistry(registry) {
  fs.mkdirSync(path.dirname(registryPath), { recursive: true });
  const orderedRegistry = {
    schemaVersion: 1,
    managers: registry.managers,
  };
  fs.writeFileSync(registryPath, `${JSON.stringify(orderedRegistry, null, 2)}\n`, "utf8");
}

function parseArgs(values) {
  const parsed = {};
  for (let index = 0; index < values.length; index += 1) {
    const key = values[index];
    if (!key.startsWith("--")) {
      continue;
    }

    parsed[key.slice(2)] = values[index + 1] ?? "";
    index += 1;
  }

  return parsed;
}
