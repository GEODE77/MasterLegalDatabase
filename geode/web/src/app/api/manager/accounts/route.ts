import { NextResponse } from "next/server";

import { getCurrentManagerSession } from "@/lib/manager/access";
import {
  createManagerInvite,
  listManagerAccounts,
  listManagerAuditEvents,
  type ManagerRole,
} from "@/lib/manager/store";

export const dynamic = "force-dynamic";

const MANAGER_ROLES: ManagerRole[] = ["admin", "manager", "reviewer"];

export async function GET(): Promise<NextResponse> {
  const manager = await getCurrentManagerSession();
  if (!manager || manager.role !== "admin") {
    return NextResponse.json({ error: "Admin manager access is required." }, { status: 403 });
  }

  return NextResponse.json({
    accounts: listManagerAccounts(),
    activity: listManagerAuditEvents(),
    currentManagerId: manager.id,
  });
}

export async function POST(request: Request): Promise<NextResponse> {
  const manager = await getCurrentManagerSession();
  if (!manager || manager.role !== "admin") {
    return NextResponse.json({ error: "Admin manager access is required." }, { status: 403 });
  }

  const payload = (await request.json().catch(() => null)) as
    | { email?: unknown; name?: unknown; role?: unknown }
    | null;
  const email = typeof payload?.email === "string" ? payload.email : "";
  const name = typeof payload?.name === "string" ? payload.name : "";
  const role = typeof payload?.role === "string" && MANAGER_ROLES.includes(payload.role as ManagerRole)
    ? (payload.role as ManagerRole)
    : "manager";

  try {
    const result = createManagerInvite({ email, name, role }, manager);
    return NextResponse.json(result, { status: 201 });
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Manager invite could not be created." },
      { status: 400 },
    );
  }
}
