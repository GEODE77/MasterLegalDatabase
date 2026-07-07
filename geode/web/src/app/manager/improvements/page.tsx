import type { ReactElement } from "react";

import { ImprovementAuditScreen } from "@/components/manager/ImprovementAuditScreen";
import { requireManagerVerification } from "@/lib/manager/access";

export const dynamic = "force-dynamic";

export default async function ManagerImprovementsPage(): Promise<ReactElement> {
  const manager = await requireManagerVerification();
  return <ImprovementAuditScreen manager={manager} />;
}
