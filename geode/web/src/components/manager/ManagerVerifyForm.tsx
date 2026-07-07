"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useState, type FormEvent, type ReactElement } from "react";

export function ManagerVerifyForm(): ReactElement {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [code, setCode] = useState("");
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const nextPath = safeNextPath(searchParams.get("next"));

  async function submit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    setError("");
    setIsSubmitting(true);

    const response = await fetch("/api/manager/verify", {
      body: JSON.stringify({ code }),
      headers: { "Content-Type": "application/json" },
      method: "POST",
    });

    setIsSubmitting(false);

    if (!response.ok) {
      setError("That code did not open the manager workspace.");
      return;
    }

    router.replace(nextPath);
    router.refresh();
  }

  return (
    <main className="manager-verify-page">
      <section className="manager-verify-panel" aria-labelledby="manager-verify-title">
        <p>Manager verification</p>
        <h1 id="manager-verify-title">Operational tools are separate from public Geode.</h1>
        <span>
          Public users can search and read Geode without signing in. Source operations, repair queues,
          publication checks, and future download controls require manager verification.
        </span>
        <form onSubmit={(event) => void submit(event)}>
          <label htmlFor="manager-code">Access code</label>
          <input
            autoComplete="one-time-code"
            id="manager-code"
            onChange={(event) => setCode(event.target.value)}
            placeholder="Enter manager code"
            type="password"
            value={code}
          />
          {error ? <strong role="alert">{error}</strong> : null}
          <button disabled={!code.trim() || isSubmitting} type="submit">
            {isSubmitting ? "Checking" : "Open manager workspace"}
          </button>
        </form>
        <a href="/query">Continue to public resources</a>
      </section>
    </main>
  );
}

function safeNextPath(value: string | null): string {
  if (!value || !value.startsWith("/") || value.startsWith("//")) {
    return "/manager/dashboard";
  }

  if (!value.startsWith("/manager")) {
    return "/manager/dashboard";
  }

  return value;
}
