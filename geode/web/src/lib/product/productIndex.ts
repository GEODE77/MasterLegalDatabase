import fs from "node:fs";
import path from "node:path";

import { MASTER_MANIFEST_PATH, REPOSITORY_ROOT } from "@/lib/paths";

const JSON_READ_RETRY_ATTEMPTS = 3;
const JSON_READ_RETRY_DELAY_MS = 25;

export type ProductRelationship = {
  confidence: number;
  evidence: string | null;
  relationship: string;
  targetId: string;
  targetType: string;
};

export type RequirementSourceType = "validated_rule_unit" | "candidate_signal";

export type CandidateRequirement = {
  actionType: string;
  actionRequired: string;
  confidence: number;
  conditions: string[];
  evidence: string;
  exceptions: string[];
  id: string;
  regulatedEntity: string | null;
  sourceLabel: string;
  sourceType: RequirementSourceType;
  subjectTags: string[];
  temporal: string | null;
  reason: string;
  title: string;
};

export type ProductSection = {
  id: string;
  level: number;
  title: string;
};

export type ProductRegulation = {
  agency: string;
  body: string;
  citation: string;
  confidence: number;
  department: string;
  id: string;
  lastUpdated: string | null;
  relationships: ProductRelationship[];
  requirements: CandidateRequirement[];
  sections: ProductSection[];
  sourceUrl: string | null;
  tags: string[];
  title: string;
};

export type ImpactResult = {
  evidence: string;
  level: "High Impact" | "Medium Impact" | "Low Impact" | "Informational" | "Unknown";
  reasons: string[];
  regulation: ProductRegulation;
  score: number;
};

export type ComplianceStep = {
  actionType: string;
  actionRequired: string;
  citation: string;
  confidence: number;
  description: string;
  evidence: string;
  regulatedEntity: string | null;
  reason: string;
  sourceId: string;
  sourceLabel: string;
  sourceType: RequirementSourceType;
  stepOrder: number;
  title: string;
};

export type RequirementSearchResult = CandidateRequirement & {
  agency: string;
  citation: string;
  department: string;
  regulationId: string;
  regulationTitle: string;
  score: number;
  sourceUrl: string | null;
};

export type ProductUpdate = {
  date: string;
  description: string;
  href: string;
  label: string;
};

export type UpdateLedgerEvent = {
  confidence: number;
  description: string;
  eventDate: string;
  eventId: string;
  eventType: string;
  fullTextDiffAvailable: boolean;
  layerId: string | null;
  requiresFullDiff: boolean;
  source: string;
  sourcePath: string;
  status: string | null;
  title: string;
};

export type UpdateLedgerSummary = {
  diffStatus: string;
  eventsWritten: number;
  fullDiffReady: boolean;
  generatedAt: string | null;
  ledgerPath: string | null;
  manifestLayerEvents: number;
  nextAction: string;
  stepGateEvents: number;
  timelineEvents: number;
  updateLogEvents: number;
};

export type RelationshipCoverageRecord = {
  confidenceAverage: number | null;
  coverageStatus: string;
  crosswalkFile: string;
  duplicateCount: number;
  lowConfidenceCount: number;
  missingEvidenceCount: number;
  missingSourceCount: number;
  missingTargetCount: number;
  relationshipCount: number;
  relationshipTypes: Record<string, number>;
  sourceType: string | null;
  targetType: string | null;
  uniqueSourceCount: number;
  uniqueTargetCount: number;
};

export type RelationshipCoverageReport = {
  ccrRegulationsTotal: number;
  ccrRegulationsWithRelationships: number;
  ccrRelationshipCoverageRatio: number;
  coveragePath: string | null;
  coverageRecords: RelationshipCoverageRecord[];
  crosswalkFilesChecked: number;
  generatedAt: string | null;
  recommendedNextActions: string[];
  structuredRelationshipPanelReady: boolean;
  totalDuplicateRelationships: number;
  totalLowConfidence: number;
  totalMissingEvidence: number;
  totalRelationships: number;
  visualGraphDeferredReason: string;
  visualGraphReady: boolean;
};

export type FullTextDiffSummary = {
  boundary: string;
  diffPath: string | null;
  diffReady: boolean;
  filesChanged: number;
  filesChecked: number;
  filesWithPriorSnapshot: number;
  filesWithoutSnapshot: number;
  generatedAt: string | null;
};

export type SourceFreshnessLayer = {
  ageDays: number | null;
  freshnessStatus: string;
  lastChecked: string | null;
  lastIngested: string | null;
  layerId: string;
  recordCount: number;
  source: string | null;
  status: string;
};

export type SourceFreshnessReport = {
  boundary: string;
  generatedAt: string | null;
  layers: SourceFreshnessLayer[];
  layersChecked: number;
  networkRefreshPerformed: boolean;
  staleLayers: number;
  unknownLayers: number;
};

export type RetrievalCatalogSummary = {
  boundary: string;
  catalogPath: string | null;
  generatedAt: string | null;
  layerCounts: Record<string, number>;
  layersIndexed: number;
  recordsWritten: number;
};

export type ProductionReadinessReport = {
  blockers: string[];
  boundary: {
    externalRelianceCondition: string;
    meaning: string;
    notImplied: string;
  };
  controls: Array<{
    controlId: string;
    detail: string;
    evidencePath: string | null;
    status: string;
    title: string;
  }>;
  generatedAt: string | null;
  systemControlsPresent: boolean;
  warnings: string[];
};

export type RemainingWorkQueue = {
  generatedAt: string | null;
  items: Array<{
    category: string;
    id: string;
    nextAction: string;
    reason: string;
    status: string;
    title: string;
  }>;
  openItems: number;
};

export type SourceStrengthReport = {
  averageSourceStrengthScore: number;
  boundary: string;
  generatedAt: string | null;
  indexPath: string | null;
  layerCounts: Record<string, Record<string, number>>;
  levelCounts: Record<string, number>;
  recordsScored: number;
};

export type SourceRepairDashboard = {
  boundary: string;
  freshnessRefreshItems: number;
  generatedAt: string | null;
  humanReviewReadyForReliance: boolean;
  items: Array<{
    category: string;
    id: string;
    nextAction: string;
    status: string;
    title: string;
  }>;
  openItems: number;
  relationshipReviewRows: number;
};

export type MasterReadinessReport = {
  blockers: string[];
  boundary: string;
  externalRelianceReady: boolean;
  generatedAt: string | null;
  humanReview: {
    requiredRoles: number;
    unassignedRoles: number;
  };
  localSystemUsable: boolean;
  relationships: {
    relationshipsChecked: number;
    reviewRelationships: number;
    strongRelationships: number;
  };
  sourceStrength: {
    averageScore: number;
    levelCounts: Record<string, number>;
    recordsScored: number;
  };
};

type Manifest = {
  data_layers?: Array<{
    id?: string;
    index_file?: string;
    last_ingested?: string | null;
    record_count?: number;
    status?: string;
  }>;
};

type RegulationIndexRecord = {
  confidence?: number;
  id?: string;
  last_updated?: string;
  source_url?: string;
  tags?: string[];
  title?: string;
  citation?: string;
};

type NormalizedRecord = {
  agency_normalized?: string | null;
  department_normalized?: string | null;
  rule_name?: string | null;
};

type CrosswalkRecord = {
  confidence?: number;
  relationship?: string;
  source_evidence?: string | null;
  source_id?: string;
  target_id?: string | null;
  target_ids?: string[];
  target_type?: string;
};

type RuleUnitRecord = {
  action_required?: string | null;
  confidence?: number | { overall?: number };
  conditions?: string[] | null;
  entity_type?: string;
  exceptions?: string[] | null;
  id?: string;
  parentRegulationId?: string;
  parent_regulation_id?: string;
  plain_english_summary?: string | null;
  regulated_entity?: string | null;
  rule_type?: string | null;
  source_section?: string | null;
  subject_tags?: string[] | null;
  temporal?: string | null;
};

export type RuleUnitReviewItem = {
  allowedOutcomes: string[];
  canonicalChangeReady: boolean;
  currentRuleUnit: Record<string, unknown> & {
    actionRequired?: string | null;
    confidence?: number | { overall?: number };
    regulatedEntity?: string | null;
    ruleType?: string | null;
  };
  issues: string[];
  loggedDecision: {
    decidedAt: string;
    decisionId: string;
    outcome: RuleUnitReviewDecision["outcome"];
  } | null;
  parentRegulationId: string;
  priority: string;
  quality: {
    atomicity?: number;
    entityClarity?: number;
    exceptionCapture?: number;
    overall?: number;
    sourceFidelity?: number;
    temporalPrecision?: number;
  };
  reviewId: string;
  reviewReason: string;
  reviewStatus: RuleUnitReviewStatus;
  ruleUnitId: string;
  sourceContext: string | null;
  sourceSection: string;
  sourceSentence: string;
  status: string;
  suggestedOutcomes: string[];
};

export type RuleUnitReviewStatus =
  | "pending"
  | "approved"
  | "revised"
  | "split"
  | "quarantined";

export type RuleUnitReviewStatusFilter = RuleUnitReviewStatus | "all" | "change_ready";

export type RuleUnitReviewStatusSummary = {
  approved: number;
  changeReady: number;
  pending: number;
  quarantined: number;
  revised: number;
  split: number;
  total: number;
};

export type RuleUnitReviewSummary = {
  approveCandidates: number;
  pendingItems: number;
  queuePath: string | null;
  quarantineCandidates: number;
  reviseCandidates: number;
  splitCandidates: number;
};

export type RuleUnitReviewDecision = {
  decidedAt: string;
  decidedBy: string;
  decisionId: string;
  outcome: "approve" | "split" | "revise" | "quarantine";
  parentRegulationId: string;
  previousRuleUnit: Record<string, unknown>;
  proposedRuleUnits: Array<Record<string, unknown>>;
  rationale: string;
  reviewId: string;
  ruleUnitId: string;
  sourceSentence: string;
};

export type RuleUnitReviewDecisionInput = {
  decidedBy?: string;
  outcome?: string;
  proposedRuleUnits?: Array<Record<string, unknown>>;
  rationale?: string;
  reviewId?: string;
};

export type RuleUnitReviewDecisionSummary = {
  approved: number;
  decisionLogPath: string | null;
  quarantined: number;
  revised: number;
  split: number;
  totalDecisions: number;
};

