import { listProductRegulations, searchProductRegulations } from "@/lib/product/productIndex";

export const dynamic = "force-dynamic";

export function GET(request: Request): Response {
  const url = new URL(request.url);
  const query = url.searchParams.get("q")?.trim();
  const limit = Number(url.searchParams.get("limit") ?? "24");
  const boundedLimit = Number.isFinite(limit) ? Math.min(Math.max(limit, 1), 50) : 24;
  const regulations = query
    ? searchProductRegulations(query, boundedLimit)
    : listProductRegulations(boundedLimit);

  return Response.json({
    count: regulations.length,
    regulations: regulations.map((regulation) => ({
      agency: regulation.agency,
      citation: regulation.citation,
      confidence: regulation.confidence,
      department: regulation.department,
      id: regulation.id,
      lastUpdated: regulation.lastUpdated,
      relationshipCount: regulation.relationships.length,
      requirementCount: regulation.requirements.length,
      requirementSources: Array.from(new Set(regulation.requirements.map((item) => item.sourceType))),
      sectionCount: regulation.sections.length,
      sourceUrl: regulation.sourceUrl,
      title: regulation.title,
    })),
  });
}
