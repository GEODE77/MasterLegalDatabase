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
  ageLabel: string;
  firstSeen: string | null;
  managerNote: string;
  officialSourceConfirmation: string;
  owner: string;
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
  managerSessionSecretConfigured: boolean;
  publicationReady: boolean;
};

export type OpsControl = {
  detail: string;
  label: string;
  status: string;
};

export type OpsCalendarItem = {
  cadence: string;
  label: string;
  nextCheck: string;
  sourceId: string;
};

export type OpsQualityArea = {
  area: string;
  detail: string;
  status: string;
};

export type OpsWorkspaceData = {
  calendar: OpsCalendarItem[];
  closeout: OpsControl[];
  downloadGate: OpsControl[];
  knownBlockers: OpsControl[];
  layers: OpsLayer[];
  pipelineAudit: OpsQualityArea[];
  publicBoundary: OpsControl[];
  qualityAreas: OpsQualityArea[];
  queue: OpsQueueItem[];
  repairProgress: OpsControl[];
  sources: OpsSource[];
  summary: OpsSummary;
  taskInbox: OpsControl[];
  trustControls: OpsControl[];
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
    calendar: toCalendarItems(sources),
    closeout: toCloseoutControls(queueItems),
    downloadGate: toDownloadGateControls(sources, queueItems),
    knownBlockers: toKnownBlockers(queueItems),
    layers,
    pipelineAudit: toPipelineAudit(layers),
    publicBoundary: toPublicBoundaryControls(),
    qualityAreas: toQualityAreas(layers, queueItems),
    queue: queueItems,
    repairProgress: toRepairProgress(queueItems),
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
      managerSessionSecretConfigured: Boolean(process.env.GEODE_MANAGER_SESSION_SECRET?.trim()),
      publicationReady: queueItems.length === 0 && numberValue(watcher, "new_data_items") === 0,
    },
    taskInbox: toTaskInbox(sources, queueItems),
    trustControls: toTrustControls(),
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
    ageLabel: queueAgeLabel(stringValue(item, "first_seen_at") ?? stringValue(item, "created_at")),
    id: stringValue(item, "queue_id") ?? "unknown",
    sourceId: stringValue(item, "source_id") ?? "unknown",
    actionType: stringValue(item, "action_type") ?? "review",
    status: stringValue(item, "status") ?? "unknown",
    reason: stringValue(item, "reason") ?? "Review required.",
    command: stringValue(item, "guarded_command"),
    firstSeen: stringValue(item, "first_seen_at") ?? stringValue(item, "created_at"),
    managerNote:
      stringValue(item, "manager_note") ??
      "No manager note has been added yet. Add reviewer context before repair intake.",
    officialSourceConfirmation:
      stringValue(item, "official_source_confirmation") ??
      "Official source still needs reviewer confirmation before intake.",
    owner: stringValue(item, "owner") ?? "Unassigned",
  }));
}

function toDownloadGateControls(sources: OpsSource[], queue: OpsQueueItem[]): OpsControl[] {
  const sourcesWithNewMaterial = sources.filter((source) => source.status !== "no_change_detected").length;
  return [
    {
      detail: sourcesWithNewMaterial
        ? `${sourcesWithNewMaterial} source records need review before a broad download.`
        : "No source has reported new material in the current watcher data.",
      label: "Source change review",
      status: sourcesWithNewMaterial ? "review" : "clear",
    },
    {
      detail: queue.length
        ? `${queue.length} queue items remain open.`
        : "No pending download queue items are listed.",
      label: "Pending downloads",
      status: queue.length ? "blocked" : "clear",
    },
    {
      detail: "Run the secret safety check and confirm the Git branch is clean before download commit.",
      label: "Workspace safety",
      status: "required",
    },
  ];
}

function toCloseoutControls(queue: OpsQueueItem[]): OpsControl[] {
  return [
    { detail: "Run secret safety before staging and after staging.", label: "No secrets", status: "required" },
    {
      detail: queue.length ? `${queue.length} pending items still require review.` : "No pending downloads listed.",
      label: "No pending downloads",
      status: queue.length ? "review" : "clear",
    },
    { detail: "Refresh the manager dashboard after every source refresh.", label: "Dashboard updated", status: "required" },
    { detail: "Commit and push only after the safety checks pass.", label: "Git pushed", status: "required" },
  ];
}

