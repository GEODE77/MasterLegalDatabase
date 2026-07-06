import { searchRequirements } from "@/lib/product/productIndex";

export const dynamic = "force-dynamic";

export function GET(request: Request): Response {
  const url = new URL(request.url);
  const query = url.searchParams.get("q")?.trim() ?? "";
  const limit = Number(url.searchParams.get("limit") ?? "25");
  const boundedLimit = Number.isFinite(limit) ? Math.min(Math.max(limit, 1), 75) : 25;
  const requirements = searchRequirements(query, boundedLimit);

  return Response.json({
    count: requirements.length,
    query: query || "air quality",
    requirements: requirements.map((requirement) => ({
      actionRequired: requirement.actionRequired,
      actionType: requirement.actionType,
      agency: requirement.agency,
      citation: requirement.citation,
      confidence: requirement.confidence,
      department: requirement.department,
      evidence: requirement.evidence,
      id: requirement.id,
      reason: requirement.reason,
      regulatedEntity: requirement.regulatedEntity,
      regulationId: requirement.regulationId,
      regulationTitle: requirement.regulationTitle,
      score: requirement.score,
      sourceLabel: requirement.sourceLabel,
      sourceType: requirement.sourceType,
      sourceUrl: requirement.sourceUrl,
      title: requirement.title,
    })),
  });
}
