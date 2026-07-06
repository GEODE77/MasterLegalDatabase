import {
  getRuleUnitReviewPacketSummary,
  getRuleUnitReviewPackets,
  type RuleUnitReviewStatusFilter,
} from "@/lib/product/productIndex";

export const dynamic = "force-dynamic";

export function GET(request: Request): Response {
  const url = new URL(request.url);
  const limit = Number(url.searchParams.get("limit") ?? "50");
  const boundedLimit = Number.isFinite(limit) ? Math.min(Math.max(limit, 1), 200) : 50;
  const status = normalizeStatus(url.searchParams.get("status"));

  return Response.json({
    packets: getRuleUnitReviewPackets(boundedLimit, status),
    status,
    summary: getRuleUnitReviewPacketSummary(),
  });
}

function normalizeStatus(value: string | null): RuleUnitReviewStatusFilter {
  if (
    value === "all"
    || value === "approved"
    || value === "change_ready"
    || value === "pending"
    || value === "quarantined"
    || value === "revised"
    || value === "split"
  ) {
    return value;
  }

  return "pending";
}
