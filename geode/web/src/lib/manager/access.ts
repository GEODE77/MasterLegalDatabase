import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { readManagerSession, type ManagerSession } from "@/lib/manager/store";

const MANAGER_COOKIE = "geode.manager.session";

export async function requireManagerVerification(): Promise<ManagerSession> {
  const session = await getCurrentManagerSession();

  if (!session) {
    redirect("/manager/verify");
  }

  return session;
}

export async function requireManagerAdmin(): Promise<ManagerSession> {
  const session = await requireManagerVerification();
  if (session.role !== "admin") {
    redirect("/manager/dashboard");
  }

  return session;
}

export async function getCurrentManagerSession(): Promise<ManagerSession | null> {
  const cookieStore = await cookies();
  let session: ManagerSession | null = null;
  try {
    session = readManagerSession(cookieStore.get(MANAGER_COOKIE)?.value);
  } catch {
    session = null;
  }

  return session;
}