export type RuleUnitReviewPacket = {
  allowedOutcomes: string[];
  canonicalChangeReady: boolean;
  currentRuleUnit: Record<string, unknown>;
  issues: string[];
  loggedDecision: Record<string, unknown> | null;
  packetId: string;
  parentRegulationId: string;
  priority: string;
  quality: Record<string, unknown>;
  relianceBoundary: string;
  reviewId: string;
  reviewReason: string;
  reviewerInstruction: string;
  ruleUnitId: string;
  sourceContext: string | null;
  sourceSection: string;
  sourceSentence: string;
  status: RuleUnitReviewStatus;
  suggestedOutcomes: string[];
};

export type RuleUnitReviewPacketSummary = {
  approved: number;
  canonicalChangeReady: number;
  generatedAt: string | null;
  packetPath: string | null;
  packetsWritten: number;
  pending: number;
  quarantined: number;
  relianceBoundary: string;
  revised: number;
  split: number;
};

export type ReliancePolicy = {
  approvalCriteria: Array<{
    criterionId: string;
    description: string;
    label: string;
    requiredFor: string;
  }>;
  approvalLevels: string[];
  canonicalChangeRules: string[];
  externalUseLimits: string[];
  generatedAt: string | null;
  policyId: string;
  purpose: string;
  relianceBoundaries: Array<{
    boundary: string;
    defaultLevel: string;
    outputType: string;
  }>;
  reviewerRoles: Array<{
    description: string;
    label: string;
    mayApplyCanonicalChanges: boolean;
    mayApproveExternalReliance: boolean;
    mayLogDecisions: boolean;
    roleId: string;
  }>;
  version: string;
};

export type ReviewerOperations = {
  assignments: Array<{
    assignedTo: string | null;
    assignmentStatus: string;
    canApplyCanonicalChanges: boolean;
    canApproveExternalReliance: boolean;
    canLogDecisions: boolean;
    effectiveDate: string | null;
    email: string | null;
    escalationPath: string[];
    label: string;
    name: string | null;
    reliancePolicyBackReference: string;
    revocationDate: string | null;
    responsibilities: string[];
    roleId: string;
  }>;
  boundary: string;
  generatedAt: string | null;
  readyForHumanAssignment: boolean;
  requiredRoles: number;
  sopPath: string | null;
  unassignedRoles: number;
};

export type RuleUnitApplyProposalSummary = {
  changes: Array<{
    action: string;
    decisionId: string;
    outcome: string;
    proposedRuleUnitIds: string[];
    ruleUnitId: string;
    validationErrors: string[];
  }>;
  decisionLogPath: string | null;
  decisionsConsidered: number;
  proposalPath: string | null;
  readyToApply: boolean;
  resultingRuleUnits: number;
  sourceRuleUnits: number;
  sourceRuleUnitsPath: string | null;
  validationErrors: string[];
};

type RuleUnitReviewRecord = {
  allowed_outcomes?: string[];
  current_rule_unit?: Record<string, unknown> & {
    action_required?: string | null;
    confidence?: number | { overall?: number };
    regulated_entity?: string | null;
    rule_type?: string | null;
  };
  issues?: string[];
  parent_regulation_id?: string;
  priority?: string;
  quality?: {
    atomicity?: number;
    entity_clarity?: number;
    exception_capture?: number;
    overall?: number;
    source_fidelity?: number;
    temporal_precision?: number;
  };
  review_id?: string;
  review_reason?: string;
  rule_unit_id?: string;
  source_context?: string | null;
  source_section?: string;
  source_sentence?: string;
  status?: string;
  suggested_outcomes?: string[];
};

type RuleUnitReviewDecisionRecord = {
  decided_at?: string;
  decided_by?: string;
  decision_id?: string;
  outcome?: "approve" | "split" | "revise" | "quarantine";
  parent_regulation_id?: string;
  previous_rule_unit?: Record<string, unknown>;
  proposed_rule_units?: Array<Record<string, unknown>>;
  rationale?: string;
  review_id?: string;
  rule_unit_id?: string;
  source_sentence?: string;
};

type RuleUnitReviewPacketRecord = {
  allowed_outcomes?: string[];
  canonical_change_ready?: boolean;
  current_rule_unit?: Record<string, unknown>;
  issues?: string[];
  logged_decision?: Record<string, unknown> | null;
  packet_id?: string;
  parent_regulation_id?: string;
  priority?: string;
  quality?: Record<string, unknown>;
  reliance_boundary?: string;
  review_id?: string;
  review_reason?: string;
  reviewer_instruction?: string;
  rule_unit_id?: string;
  source_context?: string | null;
  source_section?: string;
  source_sentence?: string;
  status?: RuleUnitReviewStatus;
  suggested_outcomes?: string[];
};

export type ProductApiSummary = {
  impactCount: number;
  needsReviewRuleUnitCount: number;
  regulationCount: number;
  requirementSource: RequirementSourceType;
  updateCount: number;
  validatedRuleUnitCount: number;
};

export type RuleUnitQualitySummary = {
  highQualityUnits: number;
  mediumQualityUnits: number;
  needsReviewUnits: number;
  qualityPath: string | null;
};

export type RuleUnitReadiness = {
  candidateFallbackActive: boolean;
  expectedSources: string[];
  quality: RuleUnitQualitySummary | null;
  status: "ready_for_rule_units" | "using_candidate_signals";
  validatedRuleUnitCount: number;
};

let manifestCache: Manifest | null = null;
let regulationIndexCache: RegulationIndexRecord[] | null = null;
let regulationToStatuteCache: CrosswalkRecord[] | null = null;
let rulemakingToRegulationCache: CrosswalkRecord[] | null = null;
let ruleUnitCache: RuleUnitRecord[] | null = null;
let ruleUnitCacheKey: string | null = null;
let outboundRelationshipMap: Map<string, CrosswalkRecord[]> | null = null;
let inboundRulemakingMap: Map<string, CrosswalkRecord[]> | null = null;
let ruleUnitByRegulationMap: Map<string, RuleUnitRecord[]> | null = null;
const bodyCache = new Map<string, string | null>();
const normalizedCache = new Map<string, NormalizedRecord | null>();

const FALLBACK_QUERY = "air quality";
const RULE_UNIT_SOURCE_PATHS = [
  path.join(REPOSITORY_ROOT, "02_Regulations_CCR", "_meta", "rule_units.jsonl"),
  path.join(REPOSITORY_ROOT, "02_Regulations_CCR", "_meta", "ccr_rule_units.jsonl"),
  path.join(REPOSITORY_ROOT, "02_Regulations_CCR", "_rule_units.jsonl"),
  path.join(REPOSITORY_ROOT, "data", "structured_output", "rule_units.jsonl"),
];
const RULE_UNIT_SUMMARY_PATH = path.join(
  REPOSITORY_ROOT,
  "02_Regulations_CCR",
  "_meta",
  "rule_units_summary.json",
);
const RULE_UNIT_REVIEW_QUEUE_PATH = path.join(
  REPOSITORY_ROOT,
  "02_Regulations_CCR",
  "_meta",
  "rule_units_review_queue.jsonl",
);
const RULE_UNIT_REVIEW_SUMMARY_PATH = path.join(
  REPOSITORY_ROOT,
  "02_Regulations_CCR",
  "_meta",
  "rule_units_review_summary.json",
);
const RULE_UNIT_REVIEW_DECISIONS_PATH = path.join(
  REPOSITORY_ROOT,
  "02_Regulations_CCR",
  "_meta",
  "rule_units_review_decisions.jsonl",
);
const RULE_UNIT_REVIEW_DECISIONS_SUMMARY_PATH = path.join(
  REPOSITORY_ROOT,
  "02_Regulations_CCR",
  "_meta",
  "rule_units_review_decisions_summary.json",
);
const RULE_UNIT_APPLY_PROPOSAL_PATH = path.join(
  REPOSITORY_ROOT,
  "02_Regulations_CCR",
  "_meta",
  "rule_units_apply_proposal.json",
);
const RULE_UNIT_REVIEW_PACKETS_PATH = path.join(
  REPOSITORY_ROOT,
  "02_Regulations_CCR",
  "_meta",
  "rule_units_review_packets.jsonl",
);
const RULE_UNIT_REVIEW_PACKETS_SUMMARY_PATH = path.join(
  REPOSITORY_ROOT,
  "02_Regulations_CCR",
  "_meta",
  "rule_units_review_packets_summary.json",
);
const RELIANCE_POLICY_PATH = path.join(
  REPOSITORY_ROOT,
  "_CONTROL_PLANE",
  "RELIANCE_POLICY.json",
);
const REVIEWER_ASSIGNMENTS_PATH = path.join(
  REPOSITORY_ROOT,
  "_CONTROL_PLANE",
  "REVIEWER_ASSIGNMENTS.json",
);
const REVIEWER_OPERATIONS_SUMMARY_PATH = path.join(
  REPOSITORY_ROOT,
  "_CONTROL_PLANE",
  "REVIEWER_OPERATIONS_SUMMARY.json",
);
const UPDATE_LEDGER_PATH = path.join(REPOSITORY_ROOT, "_CONTROL_PLANE", "UPDATE_LEDGER.jsonl");
const UPDATE_LEDGER_SUMMARY_PATH = path.join(
  REPOSITORY_ROOT,
  "_CONTROL_PLANE",
  "UPDATE_LEDGER_SUMMARY.json",
);
const RELATIONSHIP_COVERAGE_REPORT_PATH = path.join(
  REPOSITORY_ROOT,
  "_CONTROL_PLANE",
  "RELATIONSHIP_COVERAGE_REPORT.json",
);
const FULL_TEXT_DIFF_SUMMARY_PATH = path.join(
  REPOSITORY_ROOT,
  "_CONTROL_PLANE",
  "FULL_TEXT_DIFF_SUMMARY.json",
);
const SOURCE_FRESHNESS_REPORT_PATH = path.join(
  REPOSITORY_ROOT,
  "_CONTROL_PLANE",
  "SOURCE_FRESHNESS_REPORT.json",
);
const RETRIEVAL_CATALOG_SUMMARY_PATH = path.join(
  REPOSITORY_ROOT,
  "_CONTROL_PLANE",
  "RETRIEVAL_CATALOG_SUMMARY.json",
);
const PRODUCTION_READINESS_REPORT_PATH = path.join(
  REPOSITORY_ROOT,
  "_CONTROL_PLANE",
  "PRODUCTION_READINESS_REPORT.json",
);
const REMAINING_WORK_QUEUE_PATH = path.join(
  REPOSITORY_ROOT,
  "_CONTROL_PLANE",
  "REMAINING_WORK_QUEUE.json",
);
const SOURCE_STRENGTH_REPORT_PATH = path.join(
  REPOSITORY_ROOT,
  "_CONTROL_PLANE",
  "SOURCE_STRENGTH_REPORT.json",
);
const SOURCE_REPAIR_DASHBOARD_PATH = path.join(
  REPOSITORY_ROOT,
  "_CONTROL_PLANE",
  "SOURCE_REPAIR_DASHBOARD.json",
);
const MASTER_READINESS_REPORT_PATH = path.join(
  REPOSITORY_ROOT,
  "_CONTROL_PLANE",
  "MASTER_READINESS_REPORT.json",
);
const REQUIREMENT_PATTERNS: Array<{ actionType: string; keywords: string[]; title: string }> = [
  { actionType: "permit", keywords: ["permit", "license", "registration"], title: "Review permitting or registration language" },
  { actionType: "reporting", keywords: ["submit", "report", "file", "notify"], title: "Review reporting or notification language" },
  { actionType: "recordkeeping", keywords: ["maintain", "record", "retain"], title: "Review recordkeeping language" },
  { actionType: "inspection", keywords: ["inspect", "inspection"], title: "Review inspection language" },
  { actionType: "prohibition", keywords: ["shall not", "may not", "prohibited"], title: "Review prohibition language" },
  { actionType: "general", keywords: ["shall", "must", "required"], title: "Review mandatory language" },
];

