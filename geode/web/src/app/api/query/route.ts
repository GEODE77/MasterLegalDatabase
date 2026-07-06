import { searchGeodeIndex } from "@/lib/search/searchGeodeIndex";

export const dynamic = "force-dynamic";

type QueryPayload = {
  query?: string;
};

const encoder = new TextEncoder();

export async function POST(request: Request): Promise<Response> {
  let payload: QueryPayload;

  try {
    payload = (await request.json()) as QueryPayload;
  } catch {
    return Response.json({ error: "Invalid query payload." }, { status: 400 });
  }

  const query = payload.query?.trim() ?? "";

  if (query.length < 3) {
    return Response.json({ error: "Please enter a longer question." }, { status: 400 });
  }

  const stream = new ReadableStream({
    async start(controller) {
      try {
        const results = searchGeodeIndex(query, 8);

        for (const result of results) {
          controller.enqueue(encoder.encode(`${JSON.stringify(result)}\n`));
          await wait(140);
        }
      } catch {
        controller.enqueue(
          encoder.encode(`${JSON.stringify({ error: "Search could not be completed." })}\n`),
        );
      } finally {
        controller.close();
      }
    },
  });

  return new Response(stream, {
    headers: {
      "Cache-Control": "no-store",
      "Content-Type": "application/x-ndjson; charset=utf-8",
    },
  });
}

function wait(ms: number): Promise<void> {
  return new Promise((resolve) => {
    setTimeout(resolve, ms);
  });
}
