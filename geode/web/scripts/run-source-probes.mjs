import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const scriptPath = fileURLToPath(import.meta.url);
const webRoot = path.resolve(path.dirname(scriptPath), "..");
const repoRoot = path.resolve(webRoot, "..", "..");
const sourceRegistryPath = path.join(repoRoot, "_CONTROL_PLANE", "SOURCE_REGISTRY.json");
const outputPath = path.join(webRoot, "data", "manager", "source_probe_report.json");

const sources = JSON.parse(fs.readFileSync(sourceRegistryPath, "utf8"));
const generatedAt = new Date().toISOString();
const results = [];

for (const source of sources) {
  const url = source.url ?? source.api_url;
  if (!url) {
    results.push(toResult(source, "not_configured", "No public URL is registered.", null));
    continue;
  }

  try {
    const response = await fetch(url, { method: "HEAD", redirect: "follow", signal: AbortSignal.timeout(8000) });
    results.push(toResult(source, response.ok ? "reachable" : "review", `HTTP ${response.status}`, response.url));
  } catch (headError) {
    try {
      const response = await fetch(url, { method: "GET", redirect: "follow", signal: AbortSignal.timeout(8000) });
      results.push(toResult(source, response.ok ? "reachable" : "review", `GET HTTP ${response.status}`, response.url));
    } catch (getError) {
      results.push(
        toResult(
          source,
          "blocked",
          getError instanceof Error ? getError.message : "Probe failed.",
          url,
        ),
      );
    }
  }
}

const report = {
  generatedAt,
  results,
  schemaVersion: 1,
  summary: {
    blocked: results.filter((result) => result.status === "blocked").length,
    reachable: results.filter((result) => result.status === "reachable").length,
    review: results.filter((result) => result.status === "review").length,
    total: results.length,
  },
};

fs.mkdirSync(path.dirname(outputPath), { recursive: true });
fs.writeFileSync(outputPath, `${JSON.stringify(report, null, 2)}\n`, "utf8");
console.log(`Source probe report written to ${outputPath}`);

function toResult(source, status, detail, finalUrl) {
  return {
    detail,
    finalUrl,
    sourceId: source.source_id,
    sourceName: source.source_name,
    status,
    url: source.url ?? source.api_url ?? null,
  };
}