const PROFILE = {
  industry: "manufacturing",
  jurisdiction: "Colorado",
  operations: ["emissions", "waste handling", "material storage", "reporting", "recordkeeping", "permitting"],
  priorities: ["reporting", "permitting", "recordkeeping", "inspection readiness"],
};

export function searchProductRegulations(query = FALLBACK_QUERY, limit = 24): ProductRegulation[] {
  const records = readRegulationIndex();
  const tokens = tokenize(query);
  const fallbackTokens = tokenize(FALLBACK_QUERY);
  const searchTokens = tokens.length > 0 ? tokens : fallbackTokens;

  return records
    .map((record) => ({ record, score: scoreRecord(record, searchTokens) }))
    .filter(({ record, score }) => Boolean(record.id) && score > 0)
    .sort((left, right) => right.score - left.score)
    .slice(0, limit)
    .map(({ record }) => toProductRegulation(record))
    .filter((record): record is ProductRegulation => record !== null);
}

export function searchRequirements(query = FALLBACK_QUERY, limit = 25): RequirementSearchResult[] {
  const tokens = tokenize(query);
  const searchTokens = tokens.length > 0 ? tokens : tokenize(FALLBACK_QUERY);
  const regulations = searchProductRegulations(query, 80);
  const results: RequirementSearchResult[] = [];

  for (const regulation of regulations) {
    for (const requirement of regulation.requirements) {
      const score = scoreRequirement(requirement, regulation, searchTokens);

      if (score <= 0) {
        continue;
      }

      results.push({
        ...requirement,
        agency: regulation.agency,
        citation: regulation.citation,
        department: regulation.department,
        regulationId: regulation.id,
        regulationTitle: regulation.title,
        score,
        sourceUrl: regulation.sourceUrl,
      });
    }
  }

  return results
    .sort((left, right) => right.score - left.score || right.confidence - left.confidence)
    .slice(0, limit);
}

export function listProductRegulations(limit = 30): ProductRegulation[] {
  return readRegulationIndex()
    .filter((record) => Boolean(record.id))
    .slice(0, limit)
    .map((record) => toProductRegulation(record))
    .filter((record): record is ProductRegulation => record !== null);
}

export function getProductRegulation(id: string): ProductRegulation | null {
  const decodedId = decodeURIComponent(id);
  const record = readRegulationIndex().find((item) => item.id === decodedId);
  return record ? toProductRegulation(record) : null;
}

export function getImpactResults(limit = 12): ImpactResult[] {
  const candidates = [
    ...searchProductRegulations(PROFILE.operations.join(" "), 48),
    ...searchProductRegulations("permit report record inspection emission waste", 48),
  ];
  const uniqueCandidates = Array.from(new Map(candidates.map((item) => [item.id, item])).values());

  return uniqueCandidates
    .map(toImpactResult)
    .sort((left, right) => right.score - left.score)
    .slice(0, limit);
}

export function getCompliancePath(limit = 10): ComplianceStep[] {
  const steps: ComplianceStep[] = [];
  const results = getImpactResults(20);

  for (const result of results) {
    for (const requirement of result.regulation.requirements) {
      if (steps.length >= limit) {
        return steps;
      }

      steps.push({
        actionType: requirement.actionType,
        actionRequired: requirement.actionRequired,
        citation: result.regulation.citation,
        confidence: requirement.confidence,
        description: buildStepDescription(result.regulation.citation, requirement),
        evidence: requirement.evidence,
        regulatedEntity: requirement.regulatedEntity,
        reason: requirement.reason,
        sourceId: result.regulation.id,
        sourceLabel: requirement.sourceLabel,
        sourceType: requirement.sourceType,
        stepOrder: steps.length + 1,
        title: requirement.title,
      });
    }
  }

  return steps;
}

export function getProductUpdates(): ProductUpdate[] {
  const manifest = readManifest();
  const layers = manifest.data_layers ?? [];

  return layers
    .filter((layer) => layer.last_ingested)
    .map((layer) => ({
      date: layer.last_ingested ?? "unknown",
      description: `${(layer.record_count ?? 0).toLocaleString("en-US")} records are marked ${layer.status ?? "unknown"}.`,
      href: layer.id === "02_Regulations_CCR" ? "/app/explore" : "/app/updates",
      label: layer.id ?? "Corpus layer",
    }))
    .sort((left, right) => right.date.localeCompare(left.date));
}

export function getUpdateLedger(limit = 50): UpdateLedgerEvent[] {
  return readJsonl<{
    confidence?: number;
    description?: string;
    event_date?: string;
    event_id?: string;
    event_type?: string;
    full_text_diff_available?: boolean;
    layer_id?: string | null;
    requires_full_diff?: boolean;
    source?: string;
    source_path?: string;
    status?: string | null;
    title?: string;
  }>(UPDATE_LEDGER_PATH)
    .map((record) => ({
      confidence: record.confidence ?? 0,
      description: record.description ?? "",
      eventDate: record.event_date ?? "unknown",
      eventId: record.event_id ?? "unknown",
      eventType: record.event_type ?? "unknown",
      fullTextDiffAvailable: record.full_text_diff_available ?? false,
      layerId: record.layer_id ?? null,
      requiresFullDiff: record.requires_full_diff ?? false,
      source: record.source ?? "unknown",
      sourcePath: record.source_path ?? "",
      status: record.status ?? null,
      title: record.title ?? "Update event",
    }))
    .slice(0, Math.max(0, limit));
}

export function getUpdateLedgerSummary(): UpdateLedgerSummary | null {
  if (!fs.existsSync(UPDATE_LEDGER_SUMMARY_PATH)) {
    return null;
  }

  try {
    const payload = JSON.parse(fs.readFileSync(UPDATE_LEDGER_SUMMARY_PATH, "utf8")) as {
      diff_status?: string;
      events_written?: number;
      full_diff_ready?: boolean;
      generated_at?: string;
      ledger_path?: string | null;
      manifest_layer_events?: number;
      next_action?: string;
      step_gate_events?: number;
      timeline_events?: number;
      update_log_events?: number;
    };

    return {
      diffStatus: payload.diff_status ?? "unknown",
      eventsWritten: payload.events_written ?? 0,
      fullDiffReady: payload.full_diff_ready ?? false,
      generatedAt: payload.generated_at ?? null,
      ledgerPath: payload.ledger_path ?? null,
      manifestLayerEvents: payload.manifest_layer_events ?? 0,
      nextAction: payload.next_action ?? "",
      stepGateEvents: payload.step_gate_events ?? 0,
      timelineEvents: payload.timeline_events ?? 0,
      updateLogEvents: payload.update_log_events ?? 0,
    };
  } catch {
    return null;
  }
}

export function getRelationshipCoverageReport(): RelationshipCoverageReport | null {
  if (!fs.existsSync(RELATIONSHIP_COVERAGE_REPORT_PATH)) {
    return null;
  }

  try {
    const payload = JSON.parse(fs.readFileSync(RELATIONSHIP_COVERAGE_REPORT_PATH, "utf8")) as {
      ccr_regulations_total?: number;
      ccr_regulations_with_relationships?: number;
      ccr_relationship_coverage_ratio?: number;
      coverage_path?: string | null;
      coverage_records?: Array<{
        confidence_average?: number | null;
        coverage_status?: string;
        crosswalk_file?: string;
        duplicate_count?: number;
        low_confidence_count?: number;
        missing_evidence_count?: number;
        missing_source_count?: number;
        missing_target_count?: number;
        relationship_count?: number;
        relationship_types?: Record<string, number>;
        source_type?: string | null;
        target_type?: string | null;
        unique_source_count?: number;
        unique_target_count?: number;
      }>;
      crosswalk_files_checked?: number;
      generated_at?: string;
      recommended_next_actions?: string[];
      structured_relationship_panel_ready?: boolean;
      total_duplicate_relationships?: number;
      total_low_confidence?: number;
      total_missing_evidence?: number;
      total_relationships?: number;
      visual_graph_deferred_reason?: string;
      visual_graph_ready?: boolean;
    };

    return {
      ccrRegulationsTotal: payload.ccr_regulations_total ?? 0,
      ccrRegulationsWithRelationships: payload.ccr_regulations_with_relationships ?? 0,
      ccrRelationshipCoverageRatio: payload.ccr_relationship_coverage_ratio ?? 0,
      coveragePath: payload.coverage_path ?? null,
      coverageRecords: (payload.coverage_records ?? []).map((record) => ({
        confidenceAverage: record.confidence_average ?? null,
        coverageStatus: record.coverage_status ?? "unknown",
        crosswalkFile: record.crosswalk_file ?? "unknown",
        duplicateCount: record.duplicate_count ?? 0,
        lowConfidenceCount: record.low_confidence_count ?? 0,
        missingEvidenceCount: record.missing_evidence_count ?? 0,
        missingSourceCount: record.missing_source_count ?? 0,
        missingTargetCount: record.missing_target_count ?? 0,
        relationshipCount: record.relationship_count ?? 0,
        relationshipTypes: record.relationship_types ?? {},
        sourceType: record.source_type ?? null,
        targetType: record.target_type ?? null,
        uniqueSourceCount: record.unique_source_count ?? 0,
        uniqueTargetCount: record.unique_target_count ?? 0,
      })),
      crosswalkFilesChecked: payload.crosswalk_files_checked ?? 0,
      generatedAt: payload.generated_at ?? null,
      recommendedNextActions: payload.recommended_next_actions ?? [],
      structuredRelationshipPanelReady: payload.structured_relationship_panel_ready ?? false,
      totalDuplicateRelationships: payload.total_duplicate_relationships ?? 0,
      totalLowConfidence: payload.total_low_confidence ?? 0,
      totalMissingEvidence: payload.total_missing_evidence ?? 0,
      totalRelationships: payload.total_relationships ?? 0,
      visualGraphDeferredReason: payload.visual_graph_deferred_reason ?? "",
      visualGraphReady: payload.visual_graph_ready ?? false,
    };
  } catch {
    return null;
  }
}

