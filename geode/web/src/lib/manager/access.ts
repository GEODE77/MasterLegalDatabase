import { cookies } from "next/headers";
import { redirect } from "next/navigation";

const MANAGER_COOKIE = "geode.manager.verified";

export async function requireManagerVerification(): Promise<void> {
  const cookieStore = await cookies();
  const verified = cookieStore.get(MANAGER_COOKIE)?.value === "1";

  if (!verified) {
    redirect("/manager/verify");
  }
}
