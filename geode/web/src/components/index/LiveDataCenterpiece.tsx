"use client";

import { useEffect, useMemo, useRef, useState, type ReactElement } from "react";

import type { GeodeIndexStats } from "@/lib/index/geodeIndexStats";

type LiveDataCenterpieceProps = {
  initialStats: GeodeIndexStats;
  size?: "hero" | "compact";
};

const POLL_MS = 30_000;

export function LiveDataCenterpiece({
  initialStats,
  size = "hero",
}: LiveDataCenterpieceProps): ReactElement {
  const [stats, setStats] = useState(initialStats);
  const previousCount = usePrevious(stats.count);
  const changedDigitIndexes = useMemo(
    () => changedDigits(previousCount, stats.count),
    [previousCount, stats.count],
  );
  const sparkline = useMemo(() => buildSparkline(stats.points), [stats.points]);

  useEffect(() => {
    let isMounted = true;

    async function refresh(): Promise<void> {
      try {
        const response = await fetch("/api/index-stats", { cache: "no-store" });

        if (!response.ok) {
          return;
        }

        const payload = (await response.json()) as GeodeIndexStats;

        if (isMounted) {
          setStats(payload);
        }
      } catch {
        // The server-rendered value remains authoritative if live refresh is unavailable.
      }
    }

    const interval = window.setInterval(() => {
      void refresh();
    }, POLL_MS);

    return () => {
      isMounted = false;
      window.clearInterval(interval);
    };
  }, []);

  return (
    <section className={`live-index live-index--${size}`} aria-label="Geode authority index">
      <div className="live-index__label">
        <span>Geode Authority Index</span>
        <span>{formatUpdated(stats.lastUpdated)}</span>
      </div>
      <div
        className="live-index__metric"
        aria-label={`${stats.count} legal authorities indexed`}
        data-tooltip={`${formatNumber(stats.count)} legal authorities indexed - ${formatUpdated(stats.lastUpdated)}`}
      >
        {formatNumber(stats.count).split("").map((character, index) => (
          <span
            className={changedDigitIndexes.has(index) ? "is-ticking" : ""}
            key={`${index}-${character}`}
          >
            {character}
          </span>
        ))}
      </div>
      <svg
        className="live-index__sparkline"
        viewBox="0 0 100 34"
        role="img"
        aria-label="Thirty day authority index trajectory"
        preserveAspectRatio="none"
      >
        <defs>
          <linearGradient id={`live-index-fill-${size}`} x1="0" x2="0" y1="0" y2="1">
            <stop offset="0%" stopColor="currentColor" stopOpacity="0.24" />
            <stop offset="100%" stopColor="currentColor" stopOpacity="0" />
          </linearGradient>
        </defs>
        <path className="live-index__sparkline-fill" d={sparkline.fillPath} fill={`url(#live-index-fill-${size})`} />
        <path className="live-index__sparkline-line" d={sparkline.linePath} pathLength={1} />
      </svg>
      <div className="live-index__variants" aria-label="Index variants">
        {stats.variants.map((variant) => (
          <span key={variant.label}>
            <strong>{variant.label}</strong>
            {formatCompact(variant.value)}
          </span>
        ))}
      </div>
    </section>
  );
}

function usePrevious(value: number): number | null {
  const previous = useRef<number | null>(null);

  useEffect(() => {
    previous.current = value;
  }, [value]);

  return previous.current;
}

function changedDigits(previous: number | null, current: number): Set<number> {
  if (previous === null || previous === current) {
    return new Set();
  }

  const before = formatNumber(previous).padStart(formatNumber(current).length, " ");
  const after = formatNumber(current);
  const changed = new Set<number>();

  for (let index = 0; index < after.length; index += 1) {
    if (before[index] !== after[index]) {
      changed.add(index);
    }
  }

  return changed;
}

function buildSparkline(points: GeodeIndexStats["points"]): { fillPath: string; linePath: string } {
  if (points.length === 0) {
    return { fillPath: "", linePath: "" };
  }

  const values = points.map((point) => point.value);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = Math.max(1, max - min);
  const coordinates = points.map((point, index) => {
    const x = points.length === 1 ? 0 : (index / (points.length - 1)) * 100;
    const y = 28 - ((point.value - min) / range) * 22;
    return { x, y };
  });
  const linePath = coordinates
    .map((point, index) => `${index === 0 ? "M" : "L"} ${point.x.toFixed(2)} ${point.y.toFixed(2)}`)
    .join(" ");
  const first = coordinates[0];
  const last = coordinates.at(-1) ?? first;
  const fillPath = `${linePath} L ${last.x.toFixed(2)} 34 L ${first.x.toFixed(2)} 34 Z`;

  return { fillPath, linePath };
}

function formatNumber(value: number): string {
  return value.toLocaleString("en-US");
}

function formatCompact(value: number): string {
  return new Intl.NumberFormat("en-US", {
    maximumFractionDigits: 1,
    notation: value >= 10_000 ? "compact" : "standard",
  }).format(value);
}

function formatUpdated(value: string | null): string {
  if (!value) {
    return "Updated timestamp unavailable";
  }

  const formatted = new Intl.DateTimeFormat("en-US", {
    hour: "2-digit",
    hour12: false,
    minute: "2-digit",
    second: "2-digit",
    timeZone: "America/Denver",
  }).format(new Date(value));

  return `Updated ${formatted} MT`;
}
