"use client";

import type { ReactElement } from "react";

export function BeamsBackground(): ReactElement {
  return (
    <div aria-hidden="true" className="beams-background">
      <div className="beam beam-a" />
      <div className="beam beam-b" />
      <div className="beam beam-c" />
      <div className="beam-grid" />
      <div className="beam-orbit beam-orbit-a" />
      <div className="beam-orbit beam-orbit-b" />
      <div className="beam-vignette" />
    </div>
  );
}
