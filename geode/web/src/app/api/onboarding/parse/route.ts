import { inferOnboardingAnalysis, textFromUploadedFile } from "@/lib/onboarding/inferDocument";
import type { OnboardingParseResponse } from "@/lib/onboarding/types";

export const dynamic = "force-dynamic";

type JsonPayload = {
  text?: string;
};

export async function POST(request: Request): Promise<Response> {
  try {
    const text = await readRequestText(request);
    const analysis = inferOnboardingAnalysis(text);
    const response: OnboardingParseResponse = { analysis };

    return Response.json(response, {
      headers: {
        "Cache-Control": "no-store",
      },
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : "The document could not be analyzed.";

    return Response.json(
      { error: message },
      {
        headers: { "Cache-Control": "no-store" },
        status: 400,
      },
    );
  }
}

async function readRequestText(request: Request): Promise<string> {
  const contentType = request.headers.get("content-type") ?? "";

  if (contentType.includes("multipart/form-data")) {
    const formData = await request.formData();
    const file = formData.get("file");

    if (file instanceof File) {
      return textFromUploadedFile(file);
    }

    const pastedText = formData.get("text");
    return typeof pastedText === "string" ? pastedText : "";
  }

  const payload = (await request.json()) as JsonPayload;
  return payload.text ?? "";
}
