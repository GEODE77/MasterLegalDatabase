import { getRuleUnitReadiness } from "@/lib/product/productIndex";

export const dynamic = "force-dynamic";

export function GET(): Response {
  return Response.json({
    readiness: getRuleUnitReadiness(),
  });
}
