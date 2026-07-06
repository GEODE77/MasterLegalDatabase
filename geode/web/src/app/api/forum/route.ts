import { createThread, getForumStats, listThreads } from "@/lib/forum/store";
import type { ForumSort, ForumTag } from "@/lib/forum/types";

export const dynamic = "force-dynamic";

type ThreadPayload = {
  author?: string;
  body?: string;
  tags?: ForumTag[];
  title?: string;
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

  const thread = createThread({ author, body, tags: payload.tags ?? ["general"], title });
  return Response.json({ thread }, { status: 201 });
}

function parseSort(value: string | null): ForumSort {
  if (value === "new" || value === "top" || value === "unanswered") {
    return value;
  }

  return "hot";
}
