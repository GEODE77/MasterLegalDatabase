import {
  getFullTextDiffSummary,
  getProductApiSummary,
  getProductionReadinessReport,
  getRemainingWorkQueue,
  getRetrievalCatalogSummary,
  getSourceFreshnessReport,
} from "@/lib/product/productIndex";

export const dynamic = "force-dynamic";

export function GET(): Response {
  return Response.json({
    diff: getFullTextDiffSummary(),
    freshness: getSourceFreshnessReport(),
    productionReadiness: getProductionReadinessReport(),
    remainingWork: getRemainingWorkQueue(),
    retrieval: getRetrievalCatalogSummary(),
    summary: getProductApiSummary(),
  });
}
