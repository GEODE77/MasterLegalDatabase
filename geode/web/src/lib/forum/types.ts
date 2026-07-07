export type ForumSort =
  | "active"
  | "petitions"
  | "bills"
  | "rulemaking"
  | "risk"
  | "needs-review"
  | "hot"
  | "new"
  | "top"
  | "unanswered";

export type ForumIssueType =
  | "discussion"
  | "petition"
  | "bill-support"
  | "bill-opposition"
  | "rulemaking-comment"
  | "compliance-risk"
  | "legal-interpretation"
  | "industry-coalition"
  | "agency-guidance"
  | "executive-brief"
  | "source-review";

export type ForumIssueStatus =
  | "active"
  | "deadline-open"
  | "needs-review"
  | "monitoring"
  | "closed";

export type ForumImpactLevel = "executive" | "policy" | "operational" | "watch";

export type ForumVerificationStatus =
  | "source-linked"
  | "manager-reviewed"
  | "awaiting-source"
  | "community-submitted";

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
  actionLabel: string;
  affectedAudience: string;
  id: string;
  impactLevel: ForumImpactLevel;
  issueType: ForumIssueType;
  legalSource: string;
  deadline: string | null;
  status: ForumIssueStatus;
  title: string;
  excerpt: string;
  body: string;
  author: string;
  createdAt: string;
  updatedAt: string;
  votes: number;
  tags: ForumTag[];
  verificationStatus: ForumVerificationStatus;
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