export function getFullTextDiffSummary(): FullTextDiffSummary | null {
  const payload = readJsonObject<{
    boundary?: string;
    diff_path?: string | null;
    diff_ready?: boolean;
    files_changed?: number;
    files_checked?: number;
    files_with_prior_snapshot?: number;
    files_without_snapshot?: number;
    generated_at?: string;
  }>(FULL_TEXT_DIFF_SUMMARY_PATH);
  if (!payload) {
    return null;
  }
  return {
    boundary: payload.boundary ?? "",
    diffPath: payload.diff_path ?? null,
    diffReady: payload.diff_ready ?? false,
    filesChanged: payload.files_changed ?? 0,
    filesChecked: payload.files_checked ?? 0,
    filesWithPriorSnapshot: payload.files_with_prior_snapshot ?? 0,
    filesWithoutSnapshot: payload.files_without_snapshot ?? 0,
    generatedAt: payload.generated_at ?? null,
  };
}

export function getSourceFreshnessReport(): SourceFreshnessReport | null {
  const payload = readJsonObject<{
    boundary?: string;
    generated_at?: string;
    layers?: Array<{
      age_days?: number | null;
      freshness_status?: string;
      last_checked?: string | null;
      last_ingested?: string | null;
      layer_id?: string;
      record_count?: number;
      source?: string | null;
      status?: string;
    }>;
    layers_checked?: number;
    network_refresh_performed?: boolean;
    stale_layers?: number;
    unknown_layers?: number;
  }>(SOURCE_FRESHNESS_REPORT_PATH);
  if (!payload) {
    return null;
  }
  return {
    boundary: payload.boundary ?? "",
    generatedAt: payload.generated_at ?? null,
    layers: (payload.layers ?? []).map((layer) => ({
      ageDays: layer.age_days ?? null,
      freshnessStatus: layer.freshness_status ?? "unknown",
      lastChecked: layer.last_checked ?? null,
      lastIngested: layer.last_ingested ?? null,
      layerId: layer.layer_id ?? "unknown",
      recordCount: layer.record_count ?? 0,
      source: layer.source ?? null,
      status: layer.status ?? "unknown",
    })),
    layersChecked: payload.layers_checked ?? 0,
    networkRefreshPerformed: payload.network_refresh_performed ?? false,
    staleLayers: payload.stale_layers ?? 0,
    unknownLayers: payload.unknown_layers ?? 0,
  };
}

export function getRetrievalCatalogSummary(): RetrievalCatalogSummary | null {
  const payload = readJsonObject<{
    boundary?: string;
    catalog_path?: string | null;
    generated_at?: string;
    layer_counts?: Record<string, number>;
    layers_indexed?: number;
    records_written?: number;
  }>(RETRIEVAL_CATALOG_SUMMARY_PATH);
  if (!payload) {
    return null;
  }
  return {
    boundary: payload.boundary ?? "",
    catalogPath: payload.catalog_path ?? null,
    generatedAt: payload.generated_at ?? null,
    layerCounts: payload.layer_counts ?? {},
    layersIndexed: payload.layers_indexed ?? 0,
    recordsWritten: payload.records_written ?? 0,
  };
}

export function getProductionReadinessReport(): ProductionReadinessReport | null {
  const payload = readJsonObject<{
    blockers?: string[];
    boundary?: {
      external_reliance_condition?: string;
      meaning?: string;
      not_implied?: string;
    } | string;
    controls?: Array<{
      control_id?: string;
      detail?: string;
      evidence_path?: string | null;
      status?: string;
      title?: string;
    }>;
    generated_at?: string;
    production_ready?: boolean;
    system_controls_present?: boolean;
    warnings?: string[];
  }>(PRODUCTION_READINESS_REPORT_PATH);
  if (!payload) {
    return null;
  }
  return {
    blockers: payload.blockers ?? [],
    boundary: normalizeProductionBoundary(payload.boundary),
    controls: (payload.controls ?? []).map((control) => ({
      controlId: control.control_id ?? "unknown",
      detail: control.detail ?? "",
      evidencePath: control.evidence_path ?? null,
      status: control.status ?? "unknown",
      title: control.title ?? "Control",
    })),
    generatedAt: payload.generated_at ?? null,
    systemControlsPresent: payload.system_controls_present ?? payload.production_ready ?? false,
    warnings: payload.warnings ?? [],
  };
}

export function getRemainingWorkQueue(): RemainingWorkQueue | null {
  const payload = readJsonObject<{
    generated_at?: string;
    items?: Array<{
      category?: string;
      id?: string;
      next_action?: string;
      reason?: string;
      status?: string;
      title?: string;
    }>;
    open_items?: number;
  }>(REMAINING_WORK_QUEUE_PATH);
  if (!payload) {
    return null;
  }
  return {
    generatedAt: payload.generated_at ?? null,
    items: (payload.items ?? []).map((item) => ({
      category: item.category ?? "unknown",
      id: item.id ?? "unknown",
      nextAction: item.next_action ?? "",
      reason: item.reason ?? "",
      status: item.status ?? "unknown",
      title: item.title ?? "Remaining work",
    })),
    openItems: payload.open_items ?? 0,
  };
}

export function getSourceStrengthReport(): SourceStrengthReport | null {
  const payload = readJsonObject<{
    average_source_strength_score?: number;
    boundary?: string;
    generated_at?: string;
    index_path?: string | null;
    layer_counts?: Record<string, Record<string, number>>;
    level_counts?: Record<string, number>;
    records_scored?: number;
  }>(SOURCE_STRENGTH_REPORT_PATH);
  if (!payload) {
    return null;
  }
  return {
    averageSourceStrengthScore: payload.average_source_strength_score ?? 0,
    boundary: payload.boundary ?? "",
    generatedAt: payload.generated_at ?? null,
    indexPath: payload.index_path ?? null,
    layerCounts: payload.layer_counts ?? {},
    levelCounts: payload.level_counts ?? {},
    recordsScored: payload.records_scored ?? 0,
  };
}

export function getSourceRepairDashboard(): SourceRepairDashboard | null {
  const payload = readJsonObject<{
    boundary?: string;
    freshness_refresh_items?: number;
    generated_at?: string;
    human_review_ready_for_reliance?: boolean;
    items?: Array<{
      category?: string;
      id?: string;
      next_action?: string;
      status?: string;
      title?: string;
    }>;
    open_items?: number;
    relationship_review_rows?: number;
  }>(SOURCE_REPAIR_DASHBOARD_PATH);
  if (!payload) {
    return null;
  }
  return {
    boundary: payload.boundary ?? "",
    freshnessRefreshItems: payload.freshness_refresh_items ?? 0,
    generatedAt: payload.generated_at ?? null,
    humanReviewReadyForReliance: payload.human_review_ready_for_reliance ?? false,
    items: (payload.items ?? []).map((item) => ({
      category: item.category ?? "unknown",
      id: item.id ?? "unknown",
      nextAction: item.next_action ?? "",
      status: item.status ?? "unknown",
      title: item.title ?? "Repair item",
    })),
    openItems: payload.open_items ?? 0,
    relationshipReviewRows: payload.relationship_review_rows ?? 0,
  };
}

export function getMasterReadinessReport(): MasterReadinessReport | null {
  const payload = readJsonObject<{
    blockers?: string[];
    boundary?: string;
    external_reliance_ready?: boolean;
    generated_at?: string;
    human_review?: {
      required_roles?: number;
      unassigned_roles?: number;
    };
    local_system_usable?: boolean;
    relationships?: {
      relationships_checked?: number;
      review_relationships?: number;
      strong_relationships?: number;
    };
    source_strength?: {
      average_score?: number;
      level_counts?: Record<string, number>;
      records_scored?: number;
    };
  }>(MASTER_READINESS_REPORT_PATH);
  if (!payload) {
    return null;
  }
  return {
    blockers: payload.blockers ?? [],
    boundary: payload.boundary ?? "",
    externalRelianceReady: payload.external_reliance_ready ?? false,
    generatedAt: payload.generated_at ?? null,
    humanReview: {
      requiredRoles: payload.human_review?.required_roles ?? 0,
      unassignedRoles: payload.human_review?.unassigned_roles ?? 0,
    },
    localSystemUsable: payload.local_system_usable ?? false,
    relationships: {
      relationshipsChecked: payload.relationships?.relationships_checked ?? 0,
      reviewRelationships: payload.relationships?.review_relationships ?? 0,
      strongRelationships: payload.relationships?.strong_relationships ?? 0,
    },
    sourceStrength: {
      averageScore: payload.source_strength?.average_score ?? 0,
      levelCounts: payload.source_strength?.level_counts ?? {},
      recordsScored: payload.source_strength?.records_scored ?? 0,
    },
  };
}

export function getProductApiSummary(): ProductApiSummary {
  const readiness = getRuleUnitReadiness();

  return {
    impactCount: getImpactResults(100).length,
    needsReviewRuleUnitCount: readiness.quality?.needsReviewUnits ?? 0,
    regulationCount: readRegulationIndex().filter((record) => Boolean(record.id)).length,
    requirementSource: readiness.candidateFallbackActive ? "candidate_signal" : "validated_rule_unit",
    updateCount: getProductUpdates().length,
    validatedRuleUnitCount: readiness.validatedRuleUnitCount,
  };
}

