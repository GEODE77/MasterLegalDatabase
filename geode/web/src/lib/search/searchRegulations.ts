import fs from "node:fs";
import path from "node:path";

import { MASTER_MANIFEST_PATH, REPOSITORY_ROOT } from "@/lib/paths";
import type {
  RegulationDetailRecord,
  RegulationIndexRecord,
  RegulationSearchResult,
} from "@/lib/search/types";

const STOP_WORDS = new Set([
  "the",
  "and",
  "for",
  "are",
  "what",
  "which",
  "with",
  "from",
  "that",
  "this",
  "does",
  "into",
  "about",
  "colorado",
  "regulation",
  "regulations",
  "requirement",
  "requirements",
]);

type ManifestLayer = {
  id?: string;
  index_file?: string;
};

type Manifest = {
  data_layers?: ManifestLayer[];
};

type Candidate = RegulationSearchResult & {
  bodyLower: string;
  citationLower: string;
  titleLower: string;
};

export type RegulationCorpusStats = {
  agencyCount: number;
  count: number;
  lastUpdated: string | null;
};

export type RegulationReferencePreview = {
  citation: string;
  title: string;
};

export function searchRegulations(query: string, limit = 8): RegulationSearchResult[] {
  const tokens = tokenize(query);

  if (tokens.length === 0) {
    return [];
  }

  const indexPath = getRegulationIndexPath();
  const records = readIndexRecords(indexPath);
  const phrase = query.trim().toLowerCase();

  return records
    .map((record) => toCandidate(record))
    .filter((candidate): candidate is Candidate => candidate !== null)
    .map((candidate) => scoreCandidate(candidate, tokens, phrase))
    .filter((candidate) => candidate.score > 0)
    .sort((a, b) => b.score - a.score)
    .slice(0, limit)
    .map(toSearchResult);
}

export function getRegulationCorpusStats(): RegulationCorpusStats {
  const records = readIndexRecords(getRegulationIndexPath());
  const agencyIds = new Set(records.map(agencyIdFromRecord).filter((value): value is string => value !== null));
  const lastUpdated = records
    .map((record) => record.last_updated)
    .filter((value): value is string => typeof value === "string" && value.length > 0)
    .sort()
    .at(-1) ?? null;

  return {
    agencyCount: agencyIds.size,
    count: records.length,
    lastUpdated,
  };
}

export function findRegulationReference(reference: string): RegulationReferencePreview | null {
  const normalizedReference = normalizeReference(reference);

  if (!normalizedReference) {
    return null;
  }

  const records = readIndexRecords(getRegulationIndexPath());
  const record = records.find((item) => {
    const citation = normalizeReference(item.citation ?? "");
    const id = normalizeReference(item.id?.replaceAll("_", " ") ?? "");

    return Boolean(
      citation && (citation === normalizedReference || normalizedReference.includes(citation))
      || id && (id === normalizedReference || normalizedReference.includes(id)),
    );
  });

  if (!record?.id) {
    return null;
  }

  return {
    citation: record.citation ?? record.id.replaceAll("_", " "),
    title: record.title ?? record.id.replaceAll("_", " "),
  };
}

export function getRegulationById(id: string): RegulationDetailRecord | null {
  const normalizedId = decodeURIComponent(id);
  const records = readIndexRecords(getRegulationIndexPath());
  const record = records.find((item) => item.id === normalizedId);

  if (!record) {
    return null;
  }

  const candidate = toCandidate(record);

  if (!candidate) {
    return null;
  }

  return {
    ...toSearchResult(candidate),
    agency: agencyFromRecord(record) ?? agencyFromBody(candidate.body) ?? "Agency not stated",
    effectiveDate: null,
    lastUpdated: record.last_updated ?? null,
    tags: record.tags ?? [],
  };
}

export function getRelatedRegulations(id: string, limit = 4): RegulationSearchResult[] {
  const current = getRegulationById(id);

  if (!current) {
    return [];
  }

  const records = readIndexRecords(getRegulationIndexPath());
  const currentTags = new Set(current.tags);

  return records
    .filter((record) => record.id && record.id !== current.id)
    .map((record) => {
      const sharedTags = (record.tags ?? []).filter((tag) => currentTags.has(tag)).length;
      return { record, sharedTags };
    })
    .filter(({ sharedTags }) => sharedTags > 0)
    .sort((left, right) => right.sharedTags - left.sharedTags)
    .slice(0, limit)
    .map(({ record }) => toCandidate(record))
    .filter((candidate): candidate is Candidate => candidate !== null)
    .map(toSearchResult);
}

function getRegulationIndexPath(): string {
  const manifest = JSON.parse(fs.readFileSync(MASTER_MANIFEST_PATH, "utf8")) as Manifest;
  const regulationLayer = manifest.data_layers?.find((layer) => layer.id === "02_Regulations_CCR");
  const indexFile = regulationLayer?.index_file ?? "02_Regulations_CCR/_index.jsonl";

  return path.join(REPOSITORY_ROOT, indexFile);
}

function readIndexRecords(indexPath: string): RegulationIndexRecord[] {
  if (!fs.existsSync(indexPath)) {
    return [];
  }

  return fs
    .readFileSync(indexPath, "utf8")
    .split(/\r?\n/)
    .filter(Boolean)
    .map((line) => {
      try {
        return JSON.parse(line) as RegulationIndexRecord;
      } catch {
        return null;
      }
    })
    .filter((record): record is RegulationIndexRecord => record !== null);
}

