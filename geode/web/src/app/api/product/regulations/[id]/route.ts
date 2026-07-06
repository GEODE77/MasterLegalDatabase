import { getProductRegulation } from "@/lib/product/productIndex";

export const dynamic = "force-dynamic";

type RegulationRouteProps = {
  params: Promise<{ id: string }>;
};

export async function GET(_request: Request, { params }: RegulationRouteProps): Promise<Response> {
  const { id } = await params;
  const regulation = getProductRegulation(id);

  if (!regulation) {
    return Response.json({ error: "Regulation not found." }, { status: 404 });
  }

  return Response.json({
    regulation,
  });
}
