"use client";

import Link from "next/link";
import { useCallback, useEffect, useState, type CSSProperties, type ReactElement } from "react";

import { ForumTagChip } from "@/components/forum/ForumTagChip";
import { ReplyComposer } from "@/components/forum/ReplyComposer";
import { VoteButton } from "@/components/forum/VoteButton";
import { PublicNav } from "@/components/navigation/PublicNav";
import { usePersonalization } from "@/hooks/usePersonalization";
import { useProgressivePrompts } from "@/hooks/useProgressivePrompts";
import type { ForumReply, ForumThread } from "@/lib/forum/types";
import { useUndoToast } from "@/providers/UndoToastProvider";
import {
  authorInitials,
  contributorRank,
  impactLabel,
  issueTypeLabel,
  preciseTime,
  relativeTime,
  statusLabel,
  verificationLabel,
} from "./forumClient";

type ThreadDetailProps = {
  id: string;
};

export function ThreadDetail({ id }: ThreadDetailProps): ReactElement {
  const [thread, setThread] = useState<ForumThread | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const { logEvent } = usePersonalization();
  const { triggerPrompt } = useProgressivePrompts();
  const { showToast } = useUndoToast();

  const loadThread = useCallback(async (): Promise<void> => {
    const response = await fetch(`/api/forum/${id}`, { cache: "no-store" });

    if (response.ok) {
      const data = (await response.json()) as { thread: ForumThread };
      setThread(data.thread);
    }

    setIsLoading(false);
  }, [id]);

  useEffect(() => {
    void loadThread();
  }, [loadThread]);

  async function vote(target: "thread" | "reply", delta: number, replyId?: string): Promise<void> {
    const response = await fetch(`/api/forum/${id}`, {
      body: JSON.stringify({ delta, replyId, target }),
      headers: { "Content-Type": "application/json" },
      method: "PATCH",
    });

    if (response.ok) {
      const data = (await response.json()) as { thread: ForumThread };
      setThread(data.thread);
      void logEvent("forum_vote", { delta, replyId: replyId ?? null, target });
      void triggerPrompt("forum_vote_cast");
      showToast({ message: "Your vote is recorded." });
    }
  }

  const rootReplies = thread?.replies.filter((reply) => reply.parentId === null) ?? [];
  return (
    <main className="forum-page thread-page">
      <PublicNav current="forum" />
      <header className="forum-header thread-detail-header">
        <p className="forum-section-label">Forum record</p>
        <Link className="query-back" href="/forum">
          Back to forum
        </Link>
      </header>

      {isLoading ? <ThreadDetailSkeleton /> : null}
      {!isLoading && !thread ? (
        <div className="forum-empty recovery-state">
          <span className="recovery-illustration" aria-hidden="true" />
          <p>We could not find this thread. Return to the forum and choose another discussion.</p>
          <Link href="/forum">Open the forum</Link>
        </div>
      ) : null}
      {thread ? (
        <article className="thread-detail-shell">
          <div className="thread-detail-main">
            <div className="thread-byline">
              <span className="thread-author-avatar" aria-hidden="true">
                {authorInitials(thread.author)}
              </span>
              <span>{thread.author}</span>
              <span>{contributorRank(thread.author, thread.votes)}</span>
              <span>{preciseTime(thread.createdAt)}</span>
              <span>{thread.replies.length} replies</span>
            </div>
            <div className="thread-issue-summary" aria-label="Issue record">
              <span className="issue-type-pill">{issueTypeLabel(thread.issueType)}</span>
              <span className={`issue-status issue-status-${thread.status}`}>
                {statusLabel(thread.status)}
              </span>
              <span>{impactLabel(thread.impactLevel)} impact</span>
              <span>{verificationLabel(thread.verificationStatus)}</span>
            </div>
            <h1>{thread.title}</h1>
            <section className="issue-record-panel" aria-label="Issue action summary">
              <div>
                <span>Affected audience</span>
                <strong>{thread.affectedAudience}</strong>
              </div>
              <div>
                <span>Legal source</span>
                <strong>{thread.legalSource}</strong>
              </div>
              <div>
                <span>Requested action</span>
                <strong>{thread.actionLabel}</strong>
              </div>
              <div>
                <span>Action date</span>
                <strong>{thread.deadline ?? "No fixed date"}</strong>
              </div>
            </section>
            <div className="thread-tags">
              {thread.tags.map((tag) => (
                <ForumTagChip key={tag} tag={tag} />
              ))}
            </div>
            <div className="thread-body">
              {thread.body.split(/\n{2,}/).map((paragraph) => (
                <p key={paragraph}>{paragraph}</p>
              ))}
            </div>
            <div className="issue-action-controls" aria-label="Issue action controls">
              <button onClick={() => void vote("thread", 1)} type="button">
                Support action
              </button>
              <button onClick={() => void vote("thread", -1)} type="button">
                Flag concern
              </button>
              <span>{thread.votes} support signals on record</span>
            </div>
            <ReplyComposer onCreated={setThread} threadId={thread.id} />
            <section className="reply-section" aria-label="Replies">
              <div className="reply-section-heading">
                <strong>Record replies</strong>
                <span>{thread.replies.length} on record</span>
              </div>
              {rootReplies.length === 0 ? (
                <div className="forum-empty compact recovery-state">
                  <span className="recovery-illustration" aria-hidden="true" />
                  <p>No interpretations yet. Add the first practical read, citation, or operational warning.</p>
                  <a href="#reply-composer">Reply</a>
                </div>
              ) : null}
              {rootReplies.map((reply) => (
                <ReplyNode
                  depth={0}
                  key={reply.id}
                  onThreadChange={setThread}
                  reply={reply}
                  thread={thread}
                  vote={vote}
                />
              ))}
            </section>
          </div>
        </article>
      ) : null}
    </main>
  );
}

