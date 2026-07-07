import { spawnSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";

import { CONTROL_PLANE_DIR, GEODE_READ_INDEX_PATH, MASTER_MANIFEST_PATH, REPOSITORY_ROOT } from "@/lib/paths";
import type { RegulationSearchResult } from "@/lib/search/types";

export type GeodeSearchResult = RegulationSearchResult & {
  layer?: string;
  entityType?: string;
};

type JsonObject = Record<string, unknown>;

let freshnessByLayer: Map<string, { detail: string; status: string }> | null = null;

export function searchGeodeIndex(query: string, limit = 8): GeodeSearchResult[] {
  const python = process.env.PYTHON ?? "python";
  const pythonPath = [REPOSITORY_ROOT, process.env.PYTHONPATH].filter(Boolean).join(path.delimiter);
  const result = spawnSync(
    python,
    [
      "-m",
      "geode.web.query_index",
      "--database",
      GEODE_READ_INDEX_PATH,
      "--query",
      query,
      "--limit",
      String(limit),
    ],
    {
      cwd: REPOSITORY_ROOT,
      encoding: "utf8",
      env: {
        ...process.env,
        PYTHONPATH: pythonPath,
      },
      maxBuffer: 1024 * 1024 * 4,
    },
  );

  if (result.error) {
    throw result.error;
  }

  if (result.status !== 0) {
    throw new Error(result.stderr || "Geode read-index query failed.");
  }

  const results = JSON.parse(result.stdout) as GeodeSearchResult[];
  return results.map((searchResult) => enrichSearchResult(query, searchResult));
}

function enrichSearchResult(query: string, result: GeodeSearchResult): GeodeSearchResult {
  const freshness = freshnessForLayer(result.layer);
  const matchReasons = result.matchReasons?.length
    ? result.matchReasons
    : [whyResultMatched(query, result)];

  return {
    ...result,
    explanation: whyResultMatched(query, result),
    freshnessDetail: freshness.detail,
    freshnessStatus: freshness.status,
    matchReasons,
  };
}

function freshnessForLayer(layer: string | undefined): { detail: string; status: string } {
  if (!layer) {
    return { detail: "Layer freshness is not available for this result.", status: "unknown" };
  }

  return freshnessMap().get(layer) ?? {
    detail: "No freshness marker is recorded for this layer.",
    status: "unknown",
  };
}

function freshnessMap(): Map<string, { detail: string; status: string }> {
  if (freshnessByLayer) {
    return freshnessByLayer;
  }

  const next = new Map<string, { detail: string; status: string }>();
  const manifest = readJsonObject(MASTER_MANIFEST_PATH);
  const watcher = readJsonObject(path.join(CONTROL_PLANE_DIR, "SOURCE_UPDATE_WATCHER_DASHBOARD.json"));

  for (const layer of arrayValue(manifest, "data_layers")) {
    const layerId = stringValue(layer, "id");
    if (!layerId) {
      continue;
    }

    next.set(layerId, {
      detail: `Last checked: ${stringValue(layer, "last_checked") ?? "unknown"}. Last ingested: ${stringValue(layer, "last_ingested") ?? "unknown"}.`,
      status: stringValue(layer, "status") ?? "unknown",
    });
  }

  for (const source of arrayValue(watcher, "items")) {
    const status = stringValue(source, "change_status") ?? "unknown";
    const detail = stringValue(source, "next_step") ?? stringValue(source, "evidence") ?? "Source freshness needs review.";
    for (const layerId of arrayValue(source, "layer_ids")) {
      next.set(String(layerId), { detail, status });
    }
  }

  freshnessByLayer = next;
  return next;
}

function whyResultMatched(query: string, result: GeodeSearchResult): string {
  const normalizedQuery = query.toLowerCase();
  const normalizedCitation = result.citation.toLowerCase();
  const normalizedTitle = result.title.toLowerCase();

  if (normalizedCitation && normalizedQuery.includes(normalizedCitation)) {
    return "Returned because the query directly matched the citation.";
  }

  if (normalizedQuery.split(/\s+/).some((token) => token.length >= 3 && normalizedTitle.includes(token))) {
    return "Returned because the query matched the authority title or topic.";
  }

  if (result.relationshipCount) {
    return "Returned because this authority has related statutes, rules, or source links.";
  }

  return "Returned because it matched the local Geode search index.";
}

function readJsonObject(filePath: string): JsonObject | null {
  if (!fs.existsSync(filePath)) {
    return null;
  }

  try {
    const parsed = JSON.parse(fs.readFileSync(filePath, "utf8")) as unknown;
    return isObject(parsed) ? parsed : null;
  } catch {
    return null;
  }
}

function arrayValue(payload: unknown, key: string): unknown[] {
  if (!isObject(payload)) {
    return [];
  }

  const value = payload[key];
  return Array.isArray(value) ? value : [];
}

function stringValue(payload: unknown, key: string): string | null {
  if (!isObject(payload)) {
    return null;
  }

  const value = payload[key];
  return typeof value === "string" && value.trim() ? value : null;
}

function isObject(value: unknown): value is JsonObject {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
