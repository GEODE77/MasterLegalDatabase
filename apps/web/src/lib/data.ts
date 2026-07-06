import {
  agencies,
  chunks,
  discussions,
  entities,
  relations,
  searchResults,
  timelineEvents
} from "./sample-data";
import type {
  Agency,
  CorpusEntity,
  DiscussionPreview,
  EntityRelation,
  SearchResult,
  TextChunk,
  TimelineEvent
} from "./types";

const apiBaseUrl = process.env.GEODE_API_BASE_URL;

type ApiEntity = {
  geode_id: string;
  entity_type: string;
  layer: string;
  citation?: string | null;
  title: string;
  summary?: string | null;
  source_url?: string | null;
  confidence: number;
  subject_tags: string[];
  industry_tags: string[];
  agency_code?: string | null;
  effective_date?: string | null;
  status?: string | null;
};

export async function getDashboardData() {
  return {
    entities,
    timelineEvents,
    discussions,
    agencies
  };
}

export async function searchCorpus(query: string): Promise<SearchResult[]> {
  if (apiBaseUrl && query.trim()) {
    try {
      const response = await fetch(`${apiBaseUrl}/api/search?q=${encodeURIComponent(query)}`, {
        next: { revalidate: 30 }
      });
      if (response.ok) {
        const payload = (await response.json()) as Array<{ entity: ApiEntity; match_reason: string }>;
        return payload.map((item) => ({
          entity: fromApiEntity(item.entity),
          matchReason: item.match_reason
        }));
      }
    } catch {
      return fallbackSearch(query);
    }
  }
  return fallbackSearch(query);
}

export async function getEntity(geodeId: string): Promise<CorpusEntity | undefined> {
  if (apiBaseUrl) {
    try {
      const response = await fetch(`${apiBaseUrl}/api/entities/${encodeURIComponent(geodeId)}`, {
        next: { revalidate: 30 }
      });
      if (response.ok) {
        return fromApiEntity((await response.json()) as ApiEntity);
      }
    } catch {
      return entities.find((entity) => entity.geodeId === geodeId);
    }
  }
  return entities.find((entity) => entity.geodeId === geodeId);
}

export async function getEntityChunks(geodeId: string): Promise<TextChunk[]> {
  return chunks.filter((chunk) => chunk.entityGeodeId === geodeId);
}

export async function getEntityRelations(geodeId: string): Promise<EntityRelation[]> {
  return relations.filter(
    (relation) => relation.sourceGeodeId === geodeId || relation.targetGeodeId === geodeId
  );
}

export async function getEntityTimeline(geodeId: string): Promise<TimelineEvent[]> {
  return timelineEvents.filter((event) => event.legalDocumentId === geodeId);
}

export async function getAgency(code: string): Promise<Agency | undefined> {
  return agencies.find((agency) => agency.code === code);
}

export async function getAgencyEntities(code: string): Promise<CorpusEntity[]> {
  return entities.filter((entity) => entity.agencyCode === code);
}

export async function getDiscussionsForEntity(geodeId: string): Promise<DiscussionPreview[]> {
  return discussions.filter((discussion) => discussion.anchor.includes(geodeId.split("-").slice(0, 3).join("-"))
    || discussion.anchor.includes(geodeId.replace(/_/g, " ")));
}

function fallbackSearch(query: string): SearchResult[] {
  const normalized = query.trim().toLowerCase();
  if (!normalized) {
    return searchResults;
  }
  return searchResults.filter(({ entity }) =>
    [
      entity.geodeId,
      entity.citation,
      entity.title,
      entity.summary,
      entity.agencyCode,
      ...entity.subjectTags,
      ...entity.industryTags
    ]
      .join(" ")
      .toLowerCase()
      .includes(normalized)
  );
}

function fromApiEntity(entity: ApiEntity): CorpusEntity {
  return {
    geodeId: entity.geode_id,
    entityType: entity.entity_type,
    layer: entity.layer,
    citation: entity.citation ?? entity.geode_id,
    title: entity.title,
    summary: entity.summary ?? "",
    sourceUrl: entity.source_url ?? "",
    confidence: entity.confidence,
    subjectTags: entity.subject_tags ?? [],
    industryTags: entity.industry_tags ?? [],
    agencyCode: entity.agency_code ?? "",
    effectiveDate: entity.effective_date ?? "",
    status: entity.status ?? "indexed"
  };
}