function toRepairProgress(queue: OpsQueueItem[]): OpsControl[] {
  const modernLegiscan = queue.filter((item) => item.sourceId.toLowerCase().includes("legiscan"));
  return [
    {
      detail: modernLegiscan.length
        ? `${modernLegiscan.length} LegiScan repair items remain in the active queue.`
        : "No active LegiScan repair items are in the current queue.",
      label: "Modern LegiScan repairs",
      status: modernLegiscan.length ? "review" : "clear",
    },
    {
      detail: "Official replacement files must be confirmed before guarded repair intake.",
      label: "Official replacement files",
      status: modernLegiscan.length ? "needed" : "clear",
    },
  ];
}

function toKnownBlockers(queue: OpsQueueItem[]): OpsControl[] {
  const blockers = queue.filter((item) => item.status.includes("blocked") || item.reason.toLowerCase().includes("blocked"));
  return blockers.length
    ? blockers.map((item) => ({
        detail: item.reason,
        label: item.id,
        status: "known blocker",
      }))
    : [{ detail: "No known blockers are listed in the current queue.", label: "Known blockers", status: "clear" }];
}

function toTaskInbox(sources: OpsSource[], queue: OpsQueueItem[]): OpsControl[] {
  const changedSources = sources.filter((source) => source.status !== "no_change_detected");
  return [
    ...queue.slice(0, 5).map((item) => ({
      detail: `${item.owner}: ${item.reason}`,
      label: item.id,
      status: item.status,
    })),
    ...changedSources.slice(0, 3).map((source) => ({
      detail: source.nextStep,
      label: source.name,
      status: source.status,
    })),
  ];
}

function toCalendarItems(sources: OpsSource[]): OpsCalendarItem[] {
  return sources.slice(0, 8).map((source, index) => ({
    cadence: source.status === "no_change_detected" ? "weekly" : "before next download",
    label: source.name,
    nextCheck: `T+${index + 1} review window`,
    sourceId: source.id,
  }));
}

function toPipelineAudit(layers: OpsLayer[]): OpsQualityArea[] {
  return layers.map((layer) => ({
    area: layer.id,
    detail: `${layer.records.toLocaleString("en-US")} records. Source: ${layer.source}. Last checked: ${layer.lastChecked ?? "unknown"}.`,
    status: layer.status,
  }));
}

function toQualityAreas(layers: OpsLayer[], queue: OpsQueueItem[]): OpsQualityArea[] {
  const totalRecords = layers.reduce((sum, layer) => sum + layer.records, 0);
  const unresolvedFailures = queue.length;
  const confidence = totalRecords ? Math.max(55, 95 - unresolvedFailures * 3) : 0;
  return [
    {
      area: "Data confidence score",
      detail: `${confidence}% estimated from record coverage and unresolved queue items.`,
      status: unresolvedFailures ? "review" : "strong",
    },
    {
      area: "Crosswalk health",
      detail: "Relationship files are surfaced for statute, regulation, bill, agency, and rulemaking review.",
      status: "visible",
    },
    {
      area: "Pipeline error grouping",
      detail: queue.length ? `${queue.length} active issues grouped by source queue.` : "No active queue issues.",
      status: queue.length ? "review" : "clear",
    },
  ];
}

function toTrustControls(): OpsControl[] {
  return [
    { detail: "Secret safety runs before commit and push.", label: "Secret safety", status: "active" },
    { detail: "Warn before staging tokens, keys, or private records.", label: "Sensitive files", status: "active" },
    { detail: "Manager-only and temporary files are excluded from public release.", label: "Public boundary", status: "active" },
    { detail: "_RAW_ARCHIVE remains write-once source truth.", label: "Raw archive", status: "protected" },
  ];
}

function toPublicBoundaryControls(): OpsControl[] {
  return [
    { detail: "Public users can search and browse without signing in.", label: "Public access", status: "open" },
    { detail: "Manager tools remain behind named manager verification.", label: "Manager tools", status: "restricted" },
    { detail: "Audit exports are admin-only and not public assets.", label: "Audit files", status: "restricted" },
  ];
}

function queueAgeLabel(firstSeen: string | null): string {
  if (!firstSeen) {
    return "age unknown";
  }

  const timestamp = Date.parse(firstSeen);
  if (!Number.isFinite(timestamp)) {
    return "age unknown";
  }

  const days = Math.max(0, Math.floor((Date.now() - timestamp) / 86_400_000));
  return `${days} days open`;
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
