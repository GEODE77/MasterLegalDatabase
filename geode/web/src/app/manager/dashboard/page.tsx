import type { ReactElement } from "react";

import { OpsWorkspace } from "@/components/ops/OpsWorkspace";
import { requireManagerVerification } from "@/lib/manager/access";
import { getOpsWorkspaceData } from "@/lib/product/opsWorkspace";

export const dynamic = "force-dynamic";

export default async function ManagerDashboardPage(): Promise<ReactElement> {
  const manager = await requireManagerVerification();
  return <OpsWorkspace data={getOpsWorkspaceData()} manager={manager} view="home" />;
}
