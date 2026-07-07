export type RegulationSearchResult = {
  id: string;
  title: string;
  citation: string;
  excerpt: string;
  body: string;
  entityType?: string;
  explanation?: string;
  freshnessDetail?: string;
  freshnessStatus?: string;
  layer?: string;
  matchReasons?: string[];
  relationshipCount?: number;
  score: number;
  sourceUrl: string | null;
};

export type RegulationDetailRecord = RegulationSearchResult & {
  agency: string;
  effectiveDate: string | null;
  lastUpdated: string | null;
  tags: string[];
};

export type RegulationIndexRecord = {
  id?: string;
  title?: string;
  citation?: string;
  path?: string;
  source_url?: string;
  last_updated?: string;
  tags?: string[];
};
