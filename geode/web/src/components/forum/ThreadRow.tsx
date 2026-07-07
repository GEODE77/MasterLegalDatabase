"use client";

import Link from "next/link";
import type { ReactElement } from "react";

import { ForumTagChip } from "@/components/forum/ForumTagChip";
import type { ForumThreadSummary } from "@/lib/forum/types";
import {
  authorBio,
  authorInitials,
  contributorRank,
  impactLabel,
  issueTypeLabel,
  relativeTime,
  statusLabel,
  verificationLabel,
} from "./forumClient";

type ThreadRowProps = {
  onOpen?: () => void;
  thread: ForumThreadSummary;
};

export function ThreadRow({ onOpen, thread }: ThreadRowProps): ReactElement {
  const role = contributorRank(thread.author, thread.replyCount + thread.votes);

  return (
    <Link className="thread-row" href={`/forum/${thread.id}`} onClick={onOpen}>
      <span className="issue-card-topline">
        <span className="issue-type-pill">{issueTypeLabel(thread.issueType)}</span>
        <span className={`issue-status issue-status-${thread.status}`}>
          {statusLabel(thread.status)}
        </span>
        <span>{impactLabel(thread.impactLevel)} impact</span>
      </span>
      <span className="thread-row-primary">
        <span className="thread-title">{thread.title}</span>
        <span className="thread-excerpt">{thread.excerpt}</span>
      </span>
      <span className="issue-action-line">
        <small>Current action</small>
        <strong>{thread.actionLabel}</strong>
      </span>
      <span className="issue-card-grid">
        <span>
          <small>Legal source</small>
          <strong>{thread.legalSource}</strong>
        </span>
        <span>
          <small>Affected audience</small>
          <strong>{thread.affectedAudience}</strong>
        </span>
      </span>
      <span className="thread-row-author">
        <span className="thread-author-avatar" aria-hidden="true">
          {authorInitials(thread.author)}
        </span>
        <span className="thread-author-copy">
          <span className="thread-author-name">{thread.author}</span>
          <span className="thread-author-role">{role}</span>
        </span>
        <span className="thread-author-card" role="tooltip">
          <strong>{thread.author}</strong>
          <span>{role}</span>
          <small>{authorBio(thread.author, role)}</small>
          <small>{thread.replyCount} recent contributions</small>
        </span>
      </span>
      <span className="thread-row-meta">
        <span>{Math.max(thread.votes, 0)} support signals</span>
        <span>{thread.replyCount} replies</span>
        {thread.deadline ? <span>Action date {thread.deadline}</span> : null}
        <span>{verificationLabel(thread.verificationStatus)}</span>
        <span>{relativeTime(thread.updatedAt)} ago</span>
        <span className="thread-tags">
          {thread.tags.map((tag) => (
            <ForumTagChip key={tag} tag={tag} />
          ))}
        </span>
      </span>
    </Link>
  );
}
