import type { Metadata } from "next";
import { headers } from "next/headers";
import type { ReactElement, ReactNode } from "react";

import { PersonalizationProvider } from "@/providers/PersonalizationProvider";
import { ProgressivePromptProvider } from "@/providers/ProgressivePromptProvider";
import { UndoToastProvider } from "@/providers/UndoToastProvider";
import { createTransientSnapshot, readOrCreateSnapshot, resolveUserId } from "@/lib/personalization/server";
import { ProductChrome } from "@/components/navigation/ProductChrome";
import { RouteMotionProvider } from "@/components/navigation/RouteMotionProvider";

import "../styles/globals.css";

export const metadata: Metadata = {
  title: "Geode",
  description: "Public Colorado legal data with separate verified manager operations."
};

export const dynamic = "force-dynamic";

export default async function RootLayout({
  children
}: Readonly<{
  children: ReactNode;
}>): Promise<ReactElement> {
  const requestHeaders = await headers();
  const userIdHeader = requestHeaders.get("x-geode-user-id");
  const userId = userIdHeader ? resolveUserId(userIdHeader) : "build-preview";
  const initialSnapshot = userIdHeader ? readOrCreateSnapshot(userId) : createTransientSnapshot(userId);

  return (
    <html lang="en">
      <body>
        <PersonalizationProvider initialSnapshot={initialSnapshot}>
          <ProgressivePromptProvider>
            <UndoToastProvider>
              <RouteMotionProvider>
                <ProductChrome>{children}</ProductChrome>
              </RouteMotionProvider>
            </UndoToastProvider>
          </ProgressivePromptProvider>
        </PersonalizationProvider>
      </body>
    </html>
  );
}
