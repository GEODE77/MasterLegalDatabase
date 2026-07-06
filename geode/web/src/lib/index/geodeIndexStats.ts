import fs from "node:fs";
import path from "node:path";

import { MASTER_MANIFEST_PATH, REPOSITORY_ROOT } from "@/lib/paths";
import { getRegulationCorpusStats } from "@/lib/search/searchRegulations";

export type GeodeIndexPoint = {
  date: string;
  value: number;
};

export type GeodeIndexVariant = {
  label: string;
  value: number;
};

export type GeodeIndexStats = {
  agencyCount: number;
  count: number;
  lastUpdated: string | null;
  points: GeodeIndexPoint[];
  variants: GeodeIndexVariant[];
};

type ManifestLayer = {
  id?: string;
  last_checked?: string;
  last_ingested?: string;
  record_count?: number;
};

type Manifest = {
  data_layers?: ManifestLayer[];
};

type UpdateLogRecord = {
  event_type?: string;
  layer?: string | null;
  timestamp?: string;
};

const UPDATE_LOG_PATH = path.join(REPOSITORY_ROOT, "_CONTROL_PLANE", "UPDATE_LOG.jsonl");

export function getGeodeIndexStats(): GeodeIndexStats {
  const regulationStats = getRegulationCorpusStats();
  const manifest = readManifest();
  const corpusCount = totalLayerCount(manifest);
  const writeDates = readCorpusWriteDates();
  const lastUpdated = latestManifestDate(manifest) ?? regulationStats.lastUpdated;
  const endDate = dateOnly(maxDate([lastUpdated, ...writeDates]) ?? new Date().toISOString());
  const points = buildThirtyDaySeries(endDate, corpusCount, writeDates);

  return {
    agencyCount: regulationStats.agencyCount,
    count: corpusCount,
    lastUpdated,
    points,
    variants: [
      { label: "CRS", value: layerCount(manifest, "01_Statutes_CRS") },
      { label: "CCR", value: layerCount(manifest, "02_Regulations_CCR") },
      { label: "Rulemaking", value: layerCount(manifest, "04_Rulemaking") },
      { label: "Bills", value: layerCount(manifest, "03_Legislation") },
      { label: "Orders", value: layerCount(manifest, "05_Executive_Orders") },
    ],
  };
}

function readManifest(): Manifest {
  try {
    return JSON.parse(fs.readFileSync(MASTER_MANIFEST_PATH, "utf8")) as Manifest;
  } catch {
    return {};
  }
}

function layerCount(manifest: Manifest, layerId: string): number {
  return manifest.data_layers?.find((layer) => layer.id === layerId)?.record_count ?? 0;
}

function totalLayerCount(manifest: Manifest): number {
  return manifest.data_layers?.reduce((sum, layer) => sum + (layer.record_count ?? 0), 0) ?? 0;
}

function latestManifestDate(manifest: Manifest): string | null {
  return maxDate(
    manifest.data_layers?.flatMap((layer) => [layer.last_checked, layer.last_ingested]) ?? [],
  );
}

function readCorpusWriteDates(): string[] {
  if (!fs.existsSync(UPDATE_LOG_PATH)) {
    return [];
  }

  return fs
    .readFileSync(UPDATE_LOG_PATH, "utf8")
    .split(/\r?\n/)
    .filter(Boolean)
    .map(parseUpdateLogRecord)
    .filter((record): record is UpdateLogRecord => record !== null)
    .map((record) => record.timestamp)
    .filter((timestamp): timestamp is string => typeof timestamp === "string" && timestamp.length > 0);
}

function parseUpdateLogRecord(line: string): UpdateLogRecord | null {
  try {
    return JSON.parse(line) as UpdateLogRecord;
  } catch {
    return null;
  }
}

function buildThirtyDaySeries(endDate: string, currentCount: number, writeDates: string[]): GeodeIndexPoint[] {
  const dayCounts = new Map<string, number>();

  for (const timestamp of writeDates) {
    const day = dateOnly(timestamp);
    dayCounts.set(day, (dayCounts.get(day) ?? 0) + 1);
  }

  const days = Array.from({ length: 30 }, (_, index) => addDays(endDate, index - 29));
  const writesInWindow = days.reduce((sum, day) => sum + (dayCounts.get(day) ?? 0), 0);
  let running = Math.max(0, currentCount - writesInWindow);

  return days.map((day) => {
    running += dayCounts.get(day) ?? 0;
    return { date: day, value: running };
  });
}

function maxDate(values: Array<string | null | undefined>): string | null {
  const valid = values
    .filter((value): value is string => typeof value === "string" && value.length > 0)
    .map((value) => new Date(value))
    .filter((value) => !Number.isNaN(value.getTime()))
    .sort((left, right) => left.getTime() - right.getTime());

  return valid.at(-1)?.toISOString() ?? null;
}

function dateOnly(value: string): string {
  return new Date(value).toISOString().slice(0, 10);
}

function addDays(day: string, offset: number): string {
  const date = new Date(`${day}T00:00:00.000Z`);
  date.setUTCDate(date.getUTCDate() + offset);
  return date.toISOString().slice(0, 10);
}
