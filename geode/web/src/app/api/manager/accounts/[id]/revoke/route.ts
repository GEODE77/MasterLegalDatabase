import { NextResponse } from "next/server";

import { getCurrentManagerSession } from "@/lib/manager/access";
import { revokeManagerAccount } from "@/lib/manager/store";

export const dynamic = "force-dynamic";

type RevokeRouteContext = {
  params: Promise<{
    id: string;
  }>;
};

export async function POST(_request: Request, context: RevokeRouteContext): Promise<NextResponse> {
  const manager = await getCurrentManagerSession();
  if (!manager || manager.role !== "admin") {
    return NextResponse.json({ error: "Admin manager access is required." }, { status: 403 });
  }

  const { id } = await context.params;
  try {
    return NextResponse.json({ account: revokeManagerAccount(id, manager) });
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Manager account could not be revoked." },
      { status: 400 },
    );
  }
}