function toCandidate(record: RegulationIndexRecord): Candidate | null {
  if (!record.id) {
    return null;
  }

  const rulePath = path.join(REPOSITORY_ROOT, "02_Regulations_CCR", "_rules", `${record.id}.md`);

  if (!fs.existsSync(rulePath)) {
    return null;
  }

  const body = stripFrontmatter(fs.readFileSync(rulePath, "utf8"));
  const citation = record.citation ?? record.id.replaceAll("_", " ");
  const title = titleNearCitation(body, citation) ?? firstMeaningfulTitle(body) ?? record.title ?? record.id;

  return {
    id: record.id,
    title,
    citation,
    excerpt: "",
    body,
    score: 0,
    sourceUrl: record.source_url ?? null,
    bodyLower: body.toLowerCase(),
    citationLower: citation.toLowerCase(),
    titleLower: title.toLowerCase(),
  };
}

function scoreCandidate(candidate: Candidate, tokens: string[], phrase: string): Candidate {
  let score = 0;
  const bestTokenIndex = findBestTokenIndex(candidate.bodyLower, tokens);

  for (const token of tokens) {
    if (candidate.citationLower.includes(token)) {
      score += 24;
    }

    if (candidate.titleLower.includes(token)) {
      score += 18;
    }

    score += Math.min(countOccurrences(candidate.bodyLower, token), 18);
  }

  if (phrase.length > 6 && candidate.bodyLower.includes(phrase)) {
    score += 36;
  }

  return {
    ...candidate,
    excerpt: buildExcerpt(candidate.body, bestTokenIndex),
    score,
  };
}

function tokenize(value: string): string[] {
  const tokens = value
    .toLowerCase()
    .replace(/[^a-z0-9\s-]/g, " ")
    .split(/\s+/)
    .map((token) => token.trim())
    .filter((token) => token.length >= 3 && !STOP_WORDS.has(token));

  return Array.from(new Set(tokens));
}

function normalizeReference(value: string): string {
  return value
    .toLowerCase()
    .replace(/c\.?r\.?s\.?/g, "crs")
    .replace(/c\.?c\.?r\.?/g, "ccr")
    .replace(/section|sections/g, "")
    .replace(/[^a-z0-9]+/g, " ")
    .trim();
}

function countOccurrences(value: string, token: string): number {
  let count = 0;
  let index = value.indexOf(token);

  while (index !== -1) {
    count += 1;
    index = value.indexOf(token, index + token.length);
  }

  return count;
}

function findBestTokenIndex(value: string, tokens: string[]): number {
  const indexes = tokens.map((token) => value.indexOf(token)).filter((index) => index >= 0);
  return indexes.length > 0 ? Math.min(...indexes) : 0;
}

function buildExcerpt(body: string, matchIndex: number): string {
  const cleanBody = body.replace(/\s+/g, " ").trim();
  const start = Math.max(0, matchIndex - 150);
  const end = Math.min(cleanBody.length, start + 420);
  const prefix = start > 0 ? "..." : "";
  const suffix = end < cleanBody.length ? "..." : "";

  return `${prefix}${cleanBody.slice(start, end)}${suffix}`;
}

function stripFrontmatter(value: string): string {
  return value.replace(/^---[\s\S]*?---/, "").trim();
}

function firstMeaningfulTitle(body: string): string | null {
  const lines = body.split(/\r?\n/).map((line) => line.trim());
  const heading = lines.find((line) => line.startsWith("#### ") || line.startsWith("## "));

  if (!heading) {
    return null;
  }

  return heading.replace(/^#+\s*/, "").replace(/_/g, " ");
}

function titleNearCitation(body: string, citation: string): string | null {
  const lines = body
    .split(/\r?\n/)
    .slice(0, 48)
    .map((line) => line.trim())
    .filter(Boolean);
  const normalizedCitation = citation.toLowerCase();
  const citationIndex = lines.findIndex((line) => line.toLowerCase() === normalizedCitation);

  if (citationIndex <= 0) {
    return null;
  }

  const candidates = lines.slice(Math.max(0, citationIndex - 6), citationIndex).reverse();
  const title = candidates.find((line) => {
    const upper = line.toUpperCase();
    const hasLetters = /[A-Z]/i.test(line);
    const isAdministrativeLabel = /department|division|commission|office|state of colorado/i.test(line);

    return line.length > 10 && hasLetters && upper === line && !isAdministrativeLabel;
  });

  return title ?? null;
}

function toSearchResult(candidate: Candidate): RegulationSearchResult {
  return {
    body: candidate.body,
    citation: candidate.citation,
    excerpt: candidate.excerpt,
    id: candidate.id,
    score: candidate.score,
    sourceUrl: candidate.sourceUrl,
    title: candidate.title,
  };
}

function agencyFromRecord(record: RegulationIndexRecord): string | null {
  const agencyTag = record.tags?.find((tag) => !["ccr", "downloaded", "normalized"].includes(tag));

  if (!agencyTag) {
    return null;
  }

  return agencyTag
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function agencyIdFromRecord(record: RegulationIndexRecord): string | null {
  if (!record.source_url) {
    return null;
  }

  try {
    return new URL(record.source_url).searchParams.get("agencyID");
  } catch {
    return null;
  }
}

function agencyFromBody(body: string): string | null {
  const lines = body
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)
    .slice(0, 32);
  const commission = lines.find((line) => /commission|division|department|board|office/i.test(line));
  return commission ?? null;
}
