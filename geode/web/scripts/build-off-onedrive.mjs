import { spawnSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const scriptPath = fileURLToPath(import.meta.url);
const sourceRoot = path.resolve(path.dirname(scriptPath), "..");
const repoRoot = path.resolve(sourceRoot, "..", "..");
const workRoot = path.resolve(os.tmpdir(), "geode-web-build-work");
const tempRoot = path.resolve(os.tmpdir());

if (!workRoot.startsWith(tempRoot)) {
  throw new Error(`Temporary build folder must stay under ${tempRoot}`);
}

const sourceNodeModules = path.join(sourceRoot, "node_modules");
if (!fs.existsSync(sourceNodeModules)) {
  throw new Error(`node_modules was not found at ${sourceNodeModules}`);
}

const excludedNames = new Set([
  ".next",
  ".next-build",
  ".next-codex-authority",
  ".next-codex-build",
  ".next-codex-operational",
  ".next-codex-reasons",
  ".next-codex-step2",
  ".next-codex-verify",
  "__pycache__",
  "node_modules",
  "next-build.err.log",
  "next-build.out.log",
  "tsconfig.tsbuildinfo",
]);

function shouldCopy(source) {
  const relativePath = path.relative(sourceRoot, source);
  const parts = relativePath.split(path.sep);

  if (parts.includes("node_modules")) {
    return false;
  }

  if (parts[0] === "data" && parts[1] === "personalization" && parts[2] === "users") {
    return false;
  }

  return !parts.some((part) => excludedNames.has(part));
}

fs.rmSync(workRoot, { force: true, recursive: true });
fs.mkdirSync(workRoot, { recursive: true });
fs.cpSync(sourceRoot, workRoot, {
  filter: shouldCopy,
  recursive: true,
});

const tempNodeModules = path.join(workRoot, "node_modules");
fs.symlinkSync(sourceNodeModules, tempNodeModules, process.platform === "win32" ? "junction" : "dir");

const result = spawnSync(
  process.execPath,
  ["node_modules/next/dist/bin/next", "build", "--debug"],
  {
    cwd: workRoot,
    env: {
      ...process.env,
      GEODE_REPOSITORY_ROOT: repoRoot,
      NEXT_TELEMETRY_DISABLED: "1",
    },
    stdio: "inherit",
  },
);

if (result.error) {
  throw result.error;
}

process.exit(result.status ?? 1);
