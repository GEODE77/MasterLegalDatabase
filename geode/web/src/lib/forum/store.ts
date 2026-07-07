import fs from "node:fs";
import path from "node:path";

import type {
  ForumImpactLevel,
  ForumIssueStatus,
  ForumIssueType,
  ForumReply,
  ForumSort,
  ForumTag,
  ForumThread,
  ForumThreadSummary,
  ForumVerificationStatus,
} from "./types";
import { FORUM_TAGS } from "./types";

const FORUM_DIR = path.join(process.cwd(), "data", "forum");
const DEFAULT_ISSUE_TYPE: ForumIssueType = "discussion";
const DEFAULT_STATUS: ForumIssueStatus = "active";
const DEFAULT_IMPACT_LEVEL: ForumImpactLevel = "operational";
const DEFAULT_VERIFICATION_STATUS: ForumVerificationStatus = "community-submitted";

type NewThreadInput = {
  actionLabel?: string;
  affectedAudience?: string;
  author: string;
  body: string;
  deadline?: string | null;
  impactLevel?: ForumImpactLevel;
  issueType?: ForumIssueType;
  legalSource?: string;
  status?: ForumIssueStatus;
  tags: ForumTag[];
  title: string;
  verificationStatus?: ForumVerificationStatus;
};

type NewReplyInput = {
  author: string;
  body: string;
  parentId?: string | null;
};

export type ForumStats = {
  activeNow: number;
  activeActions: number;
  billActions: number;
  memberCount: number;
  needsReview: number;
  openIssues: number;
  petitions: number;
  riskItems: number;
  rulemakingActions: number;
  sourceLinked: number;
};

export function listThreads(sort: ForumSort): ForumThreadSummary[] {
  return sortThreads(readThreads(), sort).map(toSummary);
}

export function getForumStats(): ForumStats {
  const members = new Set<string>();

  for (const thread of readThreads()) {
    members.add(thread.author);

    for (const reply of thread.replies) {
      members.add(reply.author);
    }
  }

  const nowBucket = Math.floor(Date.now() / 30_000);
  const activeNow = Math.max(1, members.size + 32 + (nowBucket % 9));

  const threads = readThreads();
  const activeActions = threads.filter((thread) => thread.actionLabel.trim().length > 0).length;
  const billActions = threads.filter(
    (thread) => thread.issueType === "bill-support" || thread.issueType === "bill-opposition",
  ).length;
  const needsReview = threads.filter(
    (thread) => thread.status === "needs-review" || thread.verificationStatus === "awaiting-source",
  ).length;
  const petitions = threads.filter((thread) => thread.issueType === "petition").length;
  const riskItems = threads.filter(
    (thread) => thread.issueType === "compliance-risk" || thread.issueType === "executive-brief",
  ).length;
  const rulemakingActions = threads.filter((thread) => thread.issueType === "rulemaking-comment").length;
  const sourceLinked = threads.filter((thread) => thread.verificationStatus === "source-linked").length;

  return {
    activeActions,
    activeNow,
    billActions,
    memberCount: members.size,
    needsReview,
    openIssues: threads.filter((thread) => thread.status !== "closed").length,
    petitions,
    riskItems,
    rulemakingActions,
    sourceLinked,
  };
}

export function getThread(id: string): ForumThread | null {
  const threadPath = threadFilePath(id);

  if (!fs.existsSync(threadPath)) {
    return null;
  }

  return normalizeThread(JSON.parse(fs.readFileSync(threadPath, "utf8")) as Partial<ForumThread>);
}

export function createThread(input: NewThreadInput): ForumThread {
  ensureForumDir();

  const now = new Date().toISOString();
  const thread: ForumThread = {
    actionLabel: compactOrDefault(input.actionLabel, "Discuss next action"),
    affectedAudience: compactOrDefault(input.affectedAudience, "Colorado legal and policy teams"),
    id: makeId(input.title),
    author: input.author,
    body: input.body.trim(),
    createdAt: now,
    deadline: compactOrNull(input.deadline),
    excerpt: makeExcerpt(input.body),
    impactLevel: input.impactLevel ?? DEFAULT_IMPACT_LEVEL,
    issueType: input.issueType ?? DEFAULT_ISSUE_TYPE,
    legalSource: compactOrDefault(input.legalSource, "Source needed"),
    replies: [],
    status: input.status ?? DEFAULT_STATUS,
    tags: normalizeTags(input.tags),
    title: input.title.trim(),
    updatedAt: now,
    verificationStatus: input.verificationStatus ?? DEFAULT_VERIFICATION_STATUS,
    votes: 0,
  };

  writeThread(thread);
  return thread;
}

export function addReply(threadId: string, input: NewReplyInput): ForumThread | null {
  const thread = getThread(threadId);

  if (!thread) {
    return null;
  }

  const now = new Date().toISOString();
  const reply: ForumReply = {
    id: makeId(`reply-${threadId}-${now}`),
    author: input.author,
    body: input.body.trim(),
    createdAt: now,
    parentId: input.parentId ?? null,
    votes: 0,
  };

  thread.replies.push(reply);
  thread.updatedAt = now;
  writeThread(thread);
  return thread;
}

export function voteThread(threadId: string, delta: number): ForumThread | null {
  const thread = getThread(threadId);

  if (!thread) {
    return null;
  }

  thread.votes += Math.sign(delta);
  thread.updatedAt = new Date().toISOString();
  writeThread(thread);
  return thread;
}

export function voteReply(threadId: string, replyId: string, delta: number): ForumThread | null {
  const thread = getThread(threadId);
  const reply = thread?.replies.find((item) => item.id === replyId);

  if (!thread || !reply) {
    return null;
  }

  reply.votes += Math.sign(delta);
  thread.updatedAt = new Date().toISOString();
  writeThread(thread);
  return thread;
}

