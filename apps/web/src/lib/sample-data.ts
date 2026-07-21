import type {
  Agency,
  CorpusEntity,
  DiscussionPreview,
  EntityRelation,
  SearchResult,
  TextChunk,
  TimelineEvent
} from "./types";

export const entities: CorpusEntity[] = [
  {
    geodeId: "CRS-25-7-109",
    entityType: "statute_section",
    layer: "01_Statutes_CRS",
    citation: "CRS 25-7-109",
    title: "Emission Control Regulations",
    summary:
      "Authorizes air quality rules and anchors multiple regulatory obligations administered through the Air Quality Control Commission.",
    sourceUrl: "https://leg.colorado.gov/colorado-revised-statutes",
    confidence: 0.95,
    subjectTags: ["environment", "public-health", "air-quality"],
    industryTags: ["31-33", "221", "484"],
    agencyCode: "CDPHE_AQCC",
    effectiveDate: "2023-07-01",
    status: "current"
  },
  {
    geodeId: "5_CCR_1001-9",
    entityType: "regulation_rule",
    layer: "02_Regulations_CCR",
    citation: "5 CCR 1001-9",
    title: "Regulation Number 7: Control of Ozone via Ozone Precursors",
    summary:
      "Implements emission control requirements for sources associated with ozone precursor compounds.",
    sourceUrl: "https://www.sos.state.co.us/CCR/",
    confidence: 0.91,
    subjectTags: ["environment", "air-quality"],
    industryTags: ["211", "221", "31-33"],
    agencyCode: "CDPHE_AQCC",
    effectiveDate: "2024-01-15",
    status: "current"
  },
  {
    geodeId: "RM-2024-00412",
    entityType: "rulemaking_notice",
    layer: "04_Rulemaking",
    citation: "RM 2024-00412",
    title: "Notice of Rulemaking: Air Quality Control Commission",
    summary:
      "Rulemaking notice associated with revisions to air quality requirements and hearing deadlines.",
    sourceUrl: "https://www.sos.state.co.us/CCR/RegisterHome.do",
    confidence: 0.88,
    subjectTags: ["rulemaking", "air-quality"],
    industryTags: ["31-33"],
    agencyCode: "CDPHE_AQCC",
    effectiveDate: "2024-05-20",
    status: "notice"
  }
];

export const chunks: TextChunk[] = [
  {
    id: "chunk-crs-25-7-109-1",
    entityGeodeId: "CRS-25-7-109",
    chunkIndex: 0,
    headingPath: ["Title 25", "Article 7", "Section 109"],
    citationScope: "CRS 25-7-109",
    text:
      "The commission shall promulgate rules necessary for the effective administration and enforcement of emission control requirements. Rules adopted under this section must preserve source references, effective dates, and applicable exceptions."
  },
  {
    id: "chunk-crs-25-7-109-2",
    entityGeodeId: "CRS-25-7-109",
    chunkIndex: 1,
    headingPath: ["Title 25", "Article 7", "Section 109", "Implementation"],
    citationScope: "CRS 25-7-109",
    text:
      "Requirements may apply to owners or operators of regulated sources when the source category and compliance date are identified in the applicable rule."
  },
  {
    id: "chunk-5-ccr-1001-9-1",
    entityGeodeId: "5_CCR_1001-9",
    chunkIndex: 0,
    headingPath: ["Department of Public Health and Environment", "AQCC", "Regulation 7"],
    citationScope: "5 CCR 1001-9",
    text:
      "This regulation establishes emission control requirements for listed sources and identifies monitoring, recordkeeping, and reporting obligations."
  }
];

export const relations: EntityRelation[] = [
  {
    id: "rel-reg7-crs",
    sourceGeodeId: "5_CCR_1001-9",
    sourceType: "regulation_rule",
    targetGeodeId: "CRS-25-7-109",
    targetType: "statute_section",
    relationship: "authorized_by",
    confidence: 0.91,
    sourceEvidence: "Promulgated pursuant to section 25-7-109, C.R.S."
  },
  {
    id: "rel-rm-reg7",
    sourceGeodeId: "RM-2024-00412",
    sourceType: "rulemaking_notice",
    targetGeodeId: "5_CCR_1001-9",
    targetType: "regulation_rule",
    relationship: "modifies",
    confidence: 0.84,
    sourceEvidence: "Notice identifies proposed revisions to Regulation Number 7."
  }
];

export const timelineEvents: TimelineEvent[] = [
  {
    id: "TE-2023-07-01-001",
    legalDocumentId: "CRS-25-7-109",
    eventType: "bill_signed",
    label: "SB23-016 amended related air quality provisions.",
    date: "2023-07-01",
    sourceReference: "03_Legislation/2023/bills_2023.jsonl"
  },
  {
    id: "TE-2024-01-15-002",
    legalDocumentId: "5_CCR_1001-9",
    eventType: "rule_effective",
    label: "Rule amendments became effective for Regulation Number 7.",
    date: "2024-01-15",
    sourceReference: "04_Rulemaking/2024/register_2024_Q1.jsonl"
  },
  {
    id: "TE-2024-05-20-001",
    legalDocumentId: "RM-2024-00412",
    eventType: "rulemaking_notice",
    label: "Register notice opened rulemaking review window.",
    date: "2024-05-20",
    sourceReference: "04_Rulemaking/2024/register_2024_Q2.jsonl"
  }
];

export const agencies: Agency[] = [
  {
    code: "CDPHE_AQCC",
    name: "Air Quality Control Commission",
    jurisdiction: "Colorado",
    description:
      "Rulemaking body associated with air quality standards, emission control regulations, and related compliance obligations.",
    sourceUrl: "https://cdphe.colorado.gov/aqcc",
    entityCount: 24,
    openIssues: 3,
    activeRulemakings: 2
  }
];

export const discussions: DiscussionPreview[] = [
  {
    id: "q-air-permit-threshold",
    type: "Question",
    title: "Which source categories trigger monitoring records under Regulation 7?",
    status: "Open",
    anchor: "5 CCR 1001-9, Part B",
    sourceState: "Needs citation"
  },
  {
    id: "exp-authority-chain",
    type: "Explanation",
    title: "How CRS 25-7-109 links to AQCC rulemaking authority",
    status: "Reviewed",
    anchor: "CRS 25-7-109",
    sourceState: "Source-backed"
  },
  {
    id: "issue-effective-date",
    type: "Data Issue",
    title: "Confirm effective date in Register notice crosswalk",
    status: "Review",
    anchor: "RM-2024-00412",
    sourceState: "Evidence attached"
  }
];

export const searchResults: SearchResult[] = entities.map((entity) => ({
  entity,
  matchReason:
    entity.geodeId === "CRS-25-7-109"
      ? "citation matched"
      : entity.entityType === "rulemaking_notice"
        ? "related by rulemaking"
        : "title matched"
}));
