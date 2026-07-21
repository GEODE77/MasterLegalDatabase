export type CorpusEntity = {
  geodeId: string;
  entityType: string;
  layer: string;
  citation: string;
  title: string;
  summary: string;
  sourceUrl: string;
  confidence: number;
  subjectTags: string[];
  industryTags: string[];
  agencyCode: string;
  effectiveDate: string;
  status: string;
};

export type TextChunk = {
  id: string;
  entityGeodeId: string;
  chunkIndex: number;
  headingPath: string[];
  text: string;
  citationScope: string;
};

export type EntityRelation = {
  id: string;
  sourceGeodeId: string;
  sourceType: string;
  targetGeodeId: string;
  targetType: string;
  relationship: string;
  confidence: number;
  sourceEvidence: string;
};

export type TimelineEvent = {
  id: string;
  legalDocumentId: string;
  eventType: string;
  label: string;
  date: string;
  sourceReference: string;
};

export type Agency = {
  code: string;
  name: string;
  jurisdiction: string;
  description: string;
  sourceUrl: string;
  entityCount: number;
  openIssues: number;
  activeRulemakings: number;
};

export type DiscussionPreview = {
  id: string;
  type: "Question" | "Explanation" | "Data Issue" | "Impact Story";
  title: string;
  status: string;
  anchor: string;
  sourceState: string;
};

export type SearchResult = {
  entity: CorpusEntity;
  matchReason: string;
};
