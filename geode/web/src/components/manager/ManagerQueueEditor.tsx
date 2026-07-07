"use client";

import { useRouter } from "next/navigation";
import { useState, type FormEvent, type ReactElement } from "react";

import type { OpsQueueItem } from "@/lib/product/opsWorkspace";

type ManagerQueueEditorProps = {
  item: OpsQueueItem;
};

const STATUS_OPTIONS = ["queued", "in_review", "waiting_official_source", "blocked", "complete"];

export function ManagerQueueEditor({ item }: ManagerQueueEditorProps): ReactElement {
  const router = useRouter();
  const [message, setMessage] = useState("");
  const [isSaving, setIsSaving] = useState(false);

  async function saveQueueItem(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    setIsSaving(true);
    setMessage("");
    const form = new FormData(event.currentTarget);
    const response = await fetch(`/api/manager/queue/${encodeURIComponent(item.id)}`, {
      body: JSON.stringify({
        managerNote: form.get("managerNote"),
        officialSourceConfirmation: form.get("officialSourceConfirmation"),
        owner: form.get("owner"),
        status: form.get("status"),
      }),
      headers: { "Content-Type": "application/json" },
      method: "PATCH",
    });

    setIsSaving(false);
    if (response.ok) {
      setMessage("Saved.");
      router.refresh();
      return;
    }

    setMessage("The queue item was not saved.");
  }

  return (
    <form className="manager-queue-editor" onSubmit={saveQueueItem}>
      <label>
        Owner
        <input defaultValue={item.owner} name="owner" />
      </label>
      <label>
        Status
        <select defaultValue={item.status} name="status">
          {STATUS_OPTIONS.map((status) => (
            <option key={status} value={status}>
              {status.replaceAll("_", " ")}
            </option>
          ))}
        </select>
      </label>
      <label>
        Manager note
        <textarea defaultValue={item.managerNote} name="managerNote" rows={2} />
      </label>
      <label>
        Official source confirmation
        <textarea defaultValue={item.officialSourceConfirmation} name="officialSourceConfirmation" rows={2} />
      </label>
      <button disabled={isSaving} type="submit">
        {isSaving ? "Saving" : "Save queue item"}
      </button>
      {message ? <p>{message}</p> : null}
    </form>
  );
}
