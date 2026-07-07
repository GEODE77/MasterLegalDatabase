import { NextResponse } from "next/server";

import { getCurrentManagerSession } from "@/lib/manager/access";
import {
  listAllManagerAuditEvents,
  listManagerAccounts,
  recordManagerAuditExport,
} from "@/lib/manager/store";

export const dynamic = "force-dynamic";

export async function GET(): Promise<NextResponse> {
  const manager = await getCurrentManagerSession();
  if (!manager || manager.role !== "admin") {
    return NextResponse.json({ error: "Admin manager access is required." }, { status: 403 });
  }

  recordManagerAuditExport(manager);
  const generatedAt = new Date().toISOString();
  const payload = {
    accounts: listManagerAccounts(),
    activity: listAllManagerAuditEvents(),
    exportedBy: {
      email: manager.email,
      id: manager.id,
      name: manager.name,
      role: manager.role,
    },
    generatedAt,
    schemaVersion: 1,
  };
  const fileDate = generatedAt.slice(0, 10);

  return new NextResponse(`${JSON.stringify(payload, null, 2)}\n`, {
    headers: {
      "Content-Disposition": `attachment; filename="geode-manager-activity-${fileDate}.json"`,
      "Content-Type": "application/json; charset=utf-8",
    },
  });
}