function ThreadDetailSkeleton(): ReactElement {
  return (
    <article className="thread-detail-shell thread-detail-skeleton" aria-hidden="true">
      <div className="thread-detail-main">
        <div className="thread-byline">
          <span className="skeleton-line skeleton-meta" />
          <span className="skeleton-line skeleton-meta" />
          <span className="skeleton-line skeleton-meta" />
        </div>
        <span className="skeleton-line skeleton-heading" />
        <div className="thread-tags">
          <span className="skeleton-line skeleton-meta" />
          <span className="skeleton-line skeleton-meta" />
        </div>
        <div className="thread-body">
          <span className="skeleton-line skeleton-paragraph" />
          <span className="skeleton-line skeleton-paragraph short" />
          <span className="skeleton-line skeleton-paragraph" />
          <span className="skeleton-line skeleton-paragraph medium" />
        </div>
        <div className="reply-section">
          <div className="reply-section-heading">
            <span className="skeleton-line skeleton-meta" />
            <span className="skeleton-line skeleton-meta" />
          </div>
          <span className="skeleton-block skeleton-composer" />
        </div>
      </div>
    </article>
  );
}

type ReplyNodeProps = {
  depth: number;
  onThreadChange: (thread: ForumThread) => void;
  reply: ForumReply;
  thread: ForumThread;
  vote: (target: "thread" | "reply", delta: number, replyId?: string) => Promise<void>;
};

function ReplyNode({ depth, onThreadChange, reply, thread, vote }: ReplyNodeProps): ReactElement {
  const [isReplying, setIsReplying] = useState(false);
  const children = thread.replies.filter((item) => item.parentId === reply.id);

  useEffect(() => {
    if (!isReplying) {
      return;
    }

    function closeOnEscape(event: KeyboardEvent): void {
      if (event.key === "Escape") {
        setIsReplying(false);
      }
    }

    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [isReplying]);

  return (
    <div className="reply-node" style={{ "--reply-depth": Math.min(depth, 4) } as CSSProperties}>
      <div className="reply-card">
        <div className="reply-meta">
          <span className="thread-author-avatar" aria-hidden="true">
            {authorInitials(reply.author)}
          </span>
          <span>{reply.author}</span>
          <span>{contributorRank(reply.author, reply.votes)}</span>
          <span>{preciseTime(reply.createdAt)}</span>
          <span>{relativeTime(reply.createdAt)} ago</span>
          <span>{reply.votes} votes</span>
        </div>
        <div className="reply-body">
          {reply.body.split(/\n{2,}/).map((paragraph) => (
            <p key={paragraph}>{paragraph}</p>
          ))}
        </div>
        <div className="reply-actions">
          <VoteButton
            count={reply.votes}
            label="Vote on reply"
            onVote={(delta) => vote("reply", delta, reply.id)}
          />
          <button
            className="reply-toggle"
            onClick={() => setIsReplying((value) => !value)}
            type="button"
          >
            {isReplying ? "Close reply" : "Reply"}
          </button>
        </div>
        {isReplying ? (
          <ReplyComposer onCreated={onThreadChange} parentId={reply.id} threadId={thread.id} />
        ) : null}
        {children.length > 0 ? (
          <div className="nested-replies">
            {children.map((child) => (
              <ReplyNode
                depth={depth + 1}
                key={child.id}
                onThreadChange={onThreadChange}
                reply={child}
                thread={thread}
                vote={vote}
              />
            ))}
          </div>
        ) : null}
      </div>
    </div>
  );
}
