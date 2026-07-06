"use client";

import Link from "next/link";
import type { PointerEvent, ReactElement } from "react";

type DecisionTileProps = {
  readonly description: string;
  readonly detail?: string;
  readonly href: string;
  readonly metrics: readonly string[];
  readonly signal?: string;
  readonly title: string;
  readonly variant: "query" | "forum";
};

export function DecisionTile({
  description,
  detail,
  href,
  metrics,
  signal,
  title,
  variant,
}: DecisionTileProps): ReactElement {
  function handlePointerMove(event: PointerEvent<HTMLAnchorElement>): void {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      return;
    }

    const bounds = event.currentTarget.getBoundingClientRect();
    const x = (event.clientX - bounds.left) / bounds.width - 0.5;
    const y = (event.clientY - bounds.top) / bounds.height - 0.5;

    event.currentTarget.style.setProperty("--tilt-x", `${(-y * 7).toFixed(2)}deg`);
    event.currentTarget.style.setProperty("--tilt-y", `${(x * 8).toFixed(2)}deg`);
    event.currentTarget.style.setProperty("--glow-x", `${(event.clientX - bounds.left).toFixed(0)}px`);
    event.currentTarget.style.setProperty("--glow-y", `${(event.clientY - bounds.top).toFixed(0)}px`);
  }

  function handlePointerLeave(event: PointerEvent<HTMLAnchorElement>): void {
    event.currentTarget.style.setProperty("--tilt-x", "0deg");
    event.currentTarget.style.setProperty("--tilt-y", "0deg");
  }

  return (
    <Link
      aria-label={`${title}. ${description}`}
      className={`decision-tile decision-tile-${variant}`}
      href={href}
      onPointerLeave={handlePointerLeave}
      onPointerMove={handlePointerMove}
    >
      <span className="decision-plate" aria-hidden="true" />
      <span className="decision-sheen" aria-hidden="true" />
      <span className={`decision-glyph decision-glyph-${variant}`} aria-hidden="true">
        <span />
        <span />
        <span />
      </span>
      <span className="decision-copy">
        {signal ? <span className="decision-signal">{signal}</span> : null}
        <span className="decision-title">{title}</span>
        <span className="decision-description">{description}</span>
        {detail ? <span className="decision-detail">{detail}</span> : null}
      </span>
      <span className="decision-metrics" aria-label={`${title} context`}>
        {metrics.map((metric) => (
          <span key={metric}>{metric}</span>
        ))}
      </span>
      <span className="decision-enter" aria-hidden="true">
        Enter
      </span>
    </Link>
  );
}
