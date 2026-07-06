import {
  appendRuleUnitReviewDecision,
  getRuleUnitReviewDecisionSummary,
  getRuleUnitReviewDecisions,
  type RuleUnitReviewDecisionInput,
} from "@/lib/product/productIndex";

export const dynamic = "force-dynamic";

export function GET(request: Request): Response {
  const url = new URL(request.url);
  const limit = Number(url.searchParams.get("limit") ?? "100");
  const boundedLimit = Number.isFinite(limit) ? Math.min(Math.max(limit, 1), 500) : 100;

  return Response.json({
    decisions: getRuleUnitReviewDecisions(boundedLimit),
    summary: getRuleUnitReviewDecisionSummary(),
  });
}

export async function POST(request: Request): Promise<Response> {
  try {
    const payload = (await request.json()) as RuleUnitReviewDecisionInput;
    const decision = appendRuleUnitReviewDecision(payload);

    return Response.json(
      {
        decision,
        summary: getRuleUnitReviewDecisionSummary(),
      },
      { status: 201 },
    );
  } catch (error) {
    return Response.json(
      { error: error instanceof Error ? error.message : "Unable to append decision." },
      { status: 400 },
    );
  }
}
