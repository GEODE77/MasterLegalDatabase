import { addReply, getThread, voteReply, voteThread } from "@/lib/forum/store";

export const dynamic = "force-dynamic";

type Params = {
  params: Promise<{ id: string }>;
};

type ReplyPayload = {
  author?: string;
  body?: string;
  parentId?: string | null;
};

type VotePayload = {
  delta?: number;
  replyId?: string;
  target?: "thread" | "reply";
};

export async function GET(_request: Request, { params }: Params): Promise<Response> {
  const { id } = await params;
  const thread = getThread(id);

  if (!thread) {
    return Response.json({ error: "Thread not found." }, { status: 404 });
  }

  return Response.json({ thread }, { headers: { "Cache-Control": "no-store" } });
}

export async function POST(request: Request, { params }: Params): Promise<Response> {
  const { id } = await params;
  const payload = (await request.json()) as ReplyPayload;
  const body = payload.body?.trim() ?? "";
  const author = payload.author?.trim() || "Geode Member";

  if (body.length < 8) {
    return Response.json({ error: "Reply is too short." }, { status: 400 });
  }

  const thread = addReply(id, { author, body, parentId: payload.parentId ?? null });

  if (!thread) {
    return Response.json({ error: "Thread not found." }, { status: 404 });
  }

  return Response.json({ thread }, { status: 201 });
}

export async function PATCH(request: Request, { params }: Params): Promise<Response> {
  const { id } = await params;
  const payload = (await request.json()) as VotePayload;
  const delta = payload.delta ?? 1;
  const thread =
    payload.target === "reply" && payload.replyId
      ? voteReply(id, payload.replyId, delta)
      : voteThread(id, delta);

  if (!thread) {
    return Response.json({ error: "Vote target not found." }, { status: 404 });
  }

  return Response.json({ thread });
}