export function getProductProfile(): typeof PROFILE {
  return PROFILE;
}

export function getRuleUnitReadiness(): RuleUnitReadiness {
  const validatedRuleUnitCount = readRuleUnits().length;

  return {
    candidateFallbackActive: validatedRuleUnitCount === 0,
    expectedSources: RULE_UNIT_SOURCE_PATHS.map((filePath) => path.relative(REPOSITORY_ROOT, filePath)),
    quality: readRuleUnitQualitySummary(),
    status: validatedRuleUnitCount > 0 ? "ready_for_rule_units" : "using_candidate_signals",
    validatedRuleUnitCount,
  };
}

export function getRuleUnitReviewQueue(
  limit = 50,
  status: RuleUnitReviewStatusFilter = "pending",
): RuleUnitReviewItem[] {
  const decisionsByReviewId = latestDecisionByReviewId();
  const changeReadyRuleUnitIds = canonicalChangeReadyRuleUnitIds();

  return readJsonl<RuleUnitReviewRecord>(RULE_UNIT_REVIEW_QUEUE_PATH)
    .map((record) => toRuleUnitReviewItem(record, decisionsByReviewId, changeReadyRuleUnitIds))
    .filter((item) => reviewItemMatchesStatus(item, status))
    .slice(0, Math.max(0, limit));
}

export function getRuleUnitReviewStatusSummary(): RuleUnitReviewStatusSummary {
  const decisionsByReviewId = latestDecisionByReviewId();
  const changeReadyRuleUnitIds = canonicalChangeReadyRuleUnitIds();
  const items = readJsonl<RuleUnitReviewRecord>(RULE_UNIT_REVIEW_QUEUE_PATH).map((record) =>
    toRuleUnitReviewItem(record, decisionsByReviewId, changeReadyRuleUnitIds),
  );

  return {
    approved: items.filter((item) => item.reviewStatus === "approved").length,
    changeReady: items.filter((item) => item.canonicalChangeReady).length,
    pending: items.filter((item) => item.reviewStatus === "pending").length,
    quarantined: items.filter((item) => item.reviewStatus === "quarantined").length,
    revised: items.filter((item) => item.reviewStatus === "revised").length,
    split: items.filter((item) => item.reviewStatus === "split").length,
    total: items.length,
  };
}

export function getRuleUnitReviewSummary(): RuleUnitReviewSummary | null {
  if (!fs.existsSync(RULE_UNIT_REVIEW_SUMMARY_PATH)) {
    return null;
  }

  try {
    const payload = JSON.parse(fs.readFileSync(RULE_UNIT_REVIEW_SUMMARY_PATH, "utf8")) as {
      approve_candidates?: number;
      pending_items?: number;
      queue_path?: string | null;
      quarantine_candidates?: number;
      revise_candidates?: number;
      split_candidates?: number;
    };

    return {
      approveCandidates: payload.approve_candidates ?? 0,
      pendingItems: payload.pending_items ?? 0,
      queuePath: payload.queue_path ?? null,
      quarantineCandidates: payload.quarantine_candidates ?? 0,
      reviseCandidates: payload.revise_candidates ?? 0,
      splitCandidates: payload.split_candidates ?? 0,
    };
  } catch {
    return null;
  }
}

export function getRuleUnitReviewDecisions(limit = 100): RuleUnitReviewDecision[] {
  return readJsonl<RuleUnitReviewDecisionRecord>(RULE_UNIT_REVIEW_DECISIONS_PATH)
    .slice(-Math.max(0, limit))
    .map(toRuleUnitReviewDecision);
}

export function getRuleUnitReviewDecisionSummary(): RuleUnitReviewDecisionSummary {
  const decisions = getRuleUnitReviewDecisions(Number.MAX_SAFE_INTEGER);

  return {
    approved: decisions.filter((decision) => decision.outcome === "approve").length,
    decisionLogPath: path.relative(REPOSITORY_ROOT, RULE_UNIT_REVIEW_DECISIONS_PATH),
    quarantined: decisions.filter((decision) => decision.outcome === "quarantine").length,
    revised: decisions.filter((decision) => decision.outcome === "revise").length,
    split: decisions.filter((decision) => decision.outcome === "split").length,
    totalDecisions: decisions.length,
  };
}

export function getRuleUnitReviewPackets(
  limit = 50,
  status: RuleUnitReviewStatusFilter = "pending",
): RuleUnitReviewPacket[] {
  return readJsonl<RuleUnitReviewPacketRecord>(RULE_UNIT_REVIEW_PACKETS_PATH)
    .map(toRuleUnitReviewPacket)
    .filter((packet) => reviewPacketMatchesStatus(packet, status))
    .slice(0, Math.max(0, limit));
}

export function getRuleUnitReviewPacketSummary(): RuleUnitReviewPacketSummary | null {
  if (!fs.existsSync(RULE_UNIT_REVIEW_PACKETS_SUMMARY_PATH)) {
    return null;
  }

  try {
    const payload = JSON.parse(fs.readFileSync(RULE_UNIT_REVIEW_PACKETS_SUMMARY_PATH, "utf8")) as {
      approved?: number;
      canonical_change_ready?: number;
      generated_at?: string;
      packet_path?: string | null;
      packets_written?: number;
      pending?: number;
      quarantined?: number;
      reliance_boundary?: string;
      revised?: number;
      split?: number;
    };

    return {
      approved: payload.approved ?? 0,
      canonicalChangeReady: payload.canonical_change_ready ?? 0,
      generatedAt: payload.generated_at ?? null,
      packetPath: payload.packet_path ?? null,
      packetsWritten: payload.packets_written ?? 0,
      pending: payload.pending ?? 0,
      quarantined: payload.quarantined ?? 0,
      relianceBoundary: payload.reliance_boundary ?? "",
      revised: payload.revised ?? 0,
      split: payload.split ?? 0,
    };
  } catch {
    return null;
  }
}

export function getReliancePolicy(): ReliancePolicy | null {
  if (!fs.existsSync(RELIANCE_POLICY_PATH)) {
    return null;
  }

  try {
    const payload = JSON.parse(fs.readFileSync(RELIANCE_POLICY_PATH, "utf8")) as {
      approval_criteria?: Array<{
        criterion_id?: string;
        description?: string;
        label?: string;
        required_for?: string;
      }>;
      approval_levels?: string[];
      canonical_change_rules?: string[];
      external_use_limits?: string[];
      generated_at?: string;
      policy_id?: string;
      purpose?: string;
      reliance_boundaries?: Array<{
        boundary?: string;
        default_level?: string;
        output_type?: string;
      }>;
      reviewer_roles?: Array<{
        description?: string;
        label?: string;
        may_apply_canonical_changes?: boolean;
        may_approve_external_reliance?: boolean;
        may_log_decisions?: boolean;
        role_id?: string;
      }>;
      version?: string;
    };

    return {
      approvalCriteria: (payload.approval_criteria ?? []).map((criterion) => ({
        criterionId: criterion.criterion_id ?? "unknown",
        description: criterion.description ?? "",
        label: criterion.label ?? "Criterion",
        requiredFor: criterion.required_for ?? "research_only",
      })),
      approvalLevels: payload.approval_levels ?? [],
      canonicalChangeRules: payload.canonical_change_rules ?? [],
      externalUseLimits: payload.external_use_limits ?? [],
      generatedAt: payload.generated_at ?? null,
      policyId: payload.policy_id ?? "unknown",
      purpose: payload.purpose ?? "",
      relianceBoundaries: (payload.reliance_boundaries ?? []).map((boundary) => ({
        boundary: boundary.boundary ?? "",
        defaultLevel: boundary.default_level ?? "research_only",
        outputType: boundary.output_type ?? "output",
      })),
      reviewerRoles: (payload.reviewer_roles ?? []).map((role) => ({
        description: role.description ?? "",
        label: role.label ?? "Reviewer",
        mayApplyCanonicalChanges: role.may_apply_canonical_changes ?? false,
        mayApproveExternalReliance: role.may_approve_external_reliance ?? false,
        mayLogDecisions: role.may_log_decisions ?? false,
        roleId: role.role_id ?? "unknown",
      })),
      version: payload.version ?? "",
    };
  } catch {
    return null;
  }
}

export function getReviewerOperations(): ReviewerOperations | null {
  if (!fs.existsSync(REVIEWER_ASSIGNMENTS_PATH)) {
    return null;
  }

  try {
    const assignmentsPayload = JSON.parse(fs.readFileSync(REVIEWER_ASSIGNMENTS_PATH, "utf8")) as {
      assignment_boundary?: string;
      assignments?: Array<{
        assigned_to?: string | null;
        assignment_status?: string;
        can_apply_canonical_changes?: boolean;
        can_approve_external_reliance?: boolean;
        can_log_decisions?: boolean;
        effective_date?: string | null;
        email?: string | null;
        escalation_path?: string[];
        label?: string;
        name?: string | null;
        reliance_policy_back_reference?: string;
        revocation_date?: string | null;
        responsibilities?: string[];
        role_id?: string;
      }>;
      generated_at?: string;
    };
    const summaryPayload = fs.existsSync(REVIEWER_OPERATIONS_SUMMARY_PATH)
      ? (JSON.parse(fs.readFileSync(REVIEWER_OPERATIONS_SUMMARY_PATH, "utf8")) as {
          ready_for_human_assignment?: boolean;
          required_roles?: number;
          sop_path?: string | null;
          unassigned_roles?: number;
        })
      : {};

    return {
      assignments: (assignmentsPayload.assignments ?? []).map((assignment) => ({
        assignedTo: assignment.assigned_to ?? null,
        assignmentStatus: assignment.assignment_status ?? "unassigned",
        canApplyCanonicalChanges: assignment.can_apply_canonical_changes ?? false,
        canApproveExternalReliance: assignment.can_approve_external_reliance ?? false,
        canLogDecisions: assignment.can_log_decisions ?? false,
        effectiveDate: assignment.effective_date ?? null,
        email: assignment.email ?? null,
        escalationPath: assignment.escalation_path ?? [],
        label: assignment.label ?? "Reviewer",
        name: assignment.name ?? null,
        reliancePolicyBackReference: assignment.reliance_policy_back_reference ?? "",
        revocationDate: assignment.revocation_date ?? null,
        responsibilities: assignment.responsibilities ?? [],
        roleId: assignment.role_id ?? "unknown",
      })),
      boundary: assignmentsPayload.assignment_boundary ?? "",
      generatedAt: assignmentsPayload.generated_at ?? null,
      readyForHumanAssignment: summaryPayload.ready_for_human_assignment ?? false,
      requiredRoles: summaryPayload.required_roles ?? assignmentsPayload.assignments?.length ?? 0,
      sopPath: summaryPayload.sop_path ?? null,
      unassignedRoles: summaryPayload.unassigned_roles ?? 0,
    };
  } catch {
    return null;
  }
}

