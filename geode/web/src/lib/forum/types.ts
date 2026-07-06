export type ForumSort = "hot" | "new" | "top" | "unanswered";

export type ForumTag =
  | "advanced-ceramics"
  | "manufacturing"
  | "environment"
  | "workforce"
  | "supply-chain"
  | "general"
  | "interpretation"
  | "enforcement"
  | "case-study"
  | "ask-an-expert";

export type ForumReply = {
  id: string;
  author: string;
  body: string;
  createdAt: string;
  parentId: string | null;
  votes: number;
};

export type ForumThread = {
  id: string;
  title: string;
  excerpt: string;
  body: string;
  author: string;
  createdAt: string;
  updatedAt: string;
  votes: number;
  tags: ForumTag[];
  replies: ForumReply[];
};

export type ForumThreadSummary = Omit<ForumThread, "body" | "replies"> & {
  replyCount: number;
};

export const FORUM_TAGS: ForumTag[] = [
  "advanced-ceramics",
  "manufacturing",
  "environment",
  "workforce",
  "supply-chain",
  "general",
  "interpretation",
  "enforcement",
  "case-study",
  "ask-an-expert",
];
