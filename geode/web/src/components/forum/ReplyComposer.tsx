"use client";

import { useState, type FormEvent, type ReactElement } from "react";

import { readDraft, useDraftAutosave } from "@/hooks/useDraftAutosave";
import type { ForumThread } from "@/lib/forum/types";
import { usePersonalization } from "@/hooks/usePersonalization";
import { useProgressivePrompts } from "@/hooks/useProgressivePrompts";
import { useUndoToast } from "@/providers/UndoToastProvider";

type ReplyComposerProps = {
  onCreated: (thread: ForumThread) => void;
  parentId?: string | null;
  threadId: string;
};

export function ReplyComposer({ onCreated, parentId = null, threadId }: ReplyComposerProps): ReactElement {
  const draftKey = `geode.draft.reply.${threadId}.${parentId ?? "root"}`;
  const [body, setBody] = useState(readDraft(draftKey, ""));
  const [touched, setTouched] = useState(false);
  const [formError, setFormError] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const { logEvent, profile } = usePersonalization();
  const { triggerPrompt } = useProgressivePrompts();
  const { showToast } = useUndoToast();
  const draftSavedAt = useDraftAutosave(draftKey, body);
  const bodyError = body.trim().length >= 8 ? "" : "Add at least 8 characters before replying.";
  const composerTitle = parentId ? "Reply to this record note" : "Add a record reply";
  const composerId = parentId ? undefined : "reply-composer";
  const validationId = `reply-validation-${parentId ?? "root"}`;
  const draftStatusId = `reply-draft-status-${parentId ?? "root"}`;

  async function submit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    setTouched(true);

    if (bodyError) {
      return;
    }

    setFormError("");
    setIsSaving(true);

    try {
      const response = await fetch(`/api/forum/${threadId}`, {
        body: JSON.stringify({ author: profile.derived.displayName, body, parentId }),
        headers: { "Content-Type": "application/json" },
        method: "POST",
      });

      if (response.ok) {
        const data = (await response.json()) as { thread: ForumThread };
        setBody("");
        window.localStorage.removeItem(draftKey);
        onCreated(data.thread);
        void logEvent("forum_reply_created", {
          parentId: parentId ?? null,
          threadId,
        });
        void triggerPrompt("forum_reply_created");
        showToast({ message: "Your reply is live." });
      } else {
        setFormError("We could not post the reply. Add a little more context and try again.");
      }
    } catch {
      setFormError("We could not reach the forum. Your reply draft is still saved.");
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <form
      className={`reply-composer${parentId ? " reply-composer-nested" : " reply-composer-primary"}`}
      id={composerId}
      onSubmit={(event) => void submit(event)}
    >
      <div className="reply-composer-heading">
        <strong>{composerTitle}</strong>
        <span>Evidence, citation, practical impact, or a clear concern.</span>
      </div>
      <textarea
        aria-label="Reply"
        aria-describedby={`${validationId} ${draftStatusId}`}
        aria-invalid={touched && Boolean(bodyError)}
        onBlur={() => setTouched(true)}
        onChange={(event) => setBody(event.target.value)}
        placeholder="Add a concise record note."
        rows={4}
        value={body}
      />
      {touched ? (
        <span className={bodyError ? "field-validation is-error" : "field-validation is-valid"} id={validationId}>
          {bodyError || "Looks good."}
        </span>
      ) : null}
      {draftSavedAt ? <span className="draft-status" id={draftStatusId}>Draft saved {draftSavedAt}</span> : null}
      <div className="reply-composer-footer">
        <span>Replying as {profile.derived.displayName}</span>
        <button disabled={isSaving || Boolean(bodyError)} type="submit">
          {isSaving ? "Replying" : "Reply"}
        </button>
      </div>
      {formError ? <p className="form-error">{formError}</p> : null}
    </form>
  );
}
