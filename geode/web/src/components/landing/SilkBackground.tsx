"use client";

import type { ReactElement } from "react";

export function SilkBackground(): ReactElement {
  return (
    <div aria-hidden="true" className="silk-background">
      <div className="silk-grid" />
      <div className="silk-layer silk-layer-a" />
      <div className="silk-layer silk-layer-b" />
      <div className="silk-layer silk-layer-c" />
      <div className="silk-scanline" />
      <div className="silk-vignette" />
    </div>
  );
}
