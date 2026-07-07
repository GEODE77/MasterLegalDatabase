import type { ReactElement } from "react";

import { ManagerAdminScreen } from "@/components/manager/ManagerAdminScreen";
import { requireManagerAdmin } from "@/lib/manager/access";
import { listManagerAccounts, listManagerAuditEvents } from "@/lib/manager/store";

export const dynamic = "force-dynamic";

export default async function ManagerAdminPage(): Promise<ReactElement> {
  const manager = await requireManagerAdmin();
  return (
    <ManagerAdminScreen
      accounts={listManagerAccounts()}
      activity={listManagerAuditEvents()}
      currentManager={manager}
    />
  );
}
