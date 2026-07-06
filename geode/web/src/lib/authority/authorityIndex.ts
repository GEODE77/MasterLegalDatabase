import fs from "node:fs";
import path from "node:path";
import { spawnSync } from "node:child_process";

import { GEODE_READ_INDEX_PATH, REPOSITORY_ROOT } from "@/lib/paths";

export type RelatedAuthority = {
  confidence: number;
  direction?: "inbound" | "outbound";
  evidence: string | null;
  id: string;
  layer?: string | null;
  relationship: string;
  title?: string;
  type: string;
};

export type AuthorityTimelineEvent = {
  date: string;
  description: string;
  eventId: string;
  eventType: string;
  filePath: string | null;
};

export type AuthoritySourceVersion = {
  label: string;
  path: string;
  sha256: string;
};

export type AuthorityDetailRecord = {
  articleName: string | null;
  citation: string;
  crossReferences: string[];
  dataVersion: string | null;
  fullText: string;
  historyNote: string | null;
  id: string;
  layer: string;
  partName: string | null;
  relatedAuthorities: RelatedAuthority[];
  sectionHeading: string;
  sourceUrl: string | null;
  sourceVersions: AuthoritySourceVersion[];
  timelineEvents: AuthorityTimelineEvent[];
  title: string;
  titleName: string | null;
};

type CRSSectionRecord = {
  article_name?: string | null;
  cross_references_outbound?: string[];
  data_version?: string | null;
  full_text?: string;
  history_note?: string | null;
  id?: string;
  part_name?: string | null;
  section_heading?: string;
  section_num?: string;
  source_url?: string | null;
  title_name?: string | null;
};

type CrosswalkRecord = {
  confidence?: number;
  relationship?: string;
  source_evidence?: string | null;
  source_id?: string;
  target_id?: string | null;
  target_type?: string;
};

type ReadIndexDetail = {
  chunks?: Array<{ text?: string }>;
  entity?: {
    citation?: string | null;
    confidence?: number;
    entity_type?: string;
    geode_id?: string;
    layer?: string;
    path?: string;
    publication_year?: number | null;
    sha256?: string;
    source_url?: string;
    title?: string;
  };
  relations?: Array<{
    confidence?: number;
    direction?: "inbound" | "outbound";
    evidence?: string | null;
    related_id?: string;
    related_layer?: string | null;
    related_title?: string;
    related_type?: string | null;
    relationship?: string;
  }>;
  source_versions?: Array<{
    path?: string;
    sha256?: string;
    version_label?: string;
  }>;
  timeline_events?: Array<{
    description?: string;
    event_date?: string;
    event_id?: string;
    event_type?: string;
    file_path?: string | null;
  }>;
};

const STATUTE_TO_REGULATION_PATH = path.join(
  REPOSITORY_ROOT,
  "_CROSSWALKS",
  "statute_to_regulation.jsonl",
);

export function getAuthorityById(id: string): AuthorityDetailRecord | null {
  const decodedId = decodeURIComponent(id);

  if (decodedId.startsWith("CRS-")) {
    return getCRSAuthority(decodedId) ?? getReadIndexAuthority(decodedId);
  }

  return getReadIndexAuthority(decodedId);
}

function getCRSAuthority(id: string): AuthorityDetailRecord | null {
  const title = crsTitleNumber(id);

  if (!title) {
    return null;
  }

  const metaPath = path.join(
    REPOSITORY_ROOT,
    "01_Statutes_CRS",
    "_meta",
    `crs_title_${title.padStart(2, "0")}_meta.jsonl`,
  );
  const record = readJsonl(metaPath)
    .map((row) => row as CRSSectionRecord)
    .find((row) => row.id === id);

  if (!record?.id || !record.full_text) {
    return null;
  }

  const citation = `CRS ${record.section_num ?? id.replace(/^CRS-/, "").replaceAll("-", "-")}`;
  const sectionHeading = record.section_heading ?? citation;

  return {
    articleName: record.article_name ?? null,
    citation,
    crossReferences: record.cross_references_outbound ?? [],
    dataVersion: record.data_version ?? null,
    fullText: record.full_text,
    historyNote: record.history_note ?? null,
    id,
    layer: "01_Statutes_CRS",
    partName: record.part_name ?? null,
    relatedAuthorities: relatedAuthorities(id),
    sectionHeading,
    sourceUrl: record.source_url ?? null,
    sourceVersions: [],
    timelineEvents: [],
    title: `${citation}: ${sectionHeading}`,
    titleName: record.title_name ?? null,
  };
}

