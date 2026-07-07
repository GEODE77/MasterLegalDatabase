import { redirect } from "next/navigation";

import { requireManagerVerification } from "@/lib/manager/access";

export default async function ManagerIndexPage(): Promise<never> {
  await requireManagerVerification();
  redirect("/manager/dashboard");
}
