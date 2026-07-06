import { getProductApiSummary, getRelationshipCoverageReport } from "@/lib/product/productIndex";

export const dynamic = "force-dynamic";

export function GET(): Response {
  return Response.json({
    relationshipCoverage: getRelationshipCoverageReport(),
    summary: getProductApiSummary(),
  });
}
