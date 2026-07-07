import type { ReactElement } from "react";

import { OpsWorkspace } from "@/components/ops/OpsWorkspace";
import { getOpsWorkspaceData } from "@/lib/product/opsWorkspace";

export const dynamic = "force-dynamic";

export default function PublishPage(): ReactElement {
  return <OpsWorkspace data={getOpsWorkspaceData()} view="publish" />;
}
