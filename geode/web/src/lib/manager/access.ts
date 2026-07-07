import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { readManagerSession, type ManagerSession } from "@/lib/manager/store";

const MANAGER_COOKIE = "geode.manager.session";

export async function requireManagerVerification(): Promise<ManagerSession> {
  const cookieStore = await cookies();
  let session: ManagerSession | null = null;
  try {
    session = readManagerSession(cookieStore.get(MANAGER_COOKIE)?.value);
  } catch {
    session = null;
  }

  if (!session) {
    redirect("/manager/verify");
  }

  return session;
}
