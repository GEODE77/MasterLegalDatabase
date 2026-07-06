"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, type FormEvent, type ReactElement } from "react";

import { usePersonalization } from "@/hooks/usePersonalization";

export default function SignInPage(): ReactElement {
  const router = useRouter();
  const { setPreferences } = usePersonalization();
  const [email, setEmail] = useState("");
  const [touched, setTouched] = useState(false);
  const emailError = !email.trim() || isEmail(email) ? "" : "Use a valid email address.";

  async function submit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    setTouched(true);
    const trimmedEmail = email.trim();

    if (!trimmedEmail || emailError) {
      return;
    }

    await setPreferences({
      answers: [
        { key: "email", sensitivity: "private", value: trimmedEmail },
        { key: "displayName", value: displayNameFromEmail(trimmedEmail) },
      ],
    });
    router.push("/onboarding");
  }

  return (
    <main className="functional-page sign-in-page">
      <form className="sign-in-form" onSubmit={(event) => void submit(event)}>
        <p className="functional-kicker">Sign in</p>
        <label className="sign-in-label" htmlFor="email">Email</label>
        <input
          autoComplete="email"
          aria-describedby="email-validation"
          aria-invalid={touched && Boolean(emailError)}
          id="email"
          inputMode="email"
          onBlur={() => setTouched(true)}
          onChange={(event) => setEmail(event.target.value)}
          placeholder="name@company.com"
          type="email"
          value={email}
        />
        {touched ? (
          <span className={emailError ? "field-validation is-error" : "field-validation is-valid"} id="email-validation">
            {emailError || "Looks good."}
          </span>
        ) : null}
        <button disabled={!email.trim() || Boolean(emailError)} type="submit">
          Continue
        </button>
        <p className="sign-in-secondary">
          Need a magic link? <Link href="/sign-in?method=magic-link">Send one instead.</Link>
        </p>
      </form>
    </main>
  );
}

function isEmail(value: string): boolean {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value.trim());
}

function displayNameFromEmail(email: string): string {
  const [name] = email.split("@");
  const readableName = name.replace(/[._-]+/g, " ").trim();

  if (!readableName) {
    return "Geode user";
  }

  return readableName.replace(/\b\w/g, (letter) => letter.toUpperCase());
}
