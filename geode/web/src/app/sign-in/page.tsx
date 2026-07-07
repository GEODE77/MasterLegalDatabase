import { redirect } from "next/navigation";

export default function SignInPage(): never {
  redirect("/manager/verify");
}
