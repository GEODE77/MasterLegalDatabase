import { inflateRawSync } from "node:zlib";

import { searchRegulations } from "@/lib/search/searchRegulations";
import type { OnboardingAnalysis } from "./types";

type IndustryRule = {
  label: string;
  terms: string[];
};

const INDUSTRY_RULES: IndustryRule[] = [
  {
    label: "advanced ceramics",
    terms: ["ceramic", "silica", "kiln", "furnace", "powder", "dust", "particulate"],
  },
  {
    label: "manufacturing",
    terms: ["manufacturing", "factory", "plant", "production", "industrial", "facility"],
  },
  {
    label: "environment",
    terms: ["air quality", "water discharge", "surface water", "water", "discharge", "wastewater", "stormwater", "emissions", "waste"],
  },
  {
    label: "worker safety",
    terms: ["osha", "worker", "workplace", "injury", "exposure", "respirable", "safety"],
  },
  {
    label: "supply chain",
    terms: ["supplier", "vendor", "flowdown", "procurement", "contract", "materials"],
  },
  {
    label: "energy",
    terms: ["energy", "utility", "electric", "renewable", "power", "grid"],
  },
];

const CITATION_PATTERNS = [
  /\b\d+\s+CCR\s+\d{3,4}-\d+(?:[\w.-]+)?\b/gi,
  /\b(?:C\.R\.S\.|CRS)\s*\d{1,2}-\d{1,3}-\d{1,4}(?:\.\d+)?\b/gi,
  /\b\d+\s+CFR\s+\d+(?:\.\d+)?\b/gi,
  /\bOSHA\b/gi,
  /\bEPA\b/gi,
];

export async function textFromUploadedFile(file: File): Promise<string> {
  const bytes = Buffer.from(await file.arrayBuffer());
  const name = file.name.toLowerCase();

  if (bytes.byteLength > 4 * 1024 * 1024) {
    throw new Error("Files must be 4 MB or smaller for onboarding.");
  }

  if (name.endsWith(".docx")) {
    return extractDocxText(bytes);
  }

  if (name.endsWith(".pdf") || file.type === "application/pdf") {
    return extractPdfText(bytes);
  }

  return bytes.toString("utf8");
}

export function inferOnboardingAnalysis(text: string): OnboardingAnalysis {
  const normalizedText = normalizeText(text).slice(0, 120_000);

  if (normalizedText.length < 20) {
    throw new Error("The source did not contain enough readable text.");
  }

  const citations = extractCitations(normalizedText);
  const industries = inferIndustries(normalizedText);
  const jurisdiction = inferJurisdiction(normalizedText, citations);
  const role = inferRole(normalizedText);
  const documentKind = inferDocumentKind(normalizedText);
  const summary = summarizeDocument(documentKind, industries, jurisdiction, citations);
  const relatedRegulations = searchRegulations(
    `${summary} ${industries.join(" ")} ${citations.join(" ")}`,
    4,
  ).map((result) => ({
    citation: result.citation,
    excerpt: cleanDisplayText(result.excerpt),
    id: result.id,
    score: result.score,
    sourceUrl: result.sourceUrl,
    title: cleanDisplayText(result.title),
  }));

  return {
    citations,
    documentKind,
    industries,
    jurisdiction,
    relatedRegulations,
    role,
    summary,
  };
}

function extractDocxText(bytes: Buffer): string {
  const xml = readZipEntry(bytes, "word/document.xml");

  if (!xml) {
    return "";
  }

  return decodeXml(xml.replace(/<w:p[\s\S]*?>/g, "\n").replace(/<[^>]+>/g, " "));
}

function readZipEntry(bytes: Buffer, targetName: string): string | null {
  const eocdOffset = bytes.lastIndexOf(Buffer.from([0x50, 0x4b, 0x05, 0x06]));

  if (eocdOffset < 0) {
    return null;
  }

  const entries = bytes.readUInt16LE(eocdOffset + 10);
  let offset = bytes.readUInt32LE(eocdOffset + 16);

  for (let index = 0; index < entries; index += 1) {
    if (bytes.readUInt32LE(offset) !== 0x02014b50) {
      return null;
    }

    const method = bytes.readUInt16LE(offset + 10);
    const compressedSize = bytes.readUInt32LE(offset + 20);
    const nameLength = bytes.readUInt16LE(offset + 28);
    const extraLength = bytes.readUInt16LE(offset + 30);
    const commentLength = bytes.readUInt16LE(offset + 32);
    const localOffset = bytes.readUInt32LE(offset + 42);
    const name = bytes.subarray(offset + 46, offset + 46 + nameLength).toString("utf8");

    if (name === targetName) {
      const localNameLength = bytes.readUInt16LE(localOffset + 26);
      const localExtraLength = bytes.readUInt16LE(localOffset + 28);
      const dataStart = localOffset + 30 + localNameLength + localExtraLength;
      const data = bytes.subarray(dataStart, dataStart + compressedSize);
      return method === 8 ? inflateRawSync(data).toString("utf8") : data.toString("utf8");
    }

    offset += 46 + nameLength + extraLength + commentLength;
  }

  return null;
}

