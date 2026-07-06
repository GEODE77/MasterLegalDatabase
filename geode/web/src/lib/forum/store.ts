import fs from "node:fs";
import path from "node:path";

import type { ForumReply, ForumSort, ForumTag, ForumThread, ForumThreadSummary } from "./types";
import { FORUM_TAGS } from "./types";

const FORUM_DIR = path.join(process.cwd(), "data", "forum");

type NewThreadInput = {
  author: string;
  body: string;
  tags: ForumTag[];
  title: string;
};

type NewReplyInput = {
  author: string;
  body: string;
  parentId?: string | null;
};

export type ForumStats = {
  activeNow: number;
  memberCount: number;
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

  return { activeNow, memberCount: members.size };
}

export function getThread(id: string): ForumThread | null {
  const threadPath = threadFilePath(id);

  if (!fs.existsSync(threadPath)) {
    return null;
  }

  return JSON.parse(fs.readFileSync(threadPath, "utf8")) as ForumThread;
}

export function createThread(input: NewThreadInput): ForumThread {
  ensureForumDir();

  const now = new Date().toISOString();
  const thread: ForumThread = {
    id: makeId(input.title),
    author: input.author,
    body: input.body.trim(),
    createdAt: now,
    excerpt: makeExcerpt(input.body),
    replies: [],
    tags: normalizeTags(input.tags),
    title: input.title.trim(),
    updatedAt: now,
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
      return JSON.parse(content) as ForumThread;
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

  return sorted.sort((a, b) => hotScore(b, now) - hotScore(a, now));
}

function hotScore(thread: ForumThread, now: number): number {
  const hoursOld = Math.max(1, (now - Date.parse(thread.createdAt)) / 3_600_000);
  return thread.votes * 3 + thread.replies.length * 2 - hoursOld / 12;
}

function toSummary(thread: ForumThread): ForumThreadSummary {
  return {
    id: thread.id,
    author: thread.author,
    createdAt: thread.createdAt,
    excerpt: thread.excerpt,
    replyCount: thread.replies.length,
    tags: thread.tags,
    title: thread.title,
    updatedAt: thread.updatedAt,
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
