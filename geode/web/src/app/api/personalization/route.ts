import { NextResponse } from "next/server";

import {
  appendBehaviorEvents,
  createPublicSnapshot,
  deleteSnapshot,
  readOrCreateSnapshot,
  resolveUserId,
  updatePreferences,
} from "@/lib/personalization/server";
import type { PersonalizationEventInput, PersonalizationPreferenceUpdate } from "@/lib/personalization/types";

export const dynamic = "force-dynamic";

const USER_ID_HEADER = "x-geode-user-id";

export async function GET(request: Request): Promise<Response> {
  const userId = resolveUserId(request.headers.get(USER_ID_HEADER));
  const snapshot = createPublicSnapshot(readOrCreateSnapshot(userId));
  return responseWithIdentity(NextResponse.json({ snapshot }, { headers: { "Cache-Control": "no-store" } }), userId);
}

export async function PUT(request: Request): Promise<Response> {
  const userId = resolveUserId(request.headers.get(USER_ID_HEADER));
  const payload = (await request.json()) as PersonalizationPreferenceUpdate;
  const snapshot = createPublicSnapshot(updatePreferences(userId, payload));
  return responseWithIdentity(NextResponse.json({ snapshot }, { headers: { "Cache-Control": "no-store" } }), userId);
}

export async function POST(request: Request): Promise<Response> {
  const userId = resolveUserId(request.headers.get(USER_ID_HEADER));
  const payload = (await request.json()) as { events?: PersonalizationEventInput[] };
  const events = Array.isArray(payload.events) ? payload.events : [];

  if (events.length === 0) {
    return NextResponse.json({ error: "Event batch is empty." }, { status: 400 });
  }

  const snapshot = createPublicSnapshot(appendBehaviorEvents(userId, events));
  return responseWithIdentity(NextResponse.json({ snapshot }, { headers: { "Cache-Control": "no-store" } }), userId);
}

export async function DELETE(request: Request): Promise<Response> {
  const userId = resolveUserId(request.headers.get(USER_ID_HEADER));
  const snapshot = createPublicSnapshot(deleteSnapshot(userId).snapshot);
  const response = NextResponse.json({ deleted: true, snapshot }, { headers: { "Cache-Control": "no-store" } });
  response.cookies.set("geode.personalization.user", "", {
    expires: new Date(0),
    path: "/",
  });
  return response;
}

function responseWithIdentity(response: NextResponse, userId: string): NextResponse {
  response.cookies.set("geode.personalization.user", userId, {
    httpOnly: false,
    sameSite: "lax",
    path: "/",
  });
  return response;
}