function extractPdfText(bytes: Buffer): string {
  const raw = bytes.toString("latin1");
  const parentheticalText = Array.from(raw.matchAll(/\(([^()]{4,})\)/g))
    .map((match) => match[1])
    .join(" ");

  return normalizeText(`${parentheticalText} ${raw.replace(/[^\x20-\x7e]+/g, " ")}`);
}

function extractCitations(text: string): string[] {
  const citations = CITATION_PATTERNS.flatMap((pattern) => text.match(pattern) ?? []);
  return Array.from(new Set(citations.map((citation) => citation.trim().replace(/\s+/g, " ")))).slice(0, 8);
}

function inferIndustries(text: string): string[] {
  const lower = text.toLowerCase();
  const scored = INDUSTRY_RULES.map((rule) => ({
    label: rule.label,
    score: rule.terms.reduce((sum, term) => sum + (lower.includes(term) ? 1 : 0), 0),
  }))
    .filter((item) => item.score > 0)
    .sort((a, b) => b.score - a.score)
    .map((item) => item.label);

  return scored.length > 0 ? scored.slice(0, 3) : ["general compliance"];
}

function inferJurisdiction(text: string, citations: string[]): string {
  const lower = text.toLowerCase();
  const hasColorado = /\bcolorado\b|\bccr\b|\bc\.r\.s\.|\bcrs\b/i.test(text);
  const hasFederal = /\bcfr\b|\bosha\b|\bepa\b|federal/i.test(text) || citations.some((item) => /CFR|OSHA|EPA/i.test(item));

  if (hasColorado && hasFederal) {
    return "Colorado and federal";
  }

  if (hasFederal && !lower.includes("colorado")) {
    return "Federal";
  }

  return "Colorado";
}

function inferRole(text: string): string {
  const lower = text.toLowerCase();

  if (/board|ceo|executive|strategy|enterprise/.test(lower)) {
    return "Government affairs";
  }

  if (/counsel|legal|attorney|litigation/.test(lower)) {
    return "Legal operations";
  }

  if (/plant|operations|facility|production/.test(lower)) {
    return "Compliance";
  }

  if (/compliance|permit|audit|reporting/.test(lower)) {
    return "Compliance";
  }

  return "Regulatory intelligence";
}

function inferDocumentKind(text: string): string {
  const lower = text.toLowerCase();

  if (/board|agenda|directors/.test(lower)) {
    return "board memo";
  }

  if (/memo|memorandum/.test(lower)) {
    return "compliance memo";
  }

  if (/\bccr\b|\bc\.r\.s\.|\bcrs\b|rule|statute|regulation|section/.test(lower)) {
    return "regulatory excerpt";
  }

  if (/policy|procedure|standard/.test(lower)) {
    return "internal policy";
  }

  return "business source";
}

function summarizeDocument(
  documentKind: string,
  industries: string[],
  jurisdiction: string,
  citations: string[],
): string {
  const industryText = industries.slice(0, 2).join(" and ");
  const citationText = citations.length > 0 ? `, with explicit references to ${citations[0]}` : "";

  return `This ${documentKind} appears to concern ${industryText} obligations in ${jurisdiction}${citationText}.`;
}

function normalizeText(value: string): string {
  return value.replace(/\s+/g, " ").trim();
}

function decodeXml(value: string): string {
  return value
    .replace(/&amp;/g, "&")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&quot;/g, "\"")
    .replace(/&apos;/g, "'");
}

function cleanDisplayText(value: string): string {
  return value
    .replaceAll("\u00e2\u0080\u0099", "'")
    .replaceAll("\u00e2\u0080\u009c", "\"")
    .replaceAll("\u00e2\u0080\u009d", "\"")
    .replaceAll("\u00e2\u0080\u0093", "-")
    .replaceAll("\u00e2\u0080\u0094", "-");
}
