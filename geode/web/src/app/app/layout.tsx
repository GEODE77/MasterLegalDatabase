import { redirect } from "next/navigation";

export default function LegacyAppLayout(): never {
  redirect("/manager/dashboard");
}
