import { getGeodeIndexStats } from "@/lib/index/geodeIndexStats";

export const dynamic = "force-dynamic";

export function GET(): Response {
  return Response.json(getGeodeIndexStats(), {
    headers: {
      "Cache-Control": "no-store",
    },
  });
}
