import { NextResponse } from "next/server";

import { getCurrentManagerSession } from "@/lib/manager/access";
import { updateQueueOverride } from "@/lib/manager/operationOverrides";

export const dynamic = "force-dynamic";

type QueueRouteContext = {
  params: Promise<{
    id: string;
  }>;
};

export async function PATCH(request: Request, context: QueueRouteContext): Promise<NextResponse> {
  const manager = await getCurrentManagerSession();
  if (!manager) {
    return NextResponse.json({ error: "Manager access is required." }, { status: 403 });
  }

  const payload = (await request.json().catch(() => null)) as
    | {
        managerNote?: unknown;
        officialSourceConfirmation?: unknown;
        owner?: unknown;
        status?: unknown;
      }
    | null;
  const { id } = await context.params;

  const override = updateQueueOverride(
    id,
    {
      managerNote: typeof payload?.managerNote === "string" ? payload.managerNote : undefined,
      officialSourceConfirmation:
        typeof payload?.officialSourceConfirmation === "string"
          ? payload.officialSourceConfirmation
          : undefined,
      owner: typeof payload?.owner === "string" ? payload.owner : undefined,
      status: typeof payload?.status === "string" ? payload.status : undefined,
    },
    manager,
  );

  return NextResponse.json({ override });
}
