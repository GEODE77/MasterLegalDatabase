import { redirect } from "next/navigation";

export default function AppIndexPage(): never {
  redirect("/app/dashboard");
}
