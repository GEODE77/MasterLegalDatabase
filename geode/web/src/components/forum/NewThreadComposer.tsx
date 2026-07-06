"use client";

import { useState, type FormEvent, type ReactElement } from "react";

import { readDraft, useDraftAutosave } from "@/hooks/useDraftAutosave";
import { FORUM_TAGS, type ForumTag, type ForumThread } from "@/lib/forum/types";
import { usePersonalization } from "@/hooks/usePersonalization";
import { useProgressivePrompts } from "@/hooks/useProgressivePrompts";
import { useUndoToast } from "@/providers/UndoToastProvider";
import { tagLabel } from "./forumClient";

type NewThreadComposerProps = {
  isOpen: boolean;
  onClose: () => void;
  onCreated: (thread: ForumThread) => void;
};

const THREAD_DRAFT_KEY = "geode.draft.thread";

export function NewThreadComposer({
  isOpen,
  onClose,
  onCreated,
}: NewThreadComposerProps): ReactElement | null {
  const draft = readDraft(THREAD_DRAFT_KEY, { body: "", title: "" });
  const [body, setBody] = useState(draft.body);
  const [selectedTags, setSelectedTags] = useState<ForumTag[]>(["general"]);
  const [title, setTitle] = useState(draft.title);
  const [touched, setTouched] = useState({ body: false, title: false });
  const [formError, setFormError] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const { logEvent, profile } = usePersonalization();
  const { triggerPrompt } = useProgressivePrompts();
  const { showToast } = useUndoToast();
  const draftSavedAt = useDraftAutosave(THREAD_DRAFT_KEY, { body, title });
  const titleError = title.trim().length >= 8 ? "" : "Use at least 8 characters so others can understand the thread.";
  const bodyError = body.trim().length >= 20 ? "" : "Add at least 20 characters of context before posting.";

  if (!isOpen) {
    return null;
  }

  async function submit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    setTouched({ body: true, title: true });

    if (titleError || bodyError) {
      return;
    }

    setFormError("");
    setIsSaving(true);

    try {
      const response = await fetch("/api/forum", {
        body: JSON.stringify({ author: profile.derived.displayName, body, tags: selectedTags, title }),
        headers: { "Content-Type": "application/json" },
        method: "POST",
      });

      if (response.ok) {
        const data = (await response.json()) as { thread: ForumThread };
        onCreated(data.thread);
        void logEvent("forum_thread_created", {
          tagCount: selectedTags.length,
          titleLength: title.length,
        });
        void triggerPrompt("forum_thread_created");
        setBody("");
        setTitle("");
        setSelectedTags(["general"]);
        window.localStorage.removeItem(THREAD_DRAFT_KEY);
        onClose();
        showToast({ message: "Your thread is live." });
      } else {
        setFormError("We could not post the thread. Check the title and body, then try again.");
      }
    } catch {
      setFormError("We could not reach the forum. Keep your draft and try again.");
    } finally {
      setIsSaving(false);
    }
  }

  function toggleTag(tag: ForumTag): void {
    setSelectedTags((current) => {
      if (current.includes(tag)) {
        const next = current.filter((item) => item !== tag);
        return next.length > 0 ? next : ["general"];
      }

      return [...current, tag].slice(0, 4);
    });
  }

  return (
    <form className="thread-composer" onSubmit={(event) => void submit(event)}>
      <div className="composer-topline">
        <span>Start a thread</span>
        <button onClick={onClose} type="button">
          Cancel
        </button>
      </div>
      <div className="composer-primary">
        <label>
          <span>Title</span>
          <input
            aria-label="Thread title"
            aria-describedby="thread-title-validation"
            aria-invalid={touched.title && Boolean(titleError)}
            onBlur={() => setTouched((current) => ({ ...current, title: true }))}
            onChange={(event) => setTitle(event.target.value)}
            placeholder="What decision needs regulatory judgment?"
            value={title}
          />
          <FieldValidation id="thread-title-validation" isVisible={touched.title} message={titleError} />
        </label>
        <label>
          <span>Body</span>
          <textarea
            aria-label="Thread body"
            aria-describedby="thread-body-validation thread-draft-status"
            aria-invalid={touched.body && Boolean(bodyError)}
            onBlur={() => setTouched((current) => ({ ...current, body: true }))}
            onChange={(event) => setBody(event.target.value)}
            placeholder="State the fact pattern, the uncertainty, and the decision this should inform."
            rows={8}
            value={body}
          />
          <FieldValidation id="thread-body-validation" isVisible={touched.body} message={bodyError} />
          {draftSavedAt ? <span className="draft-status" id="thread-draft-status">Draft saved {draftSavedAt}</span> : null}
        </label>
        <div className="composer-tags" aria-label="Thread tags">
          <span>Tags</span>
          <div>
            {FORUM_TAGS.map((tag) => (
              <button
                className={selectedTags.includes(tag) ? "is-selected" : ""}
                key={tag}
                onClick={() => toggleTag(tag)}
                type="button"
              >
                /{tagLabel(tag)}
              </button>
            ))}
          </div>
        </div>
      </div>
      <div className="composer-footer">
        <span>Writing as {profile.derived.displayName}</span>
        <button disabled={isSaving || Boolean(titleError || bodyError)} type="submit">
          {isSaving ? "Starting" : "Start thread"}
        </button>
      </div>
      {formError ? <p className="form-error">{formError}</p> : null}
    </form>
  );
}

function FieldValidation({
  id,
  isVisible,
  message,
}: {
  id: string;
  isVisible: boolean;
  message: string;
}): ReactElement | null {
  if (!isVisible) {
    return null;
  }

  return (
    <span className={message ? "field-validation is-error" : "field-validation is-valid"} id={id}>
      {message || "Looks good."}
    </span>
  );
}