export function appendRuleUnitReviewDecision(
  input: RuleUnitReviewDecisionInput,
): RuleUnitReviewDecision {
  const reviewId = input.reviewId?.trim();
  const outcome = normalizeOutcome(input.outcome);
  const rationale = input.rationale?.trim() ?? "";
  const decidedBy = input.decidedBy?.trim() || "geode-reviewer";

  if (!reviewId) {
    throw new Error("reviewId is required.");
  }

  if (!outcome) {
    throw new Error("outcome must be approve, split, revise, or quarantine.");
  }

  if (!rationale) {
    throw new Error("rationale is required.");
  }

  const reviewItem = getRuleUnitReviewQueue(Number.MAX_SAFE_INTEGER).find(
    (item) => item.reviewId === reviewId,
  );

  if (!reviewItem) {
    throw new Error(`Unknown reviewId: ${reviewId}`);
  }

  if (!reviewItem.allowedOutcomes.includes(outcome)) {
    throw new Error(`Outcome ${outcome} is not allowed for ${reviewId}.`);
  }

  const proposedRuleUnits = input.proposedRuleUnits ?? [];

  if ((outcome === "split" || outcome === "revise") && proposedRuleUnits.length === 0) {
    throw new Error(`proposedRuleUnits are required for ${outcome} decisions.`);
  }

  const decidedAt = new Date().toISOString();
  const decision: RuleUnitReviewDecision = {
    decidedAt,
    decidedBy,
    decisionId: `RUD-${decidedAt.replace(/[^0-9TZ]/g, "")}-${reviewId}-${outcome}`,
    outcome,
    parentRegulationId: reviewItem.parentRegulationId,
    previousRuleUnit: reviewItem.currentRuleUnit as Record<string, unknown>,
    proposedRuleUnits,
    rationale,
    reviewId,
    ruleUnitId: reviewItem.ruleUnitId,
    sourceSentence: reviewItem.sourceSentence,
  };
  appendDecisionRecord(decision);
  writeDecisionSummary(getRuleUnitReviewDecisionSummary());
  return decision;
}

export function getRuleUnitApplyProposalSummary(): RuleUnitApplyProposalSummary | null {
  if (!fs.existsSync(RULE_UNIT_APPLY_PROPOSAL_PATH)) {
    return null;
  }

  try {
    const payload = JSON.parse(fs.readFileSync(RULE_UNIT_APPLY_PROPOSAL_PATH, "utf8")) as {
      changes?: Array<{
        action?: string;
        decision_id?: string;
        outcome?: string;
        proposed_rule_unit_ids?: string[];
        rule_unit_id?: string;
        validation_errors?: string[];
      }>;
      decision_log_path?: string | null;
      decisions_considered?: number;
      proposal_path?: string | null;
      ready_to_apply?: boolean;
      resulting_rule_units?: number;
      source_rule_units?: number;
      source_rule_units_path?: string | null;
      validation_errors?: string[];
    };

    return {
      changes: (payload.changes ?? []).map((change) => ({
        action: change.action ?? "unknown",
        decisionId: change.decision_id ?? "unknown",
        outcome: change.outcome ?? "unknown",
        proposedRuleUnitIds: change.proposed_rule_unit_ids ?? [],
        ruleUnitId: change.rule_unit_id ?? "unknown",
        validationErrors: change.validation_errors ?? [],
      })),
      decisionLogPath: payload.decision_log_path ?? null,
      decisionsConsidered: payload.decisions_considered ?? 0,
      proposalPath: payload.proposal_path ?? null,
      readyToApply: payload.ready_to_apply ?? false,
      resultingRuleUnits: payload.resulting_rule_units ?? 0,
      sourceRuleUnits: payload.source_rule_units ?? 0,
      sourceRuleUnitsPath: payload.source_rule_units_path ?? null,
      validationErrors: payload.validation_errors ?? [],
    };
  } catch {
    return null;
  }
}

function toProductRegulation(record: RegulationIndexRecord): ProductRegulation | null {
  if (!record.id) {
    return null;
  }

  const body = readRegulationBody(record.id);
  if (!body) {
    return null;
  }

  const normalized = readNormalizedRecord(record.id);
  const citation = record.citation ?? record.id.replaceAll("_", " ");
  const title = normalized?.rule_name ?? titleFromBody(body) ?? record.title ?? citation;

  return {
    agency: normalized?.agency_normalized ?? agencyFromTags(record.tags ?? []) ?? "Agency not stated",
    body,
    citation,
    confidence: record.confidence ?? 0.7,
    department: normalized?.department_normalized ?? "Department not stated",
    id: record.id,
    lastUpdated: record.last_updated ?? null,
    relationships: readRelationships(record.id),
    requirements: readRequirements(record.id, body),
    sections: extractSections(body),
    sourceUrl: record.source_url ?? null,
    tags: record.tags ?? [],
    title,
  };
}

function toImpactResult(regulation: ProductRegulation): ImpactResult {
  const reasons: string[] = ["Jurisdiction matches Colorado because the source is in the Colorado regulatory corpus."];
  let score = 20;
  const haystack = `${regulation.title} ${regulation.citation} ${regulation.tags.join(" ")} ${regulation.body.slice(0, 4000)}`.toLowerCase();

  if (haystack.includes("manufactur")) {
    score += 25;
    reasons.push("Industry signal matches manufacturing.");
  }

  for (const operation of PROFILE.operations) {
    if (haystack.includes(operation.replace(" ", "")) || haystack.includes(operation)) {
      score += 12;
      reasons.push(`Operation signal matches ${operation}.`);
    }
  }

  const hasValidatedRuleUnits = regulation.requirements.some((item) => item.sourceType === "validated_rule_unit");

  if (regulation.requirements.length > 0) {
    score += Math.min(25, regulation.requirements.length * 5);
    reasons.push(
      hasValidatedRuleUnits
        ? "Validated rule units are available for this source."
        : "Using candidate review signals because canonical rule units are not present yet.",
    );
  }

  if (regulation.relationships.length > 0) {
    score += 8;
    reasons.push("Related legal authority is available through crosswalk data.");
  }

  const clippedScore = Math.min(score, 100);

  return {
    evidence: regulation.requirements[0]?.evidence ?? "No candidate requirement excerpt was found in the current derived index.",
    level: impactLevel(clippedScore, regulation.requirements.length),
    reasons,
    regulation,
    score: clippedScore,
  };
}

function readRequirements(regulationId: string, body: string): CandidateRequirement[] {
  const ruleUnits = readRuleUnitsForRegulation(regulationId);

  if (ruleUnits.length > 0) {
    return ruleUnits.slice(0, 12).map(toRequirementFromRuleUnit);
  }

  return extractCandidateRequirements(body);
}

function toRequirementFromRuleUnit(ruleUnit: RuleUnitRecord): CandidateRequirement {
  const actionType = ruleUnit.rule_type ?? "requirement";
  const actionRequired = ruleUnit.action_required
    ?? ruleUnit.plain_english_summary
    ?? "Review the validated rule unit before treating it as an operational task.";
  const sourceLabel = ruleUnit.source_section ?? "Validated rule unit";

  return {
    actionType,
    actionRequired,
    confidence: confidenceValue(ruleUnit.confidence),
    conditions: ruleUnit.conditions ?? [],
    evidence: actionRequired,
    exceptions: ruleUnit.exceptions ?? [],
    id: ruleUnit.id ?? `${parentRegulationId(ruleUnit)}-${slugify(actionRequired)}`,
    regulatedEntity: ruleUnit.regulated_entity ?? null,
    reason: "Surfaced from a canonical rule-unit record produced by the extraction pipeline.",
    sourceLabel,
    sourceType: "validated_rule_unit",
    subjectTags: ruleUnit.subject_tags ?? [],
    temporal: ruleUnit.temporal ?? null,
    title: `Review ${actionType.replaceAll("_", " ")} requirement`,
  };
}

function confidenceValue(value: RuleUnitRecord["confidence"]): number {
  if (typeof value === "number") {
    return value;
  }

  if (typeof value?.overall === "number") {
    return value.overall;
  }

  return 0.8;
}

function buildStepDescription(citation: string, requirement: CandidateRequirement): string {
  if (requirement.sourceType === "validated_rule_unit") {
    return `Review whether ${citation} applies to the profile, then evaluate the validated requirement.`;
  }

  return `Review whether ${citation} applies to the profile before treating this signal as an operational task.`;
}

function impactLevel(score: number, requirementCount: number): ImpactResult["level"] {
  if (requirementCount === 0) {
    return "Unknown";
  }

  if (score >= 80) {
    return "High Impact";
  }

  if (score >= 50) {
    return "Medium Impact";
  }

  if (score >= 25) {
    return "Low Impact";
  }

  return "Informational";
}

function extractCandidateRequirements(body: string): CandidateRequirement[] {
  const lines = body.replace(/\r/g, "").split("\n");
  const requirements: CandidateRequirement[] = [];
  let currentSourceLabel = "Source text";

  for (const line of lines) {
    const trimmed = line.replace(/\s+/g, " ").trim();

    if (!trimmed) {
      continue;
    }

    if (isHeading(trimmed)) {
      currentSourceLabel = cleanHeading(trimmed);
      continue;
    }

    if (trimmed.length < 40 || trimmed.length > 620) {
      continue;
    }

    const lower = trimmed.toLowerCase();
    const match = REQUIREMENT_PATTERNS.find((pattern) => pattern.keywords.some((keyword) => lower.includes(keyword)));

    if (!match) {
      continue;
    }

    requirements.push({
      actionType: match.actionType,
      actionRequired: trimmed,
      confidence: 0.55,
      conditions: [],
      evidence: trimmed,
      exceptions: [],
      id: `candidate-${slugify(currentSourceLabel)}-${requirements.length + 1}`,
      regulatedEntity: null,
      reason: `Surfaced because the source text contains ${match.actionType} or mandatory-language signals.`,
      sourceLabel: currentSourceLabel,
      sourceType: "candidate_signal",
      subjectTags: [],
      temporal: null,
      title: match.title,
    });

    if (requirements.length >= 5) {
      return requirements;
    }
  }

  return requirements;
}

