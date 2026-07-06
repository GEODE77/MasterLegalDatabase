import type { ReactElement } from "react";

export function DotPatternBackground(): ReactElement {
  return (
    <div aria-hidden="true" className="query-dot-background">
      <div className="query-dot-field" />
      <div className="query-aurora-wash" />
      <div className="query-vignette" />
    </div>
  );
}
