import type { ReactElement } from "react";

import { ThreadDetail } from "@/components/forum/ThreadDetail";

type ThreadPageProps = {
  params: Promise<{ id: string }>;
};

export default async function ThreadPage({ params }: ThreadPageProps): Promise<ReactElement> {
  const { id } = await params;
  return <ThreadDetail id={id} />;
}
