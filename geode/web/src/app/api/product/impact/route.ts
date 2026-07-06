import { getImpactResults, getProductProfile } from "@/lib/product/productIndex";

export const dynamic = "force-dynamic";

export function GET(request: Request): Response {
  const url = new URL(request.url);
  const limit = Number(url.searchParams.get("limit") ?? "16");
  const boundedLimit = Number.isFinite(limit) ? Math.min(Math.max(limit, 1), 50) : 16;

  return Response.json({
    profile: getProductProfile(),
    results: getImpactResults(boundedLimit).map((result) => ({
      evidence: result.evidence,
      level: result.level,
      reasons: result.reasons,
      regulation: {
        agency: result.regulation.agency,
        citation: result.regulation.citation,
        id: result.regulation.id,
        requirementSources: Array.from(new Set(result.regulation.requirements.map((item) => item.sourceType))),
        title: result.regulation.title,
      },
      score: result.score,
    })),
  });
}
