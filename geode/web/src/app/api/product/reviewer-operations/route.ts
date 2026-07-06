import { getReviewerOperations } from "@/lib/product/productIndex";

export const dynamic = "force-dynamic";

export function GET(): Response {
  const operations = getReviewerOperations();

  if (!operations) {
    return Response.json({ error: "Reviewer operations are not available." }, { status: 404 });
  }

  return Response.json({ operations });
}
