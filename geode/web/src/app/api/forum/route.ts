import { createThread, getForumStats, listThreads } from "@/lib/forum/store";
import type {
  ForumImpactLevel,
  ForumIssueStatus,
  ForumIssueType,
  ForumSort,
  ForumTag,
  ForumVerificationStatus,
} from "@/lib/forum/types";

export const dynamic = "force-dynamic";

type ThreadPayload = {
  actionLabel?: string;
  affectedAudience?: string;
  author?: string;
  body?: string;
  deadline?: string | null;
  impactLevel?: ForumImpactLevel;
  issueType?: ForumIssueType;
  legalSource?: string;
  status?: ForumIssueStatus;
  tags?: ForumTag[];
  title?: string;
  verificationStatus?: ForumVerificationStatus;
};

export function GET(request: Request): Response {
  const url = new URL(request.url);
  const sort = parseSort(url.searchParams.get("sort"));

  return Response.json(
    { stats: getForumStats(), threads: listThreads(sort) },
    { headers: { "Cache-Control": "no-store" } },
  );
}

export async function POST(request: Request): Promise<Response> {
  const payload = (await request.json()) as ThreadPayload;
  const title = payload.title?.trim() ?? "";
  const body = payload.body?.trim() ?? "";
  const author = payload.author?.trim() || "Geode Member";

  if (title.length < 8 || body.length < 20) {
    return Response.json({ error: "Thread title or body is too short." }, { status: 400 });
  }

  const thread = createThread({
    actionLabel: payload.actionLabel,
    affectedAudience: payload.affectedAudience,
    author,
    body,
    deadline: payload.deadline,
    impactLevel: payload.impactLevel,
    issueType: payload.issueType,
    legalSource: payload.legalSource,
    status: payload.status,
    tags: payload.tags ?? ["general"],
    title,
    verificationStatus: payload.verificationStatus,
  });
  return Response.json({ thread }, { status: 201 });
}

function parseSort(value: string | null): ForumSort {
  if (
    value === "active" ||
    value === "petitions" ||
    value === "bills" ||
    value === "rulemaking" ||
    value === "risk" ||
    value === "needs-review" ||
    value === "new" ||
    value === "top" ||
    value === "unanswered"
  ) {
    return value;
  }

  return "active";
}
