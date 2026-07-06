import { getCompliancePath, getProductProfile } from "@/lib/product/productIndex";

export const dynamic = "force-dynamic";

export function GET(request: Request): Response {
  const url = new URL(request.url);
  const limit = Number(url.searchParams.get("limit") ?? "12");
  const boundedLimit = Number.isFinite(limit) ? Math.min(Math.max(limit, 1), 50) : 12;

  return Response.json({
    profile: getProductProfile(),
    steps: getCompliancePath(boundedLimit),
  });
}