function extractSections(body: string): ProductSection[] {
  const sections: ProductSection[] = [];

  for (const line of body.split(/\r?\n/)) {
    const trimmed = line.trim();

    if (!isHeading(trimmed)) {
      continue;
    }

    sections.push({
      id: slugify(cleanHeading(trimmed)),
      level: trimmed.startsWith("#### ") ? 2 : 3,
      title: cleanHeading(trimmed),
    });

    if (sections.length >= 40) {
      break;
    }
  }

  return sections;
}

function readManifest(): Manifest {
  if (manifestCache) {
    return manifestCache;
  }

  try {
    manifestCache = JSON.parse(fs.readFileSync(MASTER_MANIFEST_PATH, "utf8")) as Manifest;
    return manifestCache;
  } catch {
    manifestCache = {};
    return {};
  }
}

function readRegulationIndex(): RegulationIndexRecord[] {
  if (regulationIndexCache) {
    return regulationIndexCache;
  }

  const manifest = readManifest();
  const layer = manifest.data_layers?.find((item) => item.id === "02_Regulations_CCR");
  const indexFile = layer?.index_file ?? "02_Regulations_CCR/_index.jsonl";
  regulationIndexCache = readJsonl<RegulationIndexRecord>(path.join(REPOSITORY_ROOT, indexFile));
  return regulationIndexCache;
}

function readRelationships(sourceId: string): ProductRelationship[] {
  const outbound = getOutboundRelationshipMap().get(sourceId) ?? [];
  const inbound = getInboundRulemakingMap().get(sourceId) ?? [];

  return [...outbound, ...inbound]
    .slice(0, 12)
    .map((record) => ({
      confidence: record.confidence ?? 0,
      evidence: record.source_evidence ?? null,
      relationship: record.relationship ?? "related",
      targetId: record.target_id && record.target_id !== sourceId ? record.target_id : record.source_id ?? "unknown",
      targetType: record.target_type ?? "unknown",
    }));
}

function readRegulationBody(id: string): string | null {
  if (bodyCache.has(id)) {
    return bodyCache.get(id) ?? null;
  }

  const rulePath = path.join(REPOSITORY_ROOT, "02_Regulations_CCR", "_rules", `${id}.md`);

  if (!fs.existsSync(rulePath)) {
    bodyCache.set(id, null);
    return null;
  }

  const body = fs.readFileSync(rulePath, "utf8").replace(/^---[\s\S]*?---/, "").trim();
  bodyCache.set(id, body);
  return body;
}

function readNormalizedRecord(id: string): NormalizedRecord | null {
  if (normalizedCache.has(id)) {
    return normalizedCache.get(id) ?? null;
  }

  const recordPath = path.join(REPOSITORY_ROOT, "02_Regulations_CCR", "_normalized", "records", `${id}.json`);

  if (!fs.existsSync(recordPath)) {
    normalizedCache.set(id, null);
    return null;
  }

  try {
    const record = JSON.parse(fs.readFileSync(recordPath, "utf8")) as NormalizedRecord;
    normalizedCache.set(id, record);
    return record;
  } catch {
    normalizedCache.set(id, null);
    return null;
  }
}

function readRegulationToStatute(): CrosswalkRecord[] {
  if (regulationToStatuteCache) {
    return regulationToStatuteCache;
  }

  regulationToStatuteCache = readJsonl<CrosswalkRecord>(path.join(REPOSITORY_ROOT, "_CROSSWALKS", "regulation_to_statute.jsonl"));
  return regulationToStatuteCache;
}

function readRulemakingToRegulation(): CrosswalkRecord[] {
  if (rulemakingToRegulationCache) {
    return rulemakingToRegulationCache;
  }

  rulemakingToRegulationCache = readJsonl<CrosswalkRecord>(path.join(REPOSITORY_ROOT, "_CROSSWALKS", "rulemaking_to_regulation.jsonl"));
  return rulemakingToRegulationCache;
}

function readRuleUnits(): RuleUnitRecord[] {
  const cacheKey = ruleUnitSourceCacheKey();

  if (ruleUnitCache && ruleUnitCacheKey === cacheKey) {
    return ruleUnitCache;
  }

  const records = RULE_UNIT_SOURCE_PATHS.flatMap((filePath) => readJsonl<RuleUnitRecord>(filePath));
  const uniqueRecords = new Map<string, RuleUnitRecord>();

  for (const record of records) {
    const parentId = parentRegulationId(record);

    if (!record.id || !parentId) {
      continue;
    }

    if (record.entity_type && record.entity_type !== "rule_unit") {
      continue;
    }

    uniqueRecords.set(record.id, record);
  }

  ruleUnitCache = Array.from(uniqueRecords.values());
  ruleUnitCacheKey = cacheKey;
  ruleUnitByRegulationMap = null;
  return ruleUnitCache;
}

function ruleUnitSourceCacheKey(): string {
  return RULE_UNIT_SOURCE_PATHS.map((filePath) => {
    if (!fs.existsSync(filePath)) {
      return `${filePath}:missing`;
    }

    const stats = fs.statSync(filePath);
    return `${filePath}:${stats.size}:${stats.mtimeMs}`;
  }).join("|");
}

function readRuleUnitsForRegulation(regulationId: string): RuleUnitRecord[] {
  const ruleUnits = readRuleUnits();

  if (!ruleUnitByRegulationMap) {
    const nextRuleUnitByRegulationMap = new Map<string, RuleUnitRecord[]>();

    for (const ruleUnit of ruleUnits) {
      const parentId = parentRegulationId(ruleUnit);

      if (!parentId) {
        continue;
      }

      const current = nextRuleUnitByRegulationMap.get(parentId) ?? [];
      current.push(ruleUnit);
      nextRuleUnitByRegulationMap.set(parentId, current);
    }

    ruleUnitByRegulationMap = nextRuleUnitByRegulationMap;
  }

  return ruleUnitByRegulationMap.get(regulationId) ?? [];
}

function readRuleUnitQualitySummary(): RuleUnitQualitySummary | null {
  if (!fs.existsSync(RULE_UNIT_SUMMARY_PATH)) {
    return null;
  }

  try {
    const payload = JSON.parse(fs.readFileSync(RULE_UNIT_SUMMARY_PATH, "utf8")) as {
      high_quality_units?: number;
      medium_quality_units?: number;
      needs_review_units?: number;
      quality_path?: string | null;
    };

    return {
      highQualityUnits: payload.high_quality_units ?? 0,
      mediumQualityUnits: payload.medium_quality_units ?? 0,
      needsReviewUnits: payload.needs_review_units ?? 0,
      qualityPath: payload.quality_path ?? null,
    };
  } catch {
    return null;
  }
}

function toRuleUnitReviewItem(
  record: RuleUnitReviewRecord,
  decisionsByReviewId = latestDecisionByReviewId(),
  changeReadyRuleUnitIds = canonicalChangeReadyRuleUnitIds(),
): RuleUnitReviewItem {
  const currentRuleUnit = record.current_rule_unit ?? {};
  const reviewId = record.review_id ?? "unknown";
  const ruleUnitId = record.rule_unit_id ?? "unknown";
  const loggedDecision = decisionsByReviewId.get(reviewId) ?? null;
  const reviewStatus = statusFromDecision(loggedDecision);

  return {
    allowedOutcomes: record.allowed_outcomes ?? [],
    canonicalChangeReady: loggedDecision ? changeReadyRuleUnitIds.has(ruleUnitId) : false,
    currentRuleUnit: {
      ...currentRuleUnit,
      actionRequired: currentRuleUnit.action_required ?? null,
      confidence: currentRuleUnit.confidence ?? undefined,
      regulatedEntity: currentRuleUnit.regulated_entity ?? null,
      ruleType: currentRuleUnit.rule_type ?? null,
    },
    issues: record.issues ?? [],
    loggedDecision: loggedDecision
      ? {
          decidedAt: loggedDecision.decidedAt,
          decisionId: loggedDecision.decisionId,
          outcome: loggedDecision.outcome,
        }
      : null,
    parentRegulationId: record.parent_regulation_id ?? "unknown",
    priority: record.priority ?? "medium",
    quality: {
      atomicity: record.quality?.atomicity,
      entityClarity: record.quality?.entity_clarity,
      exceptionCapture: record.quality?.exception_capture,
      overall: record.quality?.overall,
      sourceFidelity: record.quality?.source_fidelity,
      temporalPrecision: record.quality?.temporal_precision,
    },
    reviewId,
    reviewReason: record.review_reason ?? "Review required.",
    reviewStatus,
    ruleUnitId,
    sourceContext: record.source_context ?? null,
    sourceSection: record.source_section ?? "Source text",
    sourceSentence: record.source_sentence ?? "",
    status: record.status ?? "pending",
    suggestedOutcomes: record.suggested_outcomes ?? [],
  };
}

function toRuleUnitReviewDecision(record: RuleUnitReviewDecisionRecord): RuleUnitReviewDecision {
  return {
    decidedAt: record.decided_at ?? "",
    decidedBy: record.decided_by ?? "unknown",
    decisionId: record.decision_id ?? "unknown",
    outcome: record.outcome ?? "approve",
    parentRegulationId: record.parent_regulation_id ?? "unknown",
    previousRuleUnit: record.previous_rule_unit ?? {},
    proposedRuleUnits: record.proposed_rule_units ?? [],
    rationale: record.rationale ?? "",
    reviewId: record.review_id ?? "unknown",
    ruleUnitId: record.rule_unit_id ?? "unknown",
    sourceSentence: record.source_sentence ?? "",
  };
}

