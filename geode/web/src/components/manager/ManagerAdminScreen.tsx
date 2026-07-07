"use client";

import { useState, type FormEvent, type ReactElement } from "react";

import type { ManagerAccountSummary, ManagerAuditEvent, ManagerRole, ManagerSession } from "@/lib/manager/store";

type ManagerAdminScreenProps = {
  accounts: ManagerAccountSummary[];
  activity: ManagerAuditEvent[];
  currentManager: ManagerSession;
};

type AdminState = {
  accounts: ManagerAccountSummary[];
  activity: ManagerAuditEvent[];
};

type InviteResult = {
  email: string;
  inviteCode: string;
  name: string;
};

const ROLES: ManagerRole[] = ["admin", "manager", "reviewer"];

export function ManagerAdminScreen({
  accounts,
  activity,
  currentManager,
}: ManagerAdminScreenProps): ReactElement {
  const [state, setState] = useState<AdminState>({ accounts, activity });
  const [inviteResult, setInviteResult] = useState<InviteResult | null>(null);
  const [message, setMessage] = useState("");
  const [isWorking, setIsWorking] = useState(false);

  async function refreshAccounts(): Promise<void> {
    const response = await fetch("/api/manager/accounts", { cache: "no-store" });
    if (!response.ok) {
      setMessage("The manager list could not be refreshed.");
      return;
    }

    const payload = (await response.json()) as AdminState;
    setState({
      accounts: payload.accounts,
      activity: payload.activity,
    });
  }

  async function createInvite(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    setIsWorking(true);
    setMessage("");
    setInviteResult(null);

    const form = new FormData(event.currentTarget);
    const response = await fetch("/api/manager/accounts", {
      body: JSON.stringify({
        email: form.get("email"),
        name: form.get("name"),
        role: form.get("role"),
      }),
      headers: { "Content-Type": "application/json" },
      method: "POST",
    });
    const payload = (await response.json().catch(() => null)) as
      | { error?: string; inviteCode?: string; manager?: ManagerAccountSummary }
      | null;

    setIsWorking(false);
    if (!response.ok || !payload?.inviteCode || !payload.manager) {
      setMessage(payload?.error ?? "The manager invite could not be created.");
      return;
    }

    event.currentTarget.reset();
    setInviteResult({
      email: payload.manager.email,
      inviteCode: payload.inviteCode,
      name: payload.manager.name,
    });
    await refreshAccounts();
  }

  async function revokeAccount(managerId: string): Promise<void> {
    setIsWorking(true);
    setMessage("");
    const response = await fetch(`/api/manager/accounts/${managerId}/revoke`, { method: "POST" });
    const payload = (await response.json().catch(() => null)) as { error?: string } | null;
    setIsWorking(false);
    if (!response.ok) {
      setMessage(payload?.error ?? "The manager account could not be revoked.");
      return;
    }

    await refreshAccounts();
  }

  return (
    <main className="ops-page">
      <section className="ops-manager-strip" aria-label="Verified admin manager">
        <span>Verified admin</span>
        <strong>{currentManager.name}</strong>
        <p>{currentManager.role}</p>
      </section>

      <section className="ops-intro">
        <p>Manager Administration</p>
        <h2>Create, revoke, and review manager access.</h2>
        <span>Only approved admins can open this screen. Invite codes appear once and are not stored.</span>
      </section>

      <section className="manager-admin-grid" aria-label="Manager administration">
        <form className="manager-admin-form" onSubmit={createInvite}>
          <header>
            <span>Create invite</span>
            <h3>New manager account</h3>
          </header>
          <label>
            Name
            <input name="name" placeholder="Manager name" required />
          </label>
          <label>
            Email
            <input name="email" placeholder="manager@example.com" required type="email" />
          </label>
          <label>
            Role
            <select defaultValue="manager" name="role">
              {ROLES.map((role) => (
                <option key={role} value={role}>
                  {role}
                </option>
              ))}
            </select>
          </label>
          <button disabled={isWorking} type="submit">
            Create invite
          </button>
          {message ? <p className="manager-admin-message">{message}</p> : null}
          {inviteResult ? (
            <section className="manager-invite-result" aria-live="polite">
              <span>One-time invite for {inviteResult.name}</span>
              <strong>{inviteResult.inviteCode}</strong>
              <p>Send this privately to {inviteResult.email}. It will not be shown again.</p>
            </section>
          ) : null}
        </form>

        <section className="manager-activity-panel">
          <header className="manager-activity-header">
            <div>
              <span>Recent activity</span>
              <h3>Review history</h3>
            </div>
            <a className="manager-export-link" href="/api/manager/accounts/export">
              Export audit file
            </a>
          </header>
          <div className="manager-activity-list">
            {state.activity.length ? (
              state.activity.map((event) => (
                <article key={`${event.managerId}-${event.action}-${event.occurredAt}`}>
                  <strong>{event.action.replaceAll("_", " ")}</strong>
                  <p>{event.managerName}</p>
                  <span>{shortDateTime(event.occurredAt)}</span>
                </article>
              ))
            ) : (
              <p>No manager activity has been logged yet.</p>
            )}
          </div>
        </section>
      </section>

      <section className="manager-account-table" aria-label="Manager accounts">
        <header>
          <span>{state.accounts.length} accounts</span>
          <h3>Access registry</h3>
        </header>
        <div>
          {state.accounts.map((account) => (
            <article key={account.id}>
              <div>
                <strong>{account.name}</strong>
                <p>{account.email}</p>
              </div>
              <span>{account.role}</span>
              <span>{account.status}</span>
              <span>{account.lastEventAt ? shortDateTime(account.lastEventAt) : "no activity"}</span>
              <button
                disabled={isWorking || account.status === "revoked" || account.id === currentManager.id}
                onClick={() => void revokeAccount(account.id)}
                type="button"
              >
                Revoke
              </button>
            </article>
          ))}
        </div>
      </section>
    </main>
  );
}

function shortDateTime(value: string): string {
  return value.slice(0, 16).replace("T", " ");
}
