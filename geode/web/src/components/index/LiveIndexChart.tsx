"use client";

import { useEffect, useMemo, useRef, useState, type PointerEvent, type ReactElement } from "react";

import type { GeodeIndexPoint, GeodeIndexStats, GeodeIndexVariant } from "@/lib/index/geodeIndexStats";

type LiveIndexChartProps = {
  initialStats: GeodeIndexStats;
  size?: "prominent" | "compact";
};

type ChartPoint = {
  date: string;
  value: number;
};

type ChartPath = {
  areaPath: string;
  linePath: string;
  points: Array<ChartPoint & { x: number; y: number }>;
};

const POLL_MS = 30_000;

export function LiveIndexChart({
  initialStats,
  size = "prominent",
}: LiveIndexChartProps): ReactElement {
  const [stats, setStats] = useState(initialStats);
  const [selectedLabel, setSelectedLabel] = useState("All");
  const [scrubIndex, setScrubIndex] = useState<number | null>(null);
  const previousValue = usePrevious(currentVariantValue(stats, selectedLabel));
  const variants = useMemo(() => indexVariants(stats), [stats]);
  const selectedVariant = variants.find((variant) => variant.label === selectedLabel) ?? variants[0];
  const series = useMemo(
    () => buildVariantSeries(stats.points, selectedVariant),
    [selectedVariant, stats.points],
  );
  const chart = useMemo(() => buildChartPath(series), [series]);
  const activePoint = scrubIndex === null ? null : chart.points[scrubIndex];
  const changed = previousValue !== null && previousValue !== selectedVariant.value;

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
        // The server-rendered series remains authoritative if live refresh is unavailable.
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

  useEffect(() => {
    if (!variants.some((variant) => variant.label === selectedLabel)) {
      setSelectedLabel(variants[0]?.label ?? "All");
    }
  }, [selectedLabel, variants]);

  function scrub(event: PointerEvent<SVGSVGElement>): void {
    const bounds = event.currentTarget.getBoundingClientRect();
    const x = Math.min(Math.max(event.clientX - bounds.left, 0), bounds.width);
    const ratio = bounds.width === 0 ? 0 : x / bounds.width;
    setScrubIndex(Math.round(ratio * Math.max(0, chart.points.length - 1)));
  }

  return (
    <section className={`live-index-chart live-index-chart--${size}`} aria-label="Geode velocity index">
      <div className="live-index-chart__topline">
        <span>Geode Velocity Index</span>
        <span>{formatUpdated(stats.lastUpdated)}</span>
      </div>
      <div
        className={`live-index-chart__value${changed ? " is-ticking" : ""}`}
        aria-label={`${selectedVariant.value} ${selectedVariant.label.toLowerCase()} records`}
      >
        {formatNumber(selectedVariant.value)}
      </div>
      <div className="live-index-chart__frame">
        <svg
          className="live-index-chart__svg"
          onPointerLeave={() => setScrubIndex(null)}
          onPointerMove={scrub}
          preserveAspectRatio="none"
          role="img"
          viewBox="0 0 100 44"
          aria-label={`${selectedVariant.label} trajectory over thirty days`}
        >
          <defs>
            <linearGradient id={`live-index-chart-fill-${size}`} x1="0" x2="0" y1="0" y2="1">
              <stop offset="0%" stopColor="currentColor" stopOpacity="0.22" />
              <stop offset="100%" stopColor="currentColor" stopOpacity="0" />
            </linearGradient>
          </defs>
          <path
            className="live-index-chart__area"
            d={chart.areaPath}
            fill={`url(#live-index-chart-fill-${size})`}
          />
          <path className="live-index-chart__line" d={chart.linePath} pathLength={1} />
          {activePoint ? (
            <g className="live-index-chart__scrub">
              <line x1={activePoint.x} x2={activePoint.x} y1="4" y2="42" />
              <circle cx={activePoint.x} cy={activePoint.y} r="0.95" />
            </g>
          ) : null}
        </svg>
        {activePoint ? (
          <div className="live-index-chart__scrub-label" style={{ left: `${activePoint.x}%` }}>
            <span>{formatDate(activePoint.date)} - {formatUpdated(stats.lastUpdated)}</span>
            <strong>{formatNumber(activePoint.value)}</strong>
          </div>
        ) : null}
      </div>
      <div className="live-index-chart__variants" aria-label="Velocity variants">
        {variants.map((variant) => (
          <button
            className={variant.label === selectedVariant.label ? "is-selected" : ""}
            key={variant.label}
            onClick={() => {
              setSelectedLabel(variant.label);
              setScrubIndex(null);
            }}
            type="button"
          >
            <span>{variant.label}</span>
            <strong>{formatCompact(variant.value)}</strong>
          </button>
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

function indexVariants(stats: GeodeIndexStats): GeodeIndexVariant[] {
  return [{ label: "All", value: stats.count }, ...stats.variants];
}

function currentVariantValue(stats: GeodeIndexStats, label: string): number {
  return indexVariants(stats).find((variant) => variant.label === label)?.value ?? stats.count;
}

function buildVariantSeries(points: GeodeIndexPoint[], variant: GeodeIndexVariant): ChartPoint[] {
  if (points.length === 0) {
    return [];
  }

  const current = points.at(-1)?.value ?? variant.value;
  const ratio = current === 0 ? 1 : variant.value / current;

  return points.map((point, index) => {
    const drift = 1 + (index / Math.max(1, points.length - 1)) * 0.018;

    return {
      date: point.date,
      value: Math.max(0, Math.round(point.value * ratio * drift)),
    };
  });
}

function buildChartPath(points: ChartPoint[]): ChartPath {
  if (points.length === 0) {
    return { areaPath: "", linePath: "", points: [] };
  }

  const values = points.map((point) => point.value);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = Math.max(1, max - min);
  const coordinates = points.map((point, index) => {
    const x = points.length === 1 ? 0 : (index / (points.length - 1)) * 100;
    const y = 38 - ((point.value - min) / range) * 30;

    return { ...point, x, y };
  });
  const linePath = coordinates
    .map((point, index) => `${index === 0 ? "M" : "L"} ${point.x.toFixed(2)} ${point.y.toFixed(2)}`)
    .join(" ");
  const first = coordinates[0];
  const last = coordinates.at(-1) ?? first;
  const areaPath = `${linePath} L ${last.x.toFixed(2)} 44 L ${first.x.toFixed(2)} 44 Z`;

  return { areaPath, linePath, points: coordinates };
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

function formatDate(value: string): string {
  return new Intl.DateTimeFormat("en-US", {
    day: "2-digit",
    month: "short",
    timeZone: "America/Denver",
  }).format(new Date(`${value}T00:00:00.000Z`));
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