function toRuleUnitReviewPacket(record: RuleUnitReviewPacketRecord): RuleUnitReviewPacket {
  const status = normalizeReviewStatus(record.status);

  return {
    allowedOutcomes: record.allowed_outcomes ?? [],
    canonicalChangeReady: record.canonical_change_ready ?? false,
    currentRuleUnit: record.current_rule_unit ?? {},
    issues: record.issues ?? [],
    loggedDecision: record.logged_decision ?? null,
    packetId: record.packet_id ?? "unknown",
    parentRegulationId: record.parent_regulation_id ?? "unknown",
    priority: record.priority ?? "medium",
    quality: record.quality ?? {},
    relianceBoundary: record.reliance_boundary ?? "",
    reviewId: record.review_id ?? "unknown",
    reviewReason: record.review_reason ?? "Review required.",
    reviewerInstruction: record.reviewer_instruction ?? "Review the packet before relying on it.",
    ruleUnitId: record.rule_unit_id ?? "unknown",
    sourceContext: record.source_context ?? null,
    sourceSection: record.source_section ?? "Source text",
    sourceSentence: record.source_sentence ?? "",
    status,
    suggestedOutcomes: record.suggested_outcomes ?? [],
  };
}

function normalizeReviewStatus(value: string | undefined): RuleUnitReviewStatus {
  if (
    value === "approved"
    || value === "pending"
    || value === "quarantined"
    || value === "revised"
    || value === "split"
  ) {
    return value;
  }

  return "pending";
}

function reviewPacketMatchesStatus(
  packet: RuleUnitReviewPacket,
  status: RuleUnitReviewStatusFilter,
): boolean {
  if (status === "all") {
    return true;
  }

  if (status === "change_ready") {
    return packet.canonicalChangeReady;
  }

  return packet.status === status;
}

function latestDecisionByReviewId(): Map<string, RuleUnitReviewDecision> {
  const decisions = getRuleUnitReviewDecisions(Number.MAX_SAFE_INTEGER);
  const latest = new Map<string, RuleUnitReviewDecision>();

  for (const decision of decisions) {
    latest.set(decision.reviewId, decision);
  }

  return latest;
}

function canonicalChangeReadyRuleUnitIds(): Set<string> {
  const proposal = getRuleUnitApplyProposalSummary();

  if (!proposal?.readyToApply) {
    return new Set();
  }

  return new Set(
    proposal.changes
      .filter((change) => change.action === "remove" || change.action === "replace")
      .filter((change) => change.validationErrors.length === 0)
      .map((change) => change.ruleUnitId),
  );
}

function statusFromDecision(decision: RuleUnitReviewDecision | null): RuleUnitReviewStatus {
  if (!decision) {
    return "pending";
  }

  if (decision.outcome === "approve") {
    return "approved";
  }

  if (decision.outcome === "quarantine") {
    return "quarantined";
  }

  if (decision.outcome === "revise") {
    return "revised";
  }

  return "split";
}

function reviewItemMatchesStatus(
  item: RuleUnitReviewItem,
  status: RuleUnitReviewStatusFilter,
): boolean {
  if (status === "all") {
    return true;
  }

  if (status === "change_ready") {
    return item.canonicalChangeReady;
  }

  return item.reviewStatus === status;
}

function normalizeOutcome(value: string | undefined): RuleUnitReviewDecision["outcome"] | null {
  if (value === "approve" || value === "split" || value === "revise" || value === "quarantine") {
    return value;
  }

  return null;
}

function appendDecisionRecord(decision: RuleUnitReviewDecision): void {
  fs.mkdirSync(path.dirname(RULE_UNIT_REVIEW_DECISIONS_PATH), { recursive: true });
  fs.appendFileSync(
    RULE_UNIT_REVIEW_DECISIONS_PATH,
    `${JSON.stringify(toDecisionRecord(decision))}\n`,
    "utf8",
  );
}

function toDecisionRecord(decision: RuleUnitReviewDecision): RuleUnitReviewDecisionRecord {
  return {
    decided_at: decision.decidedAt,
    decided_by: decision.decidedBy,
    decision_id: decision.decisionId,
    outcome: decision.outcome,
    parent_regulation_id: decision.parentRegulationId,
    previous_rule_unit: decision.previousRuleUnit,
    proposed_rule_units: decision.proposedRuleUnits,
    rationale: decision.rationale,
    review_id: decision.reviewId,
    rule_unit_id: decision.ruleUnitId,
    source_sentence: decision.sourceSentence,
  };
}

function writeDecisionSummary(summary: RuleUnitReviewDecisionSummary): void {
  const payload = {
    approved: summary.approved,
    decision_log_path: summary.decisionLogPath,
    generated_at: new Date().toISOString(),
    quarantined: summary.quarantined,
    revised: summary.revised,
    split: summary.split,
    total_decisions: summary.totalDecisions,
  };
  const tmpPath = `${RULE_UNIT_REVIEW_DECISIONS_SUMMARY_PATH}.${process.pid}.tmp`;
  fs.writeFileSync(tmpPath, `${JSON.stringify(payload, null, 2)}\n`, "utf8");
  fs.renameSync(tmpPath, RULE_UNIT_REVIEW_DECISIONS_SUMMARY_PATH);
}

function parentRegulationId(ruleUnit: RuleUnitRecord): string | null {
  return ruleUnit.parent_regulation_id ?? ruleUnit.parentRegulationId ?? null;
}

function getOutboundRelationshipMap(): Map<string, CrosswalkRecord[]> {
  if (outboundRelationshipMap) {
    return outboundRelationshipMap;
  }

  outboundRelationshipMap = new Map();

  for (const record of readRegulationToStatute()) {
    if (!record.source_id) {
      continue;
    }

    const current = outboundRelationshipMap.get(record.source_id) ?? [];
    current.push(record);
    outboundRelationshipMap.set(record.source_id, current);
  }

  return outboundRelationshipMap;
}

function getInboundRulemakingMap(): Map<string, CrosswalkRecord[]> {
  if (inboundRulemakingMap) {
    return inboundRulemakingMap;
  }

  inboundRulemakingMap = new Map();

  for (const record of readRulemakingToRegulation()) {
    if (!record.target_id) {
      continue;
    }

    const current = inboundRulemakingMap.get(record.target_id) ?? [];
    current.push(record);
    inboundRulemakingMap.set(record.target_id, current);
  }

  return inboundRulemakingMap;
}

function readJsonl<T>(filePath: string): T[] {
  if (!fs.existsSync(filePath)) {
    return [];
  }

  return fs
    .readFileSync(filePath, "utf8")
    .split(/\r?\n/)
    .filter(Boolean)
    .map((line) => {
      try {
        return JSON.parse(line) as T;
      } catch {
        return null;
      }
    })
    .filter((record): record is T => record !== null);
}

function readJsonObject<T>(filePath: string): T | null {
  if (!fs.existsSync(filePath)) {
    return null;
  }

  for (let attempt = 1; attempt <= JSON_READ_RETRY_ATTEMPTS; attempt += 1) {
    try {
      const content = fs.readFileSync(filePath, "utf8").trim();

      if (!content) {
        throw new Error("empty JSON file");
      }

      return JSON.parse(content) as T;
    } catch {
      if (attempt === JSON_READ_RETRY_ATTEMPTS) {
        return null;
      }

      sleepSync(JSON_READ_RETRY_DELAY_MS * attempt);
    }
  }

  return null;
}

function normalizeProductionBoundary(
  boundary: {
    external_reliance_condition?: string;
    meaning?: string;
    not_implied?: string;
  } | string | undefined,
): ProductionReadinessReport["boundary"] {
  if (typeof boundary === "string") {
    return {
      externalRelianceCondition: "",
      meaning: boundary,
      notImplied: "",
    };
  }

  return {
    externalRelianceCondition: boundary?.external_reliance_condition ?? "",
    meaning: boundary?.meaning ?? "",
    notImplied: boundary?.not_implied ?? "",
  };
}

function scoreRecord(record: RegulationIndexRecord, tokens: string[]): number {
  const haystack = `${record.id ?? ""} ${record.title ?? ""} ${record.citation ?? ""} ${(record.tags ?? []).join(" ")}`.toLowerCase();
  return tokens.reduce((score, token) => score + (haystack.includes(token) ? 1 : 0), 0);
}

function scoreRequirement(
  requirement: CandidateRequirement,
  regulation: ProductRegulation,
  tokens: string[],
): number {
  const haystack = [
    requirement.actionRequired,
    requirement.actionType,
    requirement.evidence,
    requirement.reason,
    requirement.regulatedEntity ?? "",
    requirement.sourceLabel,
    requirement.subjectTags.join(" "),
    requirement.title,
    regulation.agency,
    regulation.citation,
    regulation.department,
    regulation.title,
    regulation.tags.join(" "),
  ]
    .join(" ")
    .toLowerCase();
  const tokenScore = tokens.reduce((score, token) => score + (haystack.includes(token) ? 4 : 0), 0);
  const sourceScore = requirement.sourceType === "validated_rule_unit" ? 12 : 4;
  const confidenceScore = Math.round(requirement.confidence * 10);
  const relationshipScore = Math.min(regulation.relationships.length, 4);

  return tokenScore + sourceScore + confidenceScore + relationshipScore;
}

function tokenize(value: string): string[] {
  return Array.from(
    new Set(
      value
        .toLowerCase()
        .replace(/[^a-z0-9\s-]/g, " ")
        .split(/\s+/)
        .map((token) => token.trim())
        .filter((token) => token.length >= 3),
    ),
  );
}

function titleFromBody(body: string): string | null {
  return body
    .split(/\r?\n/)
    .map((line) => line.trim())
    .find((line) => line.startsWith("#### ") || /^[A-Z][A-Z\s,;()/-]{14,}$/.test(line))
    ?.replace(/^#+\s*/, "") ?? null;
}

function isHeading(value: string): boolean {
  return value.startsWith("#### ")
    || /^(PART|RULE|REGULATION|APPENDIX)\s+[A-Z0-9]/.test(value)
    || /^[A-Z][A-Z\s,;()/-]{14,}$/.test(value)
    || /^([IVXLCDM]+\.|[A-Z]\.|[0-9]+\.)\s+[A-Z0-9]/.test(value);
}

function cleanHeading(value: string): string {
  return value.replace(/^#+\s*/, "").replace(/^[^ ]+\.\s*/, "").replace(/_/g, " ");
}

function slugify(value: string): string {
  return value
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/(^-|-$)/g, "")
    .slice(0, 80) || "section";
}

function agencyFromTags(tags: string[]): string | null {
  const agencyTag = tags.find((tag) => !["ccr", "downloaded", "normalized", "regulation_rule_acquisition"].includes(tag));

  if (!agencyTag) {
    return null;
  }

  return agencyTag
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function sleepSync(ms: number): void {
  const end = Date.now() + ms;

  while (Date.now() < end) {
    // Short synchronous retry guard for local JSON reads during atomic report rewrites.
  }
}