function readThreads(): ForumThread[] {
  ensureForumDir();

  return fs
    .readdirSync(FORUM_DIR)
    .filter((fileName) => fileName.endsWith(".json"))
    .map((fileName) => {
      const content = fs.readFileSync(path.join(FORUM_DIR, fileName), "utf8");
      return normalizeThread(JSON.parse(content) as Partial<ForumThread>);
    });
}

function sortThreads(threads: ForumThread[], sort: ForumSort): ForumThread[] {
  const now = Date.now();
  const sorted = [...threads];

  if (sort === "new") {
    return sorted.sort((a, b) => Date.parse(b.createdAt) - Date.parse(a.createdAt));
  }

  if (sort === "top") {
    return sorted.sort((a, b) => b.votes - a.votes);
  }

  if (sort === "unanswered") {
    return sorted
      .filter((thread) => thread.replies.length === 0)
      .sort((a, b) => Date.parse(b.createdAt) - Date.parse(a.createdAt));
  }

  if (sort === "petitions") {
    return sorted
      .filter((thread) => thread.issueType === "petition")
      .sort((a, b) => hotScore(b, now) - hotScore(a, now));
  }

  if (sort === "bills") {
    return sorted
      .filter((thread) => thread.issueType === "bill-support" || thread.issueType === "bill-opposition")
      .sort((a, b) => hotScore(b, now) - hotScore(a, now));
  }

  if (sort === "rulemaking") {
    return sorted
      .filter((thread) => thread.issueType === "rulemaking-comment")
      .sort((a, b) => hotScore(b, now) - hotScore(a, now));
  }

  if (sort === "risk") {
    return sorted
      .filter((thread) => thread.issueType === "compliance-risk" || thread.issueType === "executive-brief")
      .sort((a, b) => hotScore(b, now) - hotScore(a, now));
  }

  if (sort === "needs-review") {
    return sorted
      .filter((thread) => thread.status === "needs-review" || thread.verificationStatus === "awaiting-source")
      .sort((a, b) => Date.parse(b.updatedAt) - Date.parse(a.updatedAt));
  }

  return sorted.sort((a, b) => hotScore(b, now) - hotScore(a, now));
}

function hotScore(thread: ForumThread, now: number): number {
  const hoursOld = Math.max(1, (now - Date.parse(thread.createdAt)) / 3_600_000);
  return thread.votes * 3 + thread.replies.length * 2 - hoursOld / 12;
}

function toSummary(thread: ForumThread): ForumThreadSummary {
  return {
    actionLabel: thread.actionLabel,
    affectedAudience: thread.affectedAudience,
    id: thread.id,
    author: thread.author,
    createdAt: thread.createdAt,
    deadline: thread.deadline,
    excerpt: thread.excerpt,
    impactLevel: thread.impactLevel,
    issueType: thread.issueType,
    legalSource: thread.legalSource,
    replyCount: thread.replies.length,
    status: thread.status,
    tags: thread.tags,
    title: thread.title,
    updatedAt: thread.updatedAt,
    verificationStatus: thread.verificationStatus,
    votes: thread.votes,
  };
}

function writeThread(thread: ForumThread): void {
  ensureForumDir();
  fs.writeFileSync(threadFilePath(thread.id), `${JSON.stringify(thread, null, 2)}\n`, "utf8");
}

function threadFilePath(id: string): string {
  return path.join(FORUM_DIR, `${id}.json`);
}

function ensureForumDir(): void {
  fs.mkdirSync(FORUM_DIR, { recursive: true });
}

function makeId(value: string): string {
  const slug = value
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/(^-|-$)/g, "")
    .slice(0, 48);
  return `${slug || "thread"}-${Date.now().toString(36)}`;
}

function makeExcerpt(value: string): string {
  const compact = value.trim().replace(/\s+/g, " ");
  return compact.length > 190 ? `${compact.slice(0, 187)}...` : compact;
}

function normalizeTags(tags: ForumTag[]): ForumTag[] {
  const validTags = tags.filter((tag) => FORUM_TAGS.includes(tag));
  return validTags.length > 0 ? Array.from(new Set(validTags)).slice(0, 4) : ["general"];
}

function normalizeThread(thread: Partial<ForumThread>): ForumThread {
  return {
    actionLabel: compactOrDefault(thread.actionLabel, "Discuss next action"),
    affectedAudience: compactOrDefault(thread.affectedAudience, "Colorado legal and policy teams"),
    author: thread.author ?? "Geode Member",
    body: thread.body ?? "",
    createdAt: thread.createdAt ?? new Date(0).toISOString(),
    deadline: compactOrNull(thread.deadline),
    excerpt: thread.excerpt ?? makeExcerpt(thread.body ?? ""),
    id: thread.id ?? makeId(thread.title ?? "thread"),
    impactLevel: thread.impactLevel ?? DEFAULT_IMPACT_LEVEL,
    issueType: thread.issueType ?? DEFAULT_ISSUE_TYPE,
    legalSource: compactOrDefault(thread.legalSource, "Source needed"),
    replies: thread.replies ?? [],
    status: thread.status ?? DEFAULT_STATUS,
    tags: normalizeTags(thread.tags ?? ["general"]),
    title: thread.title ?? "Untitled issue",
    updatedAt: thread.updatedAt ?? thread.createdAt ?? new Date(0).toISOString(),
    verificationStatus: thread.verificationStatus ?? DEFAULT_VERIFICATION_STATUS,
    votes: thread.votes ?? 0,
  };
}

function compactOrDefault(value: string | null | undefined, fallback: string): string {
  return value?.trim() || fallback;
}

function compactOrNull(value: string | null | undefined): string | null {
  const compact = value?.trim();
  return compact ? compact : null;
}