function getReadIndexAuthority(id: string): AuthorityDetailRecord | null {
  const detail = readIndexDetail(id);
  const entity = detail?.entity;

  if (!entity?.geode_id) {
    return null;
  }

  const fullText = detail?.chunks
    ?.map((chunk) => chunk.text?.trim())
    .filter((text): text is string => Boolean(text))
    .join("\n\n");
  const citation = entity.citation ?? entity.geode_id;
  const title = entity.title ?? citation;

  return {
    articleName: null,
    citation,
    crossReferences: [],
    dataVersion: entity.publication_year ? String(entity.publication_year) : null,
    fullText: fullText || title,
    historyNote: entity.path ? `Indexed from ${entity.path}.` : null,
    id: entity.geode_id,
    layer: entity.layer ?? "Geode",
    partName: null,
    relatedAuthorities: readIndexRelations(detail),
    sectionHeading: title,
    sourceUrl: entity.source_url || null,
    sourceVersions: readIndexSourceVersions(detail),
    timelineEvents: readIndexTimelineEvents(detail),
    title,
    titleName: layerLabel(entity.layer),
  };
}

function readIndexDetail(id: string): ReadIndexDetail | null {
  const python = process.env.PYTHON ?? "python";
  const pythonPath = [REPOSITORY_ROOT, process.env.PYTHONPATH].filter(Boolean).join(path.delimiter);
  const result = spawnSync(
    python,
    [
      "-m",
      "geode.web.detail_index",
      "--database",
      GEODE_READ_INDEX_PATH,
      "--id",
      id,
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

  if (result.error || result.status !== 0) {
    return null;
  }

  try {
    return JSON.parse(result.stdout) as ReadIndexDetail | null;
  } catch {
    return null;
  }
}

function readIndexRelations(detail: ReadIndexDetail | null): RelatedAuthority[] {
  return (detail?.relations ?? []).slice(0, 32).flatMap((relation) => {
    if (!relation.related_id) {
      return [];
    }

    return [
      {
        confidence: relation.confidence ?? 0,
        direction: relation.direction,
        evidence: relation.evidence ?? null,
        id: relation.related_id,
        layer: relation.related_layer ?? null,
        relationship: relation.relationship ?? "related",
        title: relation.related_title ?? relation.related_id,
        type: relation.related_type ?? "authority",
      },
    ];
  });
}

function readIndexSourceVersions(detail: ReadIndexDetail | null): AuthoritySourceVersion[] {
  return (detail?.source_versions ?? []).flatMap((version) => {
    if (!version.path || !version.sha256) {
      return [];
    }

    return [
      {
        label: version.version_label ?? "current",
        path: version.path,
        sha256: version.sha256,
      },
    ];
  });
}

function readIndexTimelineEvents(detail: ReadIndexDetail | null): AuthorityTimelineEvent[] {
  return (detail?.timeline_events ?? []).flatMap((event) => {
    if (!event.event_id || !event.event_date) {
      return [];
    }

    return [
      {
        date: event.event_date,
        description: event.description ?? "",
        eventId: event.event_id,
        eventType: event.event_type ?? "event",
        filePath: event.file_path ?? null,
      },
    ];
  });
}

function crsTitleNumber(id: string): string | null {
  const match = /^CRS-(\d+(?:\.\d+)?)-/.exec(id);
  return match?.[1] ?? null;
}

function relatedAuthorities(id: string): RelatedAuthority[] {
  if (!fs.existsSync(STATUTE_TO_REGULATION_PATH)) {
    return [];
  }

  return readJsonl(STATUTE_TO_REGULATION_PATH)
    .map((row) => row as CrosswalkRecord)
    .filter((row) => row.source_id === id && Boolean(row.target_id))
    .slice(0, 24)
    .map((row) => ({
      confidence: row.confidence ?? 0,
      evidence: row.source_evidence ?? null,
      id: row.target_id ?? "",
      layer: "02_Regulations_CCR",
      relationship: row.relationship ?? "related",
      title: row.target_id ?? "",
      type: row.target_type ?? "authority",
    }));
}

function layerLabel(layer?: string): string | null {
  if (layer === "01_Statutes_CRS") {
    return "Colorado Revised Statutes";
  }

  if (layer === "02_Regulations_CCR") {
    return "Code of Colorado Regulations";
  }

  if (layer === "03_Legislation") {
    return "Colorado Legislation";
  }

  if (layer === "04_Rulemaking") {
    return "Colorado Rulemaking";
  }

  if (layer === "05_Executive_Orders") {
    return "Colorado Executive Orders";
  }

  if (layer === "06_Session_Laws") {
    return "Colorado Session Laws";
  }

  if (layer === "07_Supplementary") {
    return "Supplementary Authority";
  }

  return null;
}

function readJsonl(filePath: string): unknown[] {
  if (!fs.existsSync(filePath)) {
    return [];
  }

  return fs
    .readFileSync(filePath, "utf8")
    .split(/\r?\n/)
    .filter(Boolean)
    .flatMap((line) => {
      try {
        return [JSON.parse(line) as unknown];
      } catch {
        return [];
      }
    });
}
