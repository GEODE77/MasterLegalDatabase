import { getReliancePolicy } from "@/lib/product/productIndex";

export const dynamic = "force-dynamic";

export function GET(): Response {
  const policy = getReliancePolicy();

  if (!policy) {
    return Response.json({ error: "Reliance policy is not available." }, { status: 404 });
  }

  return Response.json({ policy });
}
