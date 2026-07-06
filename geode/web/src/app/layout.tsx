import type { Metadata } from "next";
import { headers } from "next/headers";
import type { ReactElement, ReactNode } from "react";

import { PersonalizationProvider } from "@/providers/PersonalizationProvider";
import { ProgressivePromptProvider } from "@/providers/ProgressivePromptProvider";
import { UndoToastProvider } from "@/providers/UndoToastProvider";
import { readOrCreateSnapshot, resolveUserId } from "@/lib/personalization/server";
import { ProductChrome } from "@/components/navigation/ProductChrome";
import { RouteMotionProvider } from "@/components/navigation/RouteMotionProvider";
import { AtmosphericLayer } from "@/components/atmosphere/AtmosphericLayer";

import "../styles/globals.css";

export const metadata: Metadata = {
  title: "Geode",
  description: "Project Geode frontend reset scaffold"
};

export default async function RootLayout({
  children
}: Readonly<{
  children: ReactNode;
}>): Promise<ReactElement> {
  const requestHeaders = await headers();
  const userId = resolveUserId(requestHeaders.get("x-geode-user-id"));
  const initialSnapshot = readOrCreateSnapshot(userId);

  return (
    <html lang="en">
      <body>
        <AtmosphericLayer />
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
