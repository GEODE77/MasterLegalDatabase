import type { ReactElement } from "react";

export function ForumBackground(): ReactElement {
  return (
    <div aria-hidden="true" className="forum-background">
      <div className="forum-thread-lines" />
      <div className="forum-glass-wash" />
      <div className="forum-background-vignette" />
    </div>
  );
}
