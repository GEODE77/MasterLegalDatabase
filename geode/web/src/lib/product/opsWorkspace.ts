import fs from "node:fs";
import path from "node:path";

import { CONTROL_PLANE_DIR, MASTER_MANIFEST_PATH } from "@/lib/paths";

type JsonObject = Record<string, unknown>;

const JSON_READ_RETRY_ATTEMPTS = 4;
const JSON_READ_RETRY_DELAY_MS = 30;

export type OpsSource = {
  id: string;
  name: string;
  layerIds: string[];
  localMarker: string | null;
  observedMarker: string | null;
  status: string;
  downloadStatus: string;
  nextStep: string;
};

export type OpsQueueItem = {
  id: string;
  sourceId: string;
  actionType: string;
  status: string;
  reason: string;
  command: string | null;
};

export type OpsLayer = {
  id: string;
  records: number;
  source: string;
  lastChecked: string | null;
  lastIngested: string | null;
  status: string;
};

export type OpsSummary = {
  generatedAt: string | null;
  overallStatus: string;
  newDataItems: number;
  manualReviewItems: number;
  watchedSources: number;
  queueItems: number;
  totalRecords: number;
  pushedState: string;
  nextRecommendation: string;
};

export type OpsWorkspaceData = {
  layers: OpsLayer[];
  queue: OpsQueueItem[];
  sources: OpsSource[];
  summary: OpsSummary;
};

export function getOpsWorkspaceData(): OpsWorkspaceData {
  const manifest = readJsonObject(MASTER_MANIFEST_PATH);
  const watcher = readJsonObject(path.join(CONTROL_PLANE_DIR, "SOURCE_UPDATE_WATCHER_DASHBOARD.json"));
  const queue = readJsonObject(path.join(CONTROL_PLANE_DIR, "SOURCE_UPDATE_DOWNLOAD_QUEUE.json"));
  const nextDownload = readJsonObject(path.join(CONTROL_PLANE_DIR, "NEXT_DOWNLOAD_DASHBOARD.json"));

  const layers = toLayers(manifest);
  const sources = toSources(watcher);
  const queueItems = toQueueItems(queue);
  const totalRecords = layers.reduce((sum, layer) => sum + layer.records, 0);
  const recommendation = objectValue(nextDownload, "overall_recommendation");

  return {
    layers,
    queue: queueItems,
    sources,
    summary: {
      generatedAt: stringValue(watcher, "generated_at"),
      overallStatus: stringValue(watcher, "status") ?? "unknown",
      newDataItems: numberValue(watcher, "new_data_items"),
      manualReviewItems: numberValue(watcher, "manual_review_items"),
      watchedSources: numberValue(watcher, "watch_items_total"),
      queueItems: queueItems.length,
      totalRecords,
      pushedState:
        "Branch is clean and pushed when the download closeout checklist reports Git as passed.",
      nextRecommendation:
        stringValue(recommendation, "reason") ??
        "Run the source update watcher before starting the next download.",
    },
  };
}

function toLayers(payload: JsonObject | null): OpsLayer[] {
  const layers = arrayValue(payload, "data_layers");
  return layers.map((layer) => ({
    id: stringValue(layer, "id") ?? "Unknown layer",
    records: numberValue(layer, "record_count"),
    source: stringValue(layer, "source") ?? "unknown",
    lastChecked: stringValue(layer, "last_checked"),
    lastIngested: stringValue(layer, "last_ingested"),
    status: stringValue(layer, "status") ?? "unknown",
  }));
}

function toSources(payload: JsonObject | null): OpsSource[] {
  const items = arrayValue(payload, "items");
  return items.map((item) => ({
    id: stringValue(item, "source_id") ?? "unknown",
    name: stringValue(item, "source_name") ?? stringValue(item, "source_id") ?? "Unknown source",
    layerIds: arrayValue(item, "layer_ids").map((value) => String(value)),
    localMarker: stringValue(item, "local_marker"),
    observedMarker: stringValue(item, "latest_observed_marker"),
    status: stringValue(item, "change_status") ?? "unknown",
    downloadStatus: stringValue(item, "download_status") ?? "unknown",
    nextStep: stringValue(item, "next_step") ?? "Review this source before acting.",
  }));
}

function toQueueItems(payload: JsonObject | null): OpsQueueItem[] {
  const items = arrayValue(payload, "items");
  return items.map((item) => ({
    id: stringValue(item, "queue_id") ?? "unknown",
    sourceId: stringValue(item, "source_id") ?? "unknown",
    actionType: stringValue(item, "action_type") ?? "review",
    status: stringValue(item, "status") ?? "unknown",
    reason: stringValue(item, "reason") ?? "Review required.",
    command: stringValue(item, "guarded_command"),
  }));
}

function readJsonObject(filePath: string): JsonObject | null {
  if (!fs.existsSync(filePath)) {
    return null;
  }

  for (let attempt = 1; attempt <= JSON_READ_RETRY_ATTEMPTS; attempt += 1) {
    try {
      const content = fs.readFileSync(filePath, "utf8").trim();
      if (!content) {
        throw new SyntaxError("empty JSON file");
      }

      const parsed = JSON.parse(content) as unknown;
      return isObject(parsed) ? parsed : null;
    } catch {
      if (attempt === JSON_READ_RETRY_ATTEMPTS) {
        return null;
      }

      sleep(JSON_READ_RETRY_DELAY_MS);
    }
  }

  return null;
}

function sleep(milliseconds: number): void {
  Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, milliseconds);
}

function objectValue(payload: unknown, key: string): JsonObject | null {
  if (!isObject(payload)) {
    return null;
  }

  const value = payload[key];
  return isObject(value) ? value : null;
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

function numberValue(payload: unknown, key: string): number {
  if (!isObject(payload)) {
    return 0;
  }

  const value = payload[key];
  return typeof value === "number" && Number.isFinite(value) ? value : 0;
}

function isObject(value: unknown): value is JsonObject {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
