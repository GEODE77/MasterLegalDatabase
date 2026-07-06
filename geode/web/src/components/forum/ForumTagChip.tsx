import type { ReactElement } from "react";

import type { ForumTag } from "@/lib/forum/types";
import { tagLabel } from "./forumClient";

type ForumTagChipProps = {
  tag: ForumTag;
};

export function ForumTagChip({ tag }: ForumTagChipProps): ReactElement {
  return <span className="forum-tag">/{tagLabel(tag)}</span>;
}
