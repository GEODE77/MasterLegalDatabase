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

if (!email || !name) {
  console.error("Usage: node scripts/create-first-admin.mjs --email owner@example.com --name \"Owner Name\"");
  process.exit(1);
}

const registry = readRegistry();
if (registry.managers.length) {
  console.error("First-admin setup is locked because the manager registry already contains accounts.");
  process.exit(1);
}

const inviteCode = randomBytes(18).toString("base64url");
const salt = randomBytes(16).toString("hex");
const inviteCodeHash = pbkdf2Sync(inviteCode, salt, INVITE_HASH_ITERATIONS, INVITE_HASH_BYTES, "sha256").toString("hex");

registry.managers.push({
  createdAt: new Date().toISOString(),
  email,
  id: `mgr_${randomBytes(8).toString("hex")}`,
  inviteCodeHash,
  inviteCodeSalt: salt,
  invitedBy: "first-admin-setup",
  name,
  role: "admin",
  status: "active",
});
writeRegistry(registry);

console.log(`First admin invite created for ${name} <${email}>.`);
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
  fs.writeFileSync(
    registryPath,
    `${JSON.stringify({ managers: registry.managers, schemaVersion: 1 }, null, 2)}\n`,
    "utf8",
  );
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
