import fs from "node:fs";
import path from "node:path";

import { CONTROL_PLANE_DIR, MASTER_MANIFEST_PATH, REPOSITORY_ROOT } from "@/lib/paths";
import { readQueueOverrides } from "@/lib/manager/operationOverrides";

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

export type OpsQualityStatusLayer = {
  id: string;
  label: string;
  recordCount: number;
  qualityStage: string;
  localUseStatus: string;
  externalRelianceStatus: string;
  officialRefreshRequired: boolean;
  reasons: string[];
  nextActions: string[];
};

export type OpsQualityStatus = {
  agentGuidance: string;
  externalRelianceReady: boolean;
  generatedAt: string | null;
  layerSummary: Record<string, number>;
  layers: OpsQualityStatusLayer[];
  localSystemUsable: boolean;
  openSystemBlockers: string[];
  overallQualityStage: string;
};

export type OpsCrosswalkReview = {
  file: string;
  lowConfidence: number;
  missingEvidence: number;
  relationships: number;
  status: string;
};

export type OpsWorkspaceData = {
  calendar: OpsCalendarItem[];
  closeout: OpsControl[];
  crosswalkReviews: OpsCrosswalkReview[];
  downloadGate: OpsControl[];
  knownBlockers: OpsControl[];
  layers: OpsLayer[];
  pipelineAudit: OpsQualityArea[];
  publicBoundary: OpsControl[];
  qualityAreas: OpsQualityArea[];
  qualityStatus: OpsQualityStatus;
  queue: OpsQueueItem[];
  repairProgress: OpsControl[];
  sourceProbeControls: OpsControl[];
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
  const qualityStatus = readJsonObject(path.join(CONTROL_PLANE_DIR, "QUALITY_STATUS.json"));
  const probeReport = readJsonObject(
    path.join(REPOSITORY_ROOT, "geode", "web", "data", "manager", "source_probe_report.json"),
  );

  const layers = toLayers(manifest);
  const sources = toSources(watcher);
  const queueItems = toQueueItems(queue);
  const totalRecords = layers.reduce((sum, layer) => sum + layer.records, 0);
  const recommendation = objectValue(nextDownload, "overall_recommendation");

  return {
    calendar: toCalendarItems(sources),
    closeout: toCloseoutControls(queueItems),
    crosswalkReviews: toCrosswalkReviews(),
    downloadGate: toDownloadGateControls(sources, queueItems),
    knownBlockers: toKnownBlockers(queueItems),
    layers,
    pipelineAudit: toPipelineAudit(layers),
    publicBoundary: toPublicBoundaryControls(),
    qualityAreas: toQualityAreas(layers, queueItems),
    qualityStatus: toQualityStatus(qualityStatus),
    queue: queueItems,
    repairProgress: toRepairProgress(queueItems),
    sourceProbeControls: toSourceProbeControls(probeReport),
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
    trustControls: toTrustControls(Boolean(process.env.GEODE_MANAGER_SESSION_SECRET?.trim())),
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
  const generatedAt = stringValue(payload, "generated_at");
  const overrides = readQueueOverrides();
  return items.map((item) => {
    const queueId = stringValue(item, "queue_id") ?? "unknown";
    const override = overrides[queueId];
    const firstSeen = stringValue(item, "first_seen_at") ?? stringValue(item, "created_at") ?? generatedAt;
    return {
      ageLabel: queueAgeLabel(firstSeen),
      id: queueId,
      sourceId: stringValue(item, "source_id") ?? "unknown",
      actionType: stringValue(item, "action_type") ?? "review",
      status: override?.status ?? stringValue(item, "status") ?? "unknown",
      reason: stringValue(item, "reason") ?? "Review required.",
      command: stringValue(item, "guarded_command"),
      firstSeen,
      managerNote:
        override?.managerNote ??
        stringValue(item, "manager_note") ??
        "No manager note has been added yet. Add reviewer context before repair intake.",
      officialSourceConfirmation:
        override?.officialSourceConfirmation ??
        stringValue(item, "official_source_confirmation") ??
        "Official source still needs reviewer confirmation before intake.",
      owner: override?.owner ?? stringValue(item, "owner") ?? "Unassigned",
    };
  });
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
  const schedule = readJsonObject(
    path.join(REPOSITORY_ROOT, "geode", "web", "data", "manager", "source_automation_schedule.json"),
  );
  const scheduledItems = arrayValue(schedule, "checks");
  return sources.slice(0, 8).map((source, index) => {
    const scheduled = scheduledItems.find(
      (item) => isObject(item) && stringValue(item, "sourceId") === source.id,
    );
    return {
    cadence: source.status === "no_change_detected" ? "weekly" : "before next download",
    label: source.name,
      nextCheck:
        (isObject(scheduled) ? stringValue(scheduled, "nextAction") : null) ??
        `T+${index + 1} review window`,
    sourceId: source.id,
    };
  });
}

function toPipelineAudit(layers: OpsLayer[]): OpsQualityArea[] {
  return layers.map((layer) => ({
    area: layer.id,
    detail: `${layer.records.toLocaleString("en-US")} records. ${countLayerFiles(layer.id)} readable files. Source: ${layer.source}. Last checked: ${layer.lastChecked ?? "unknown"}.`,
    status: layer.status,
  }));
}

function toQualityAreas(layers: OpsLayer[], queue: OpsQueueItem[]): OpsQualityArea[] {
  const totalRecords = layers.reduce((sum, layer) => sum + layer.records, 0);
  const unresolvedFailures = queue.length;
  const staleLayers = layers.filter((layer) => layer.status !== "current").length;
  const crosswalkReviews = toCrosswalkReviews();
  const relationshipIssues = crosswalkReviews.reduce(
    (sum, item) => sum + item.lowConfidence + item.missingEvidence,
    0,
  );
  const confidence = totalRecords
    ? Math.max(50, 98 - unresolvedFailures * 4 - staleLayers * 3 - Math.min(relationshipIssues, 20))
    : 0;
  return [
    {
      area: "Data confidence score",
      detail: `${confidence}% estimated from record coverage and unresolved queue items.`,
      status: unresolvedFailures ? "review" : "strong",
    },
    {
      area: "Crosswalk health",
      detail: `${crosswalkReviews.length} crosswalk files checked. ${relationshipIssues} relationship issues need review.`,
      status: relationshipIssues ? "review" : "strong",
    },
    {
      area: "Pipeline error grouping",
      detail: queue.length ? `${queue.length} active issues grouped by source queue.` : "No active queue issues.",
      status: queue.length ? "review" : "clear",
    },
  ];
}

function toQualityStatus(payload: JsonObject | null): OpsQualityStatus {
  const layers = arrayValue(payload, "layers")
    .filter(isObject)
    .map((layer) => ({
      externalRelianceStatus: stringValue(layer, "external_reliance_status") ?? "unknown",
      id: stringValue(layer, "layer_id") ?? "unknown",
      label: stringValue(layer, "label") ?? stringValue(layer, "layer_id") ?? "Unknown layer",
      localUseStatus: stringValue(layer, "local_use_status") ?? "unknown",
      nextActions: arrayValue(layer, "next_actions").map((value) => String(value)),
      officialRefreshRequired: booleanValue(layer, "official_refresh_required"),
      qualityStage: stringValue(layer, "quality_stage") ?? "unknown",
      reasons: arrayValue(layer, "status_reasons").map((value) => String(value)),
      recordCount: numberValue(layer, "record_count"),
    }));

  return {
    agentGuidance:
      stringValue(payload, "agent_guidance") ??
      "Quality status has not been generated yet. Rebuild the source quality operating layer.",
    externalRelianceReady: booleanValue(payload, "external_reliance_ready"),
    generatedAt: stringValue(payload, "generated_at"),
    layerSummary: recordNumberValue(objectValue(payload, "layer_summary")),
    layers,
    localSystemUsable: booleanValue(payload, "local_system_usable"),
    openSystemBlockers: arrayValue(payload, "open_system_blockers").map((value) => String(value)),
    overallQualityStage: stringValue(payload, "overall_quality_stage") ?? "unknown",
  };
}

function toCrosswalkReviews(): OpsCrosswalkReview[] {
  const crosswalkDir = path.join(REPOSITORY_ROOT, "_CROSSWALKS");
  if (!fs.existsSync(crosswalkDir)) {
    return [];
  }

  return fs
    .readdirSync(crosswalkDir)
    .filter((file) => file.endsWith(".jsonl"))
    .sort()
    .map((file) => {
      const records = readJsonl(path.join(crosswalkDir, file));
      const missingEvidence = records.filter((record) => !stringValue(record, "source_evidence")).length;
      const lowConfidence = records.filter((record) => numberValue(record, "confidence") > 0 && numberValue(record, "confidence") < 0.6).length;
      const issueCount = missingEvidence + lowConfidence;
      return {
        file,
        lowConfidence,
        missingEvidence,
        relationships: records.length,
        status: issueCount ? "review" : "strong",
      };
    });
}

function toTrustControls(managerSecretConfigured: boolean): OpsControl[] {
  return [
    { detail: "Secret safety runs before commit and push.", label: "Secret safety", status: "active" },
    {
      detail: managerSecretConfigured
        ? "GEODE_MANAGER_SESSION_SECRET is configured for this runtime."
        : "Set GEODE_MANAGER_SESSION_SECRET before public production launch.",
      label: "Manager session secret",
      status: managerSecretConfigured ? "configured" : "missing",
    },
    { detail: "Warn before staging tokens, keys, or private records.", label: "Sensitive files", status: "active" },
    { detail: "Manager-only and temporary files are excluded from public release.", label: "Public boundary", status: "active" },
    { detail: "_RAW_ARCHIVE remains write-once source truth.", label: "Raw archive", status: "protected" },
  ];
}

function toSourceProbeControls(probeReport: JsonObject | null): OpsControl[] {
  const summary = objectValue(probeReport, "summary");
  if (!summary) {
    return [
      {
        detail: "Run npm run source:probe from geode/web to refresh the live source probe report.",
        label: "Live source probes",
        status: "ready",
      },
    ];
  }

  return [
    {
      detail: `${numberValue(summary, "reachable")} reachable, ${numberValue(summary, "review")} need review, ${numberValue(summary, "blocked")} blocked.`,
      label: "Live source probes",
      status: "reported",
    },
    {
      detail: `Last generated: ${stringValue(probeReport, "generatedAt") ?? "unknown"}.`,
      label: "Probe report",
      status: "current",
    },
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

function readJsonl(filePath: string): JsonObject[] {
  if (!fs.existsSync(filePath)) {
    return [];
  }

  return fs
    .readFileSync(filePath, "utf8")
    .split(/\r?\n/)
    .filter(Boolean)
    .flatMap((line) => {
      try {
        const parsed = JSON.parse(line) as unknown;
        return isObject(parsed) ? [parsed] : [];
      } catch {
        return [];
      }
    });
}

function countLayerFiles(layerId: string): number {
  const layerPath = path.join(REPOSITORY_ROOT, layerId);
  if (!fs.existsSync(layerPath)) {
    return 0;
  }

  let count = 0;
  const stack = [layerPath];
  while (stack.length) {
    const current = stack.pop();
    if (!current) {
      continue;
    }

    for (const entry of fs.readdirSync(current, { withFileTypes: true })) {
      const entryPath = path.join(current, entry.name);
      if (entry.isDirectory()) {
        stack.push(entryPath);
      } else if (/\.(json|jsonl|md)$/i.test(entry.name)) {
        count += 1;
      }
    }
  }

  return count;
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

function booleanValue(payload: unknown, key: string): boolean {
  if (!isObject(payload)) {
    return false;
  }

  return payload[key] === true;
}

function recordNumberValue(payload: JsonObject | null): Record<string, number> {
  if (!payload) {
    return {};
  }

  return Object.fromEntries(
    Object.entries(payload).filter(
      (entry): entry is [string, number] =>
        typeof entry[1] === "number" && Number.isFinite(entry[1]),
    ),
  );
}

function isObject(value: unknown): value is JsonObject {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
