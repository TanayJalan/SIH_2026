import { useState } from "react";
import { MapPin, AlertTriangle, TrendingDown, Users } from "lucide-react";

import { InstitutionCompliance } from "@/lib/api";
import { cn } from "@/lib/utils";

export const TILE = 26;
export const GAP = 4;

export const INDIA_TILE_GRID: IndiaTile[] = [
  { id: "JK", name: "Jammu & Kashmir", x: 0, y: 0 },
  { id: "HP", name: "Himachal Pradesh", x: 1, y: 0 },
  { id: "PB", name: "Punjab", x: 2, y: 0 },
  { id: "HR", name: "Haryana", x: 3, y: 0 },
  { id: "DL", name: "Delhi", x: 3, y: 1 },
  { id: "UP", name: "Uttar Pradesh", x: 4, y: 0 },
  { id: "UK", name: "Uttarakhand", x: 3, y: -1 },
  { id: "RJ", name: "Rajasthan", x: 2, y: 1 },
  { id: "MP", name: "Madhya Pradesh", x: 3, y: 2 },
  { id: "BR", name: "Bihar", x: 5, y: 1 },
  { id: "WB", name: "West Bengal", x: 6, y: 1 },
  { id: "GJ", name: "Gujarat", x: 1, y: 2 },
  { id: "MH", name: "Maharashtra", x: 2, y: 3 },
  { id: "CG", name: "Chhattisgarh", x: 3, y: 3 },
  { id: "OD", name: "Odisha", x: 4, y: 3 },
  { id: "GA", name: "Goa", x: 1, y: 4 },
  { id: "KA", name: "Karnataka", x: 2, y: 5 },
  { id: "TG", name: "Telangana", x: 3, y: 4 },
  { id: "AP", name: "Andhra Pradesh", x: 4, y: 4 },
  { id: "TN", name: "Tamil Nadu", x: 5, y: 4 },
  { id: "KL", name: "Kerala", x: 2, y: 6 },
];

export interface IndiaTile {
  id: string;
  name: string;
  x: number;
  y: number;
}

export type TileMetric = "compliance" | "sla" | "pending" | "penal";

export const METRIC_LABELS: Record<TileMetric, string> = {
  compliance: "Compliance RAG",
  sla: "SLA breaches",
  pending: "Pending applications",
  penal: "Penal actions",
};

const METRIC_ICONS: Record<TileMetric, React.ElementType> = {
  compliance: AlertTriangle,
  sla: TrendingDown,
  pending: MapPin,
  penal: Users,
};

interface StateAggregate {
  name: string;
  count: number;
  avgScore: number;
  red: number;
  amber: number;
  green: number;
}

/** Institution.state carries the full name; the cartogram is keyed by code. */
const TILE_ID_BY_STATE_NAME = new Map(
  INDIA_TILE_GRID.map((tile) => [tile.name, tile.id]),
);

function tileIdForState(state: string): string {
  return TILE_ID_BY_STATE_NAME.get(state) ?? state;
}

function aggregateByState(data: InstitutionCompliance[]): Map<string, StateAggregate> {
  const byState = new Map<string, StateAggregate>();
  for (const item of data) {
    const stateId = tileIdForState(item.state);
    const current = byState.get(stateId) ?? {
      name: item.state,
      count: 0,
      avgScore: 0,
      red: 0,
      amber: 0,
      green: 0,
    };
    current.count += 1;
    current.avgScore += item.score;
    if (item.status === "RED") current.red += 1;
    else if (item.status === "AMBER") current.amber += 1;
    else if (item.status === "GREEN") current.green += 1;
    byState.set(stateId, current);
  }
  for (const agg of byState.values()) {
    agg.avgScore = agg.count ? agg.avgScore / agg.count : 0;
  }
  return byState;
}

function complianceBandFor(score: number): "ok" | "watch" | "breach" {
  if (score >= 80) return "ok";
  if (score >= 60) return "watch";
  return "breach";
}

function breachRate(agg: StateAggregate): number {
  if (agg.count === 0) return 0;
  return ((agg.red + agg.amber) / agg.count) * 100;
}

export interface IndiaTileMapProps {
  data: InstitutionCompliance[];
  metric: TileMetric;
  onMetricChange: (metric: TileMetric) => void;
  selectedState: string | null;
  onSelectState: (state: string | null) => void;
  className?: string;
}

export function IndiaTileMap({
  data,
  metric,
  onMetricChange,
  selectedState,
  onSelectState,
  className,
}: IndiaTileMapProps) {
  const [hover, setHover] = useState<string | null>(null);
  const byState = aggregateByState(data);

  const totalInstitutions = data.length;

  return (
    <section
      className={cn("min-w-0 space-y-4", className)}
      aria-label="India tile-grid cartogram"
    >
      <div className="flex flex-wrap items-center gap-3 mb-2">
        <span className="text-11 font-semibold uppercase tracking-[0.12em] text-ink-500">
          Colour tiles by
        </span>
        <div
          role="radiogroup"
          aria-label="Tile colour metric"
          className="inline-flex items-center rounded-input border border-line bg-surface"
        >
          {Object.entries(METRIC_LABELS).map(([key, label]) => {
            const value = key as TileMetric;
            const isActive = metric === value;
            const CompIcon = METRIC_ICONS[value];
            return (
              <button
                key={value}
                type="button"
                role="radio"
                aria-pressed={isActive}
                onClick={() => onMetricChange(value)}
                className={cn(
                  "flex items-center gap-1.5 rounded-input px-2.5 py-1 text-12 font-medium transition-colors duration-300",
                  isActive
                    ? "bg-saffron text-ink border-saffron"
                    : "text-ink-500 border-transparent hover:bg-paper hover:text-ink",
                )}
              >
                <CompIcon aria-hidden={true} className="size-3.5" />
                {label}
              </button>
            );
          })}
        </div>
        {totalInstitutions > 0 && (
          <span className="text-11 text-ink-500">
            {totalInstitutions} institution{totalInstitutions === 1 ? "" : "s"}
          </span>
        )}
      </div>

      <svg
        className="relative mx-auto block h-auto w-full max-w-[320px]"
        role="img"
        aria-label="Tile grid of Indian states and union territories"
        width={7 * (TILE + GAP)}
        height={8 * (TILE + GAP)}
        viewBox={`0 ${-(TILE + GAP)} ${7 * (TILE + GAP)} ${8 * (TILE + GAP)}`}
      >
        {INDIA_TILE_GRID.map((tile) => {
          const agg = byState.get(tile.id);
          const hasData = agg !== undefined;
          const isHovered = hover === tile.id;
          const isTargeted = selectedState === tile.id || isHovered;

          let band: "ok" | "watch" | "breach" | "neutral" = "neutral";
          let valueText = "No data";
          let subtitle = "No institutions";

          if (hasData && agg) {
            if (metric === "compliance") {
              band = complianceBandFor(agg.avgScore);
              valueText = `${Math.round(agg.avgScore)}`;
              subtitle = `${agg.count} institution${agg.count === 1 ? "" : "s"} · ${agg.red} RED · ${agg.amber} AMBER`;
            } else {
              const rate = breachRate(agg);
              band =
                rate >= 60 ? "breach" : rate >= 30 ? "watch" : rate > 0 ? "ok" : "neutral";
              valueText = `${Math.round(rate)}%`;
              subtitle = `${agg.count} institution${agg.count === 1 ? "" : "s"} · ${Math.round(agg.avgScore)} avg score`;
            }
          }

          const fill =
            band === "breach"
              ? "var(--breach)"
              : band === "watch"
                ? "var(--watch)"
                : band === "ok"
                  ? "var(--ok)"
                  : "var(--neutral)";

          return (
            <g
              key={tile.id}
              transform={`translate(${tile.x * (TILE + GAP)},${tile.y * (TILE + GAP)})`}
            >
              <rect
                x={0}
                y={0}
                width={TILE}
                height={TILE}
                rx={3}
                fill={fill}
                stroke={isTargeted ? "var(--ink)" : "var(--line)"}
                strokeWidth={isTargeted ? 2 : 1}
                className="transition-[fill,stroke] duration-300 ease-in-out"
                onMouseEnter={() => setHover(tile.id)}
                onMouseLeave={() => setHover(null)}
                onClick={() => onSelectState(selectedState === tile.id ? null : tile.id)}
                role="button"
                tabIndex={0}
                aria-label={
                  hasData
                    ? `${tile.name}: ${valueText}, ${subtitle}`
                    : `${tile.name}: no data`
                }
                onKeyDown={(event) => {
                  if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    onSelectState(selectedState === tile.id ? null : tile.id);
                  }
                }}
              />
              {hasData && band !== "neutral" && (
                <text
                  x={TILE / 2}
                  y={TILE / 2 + 3}
                  textAnchor="middle"
                  dominantBaseline="central"
                  fill="var(--surface)"
                  className="text-[10px] font-semibold fill-surface"
                  pointerEvents="none"
                >
                  {tile.id === "DL" || tile.id === "MH" || tile.id === "TN"
                    ? Math.round(agg!.avgScore)
                    : ""}
                </text>
              )}
            </g>
          );
        })}
      </svg>

      <div className="mt-3 max-h-40 overflow-y-auto rounded-input border border-line bg-paper p-3 text-12">
        <p className="mb-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-ink-500">
          State summary
        </p>
        {data.length === 0 ? (
          <p className="text-[11px] text-ink-500">
            No institution data available for the selected filters.
          </p>
        ) : (
          <ul className="space-y-1.5">
            {[...byState.entries()]
              .sort((a, b) => b[1].red + b[1].amber - (a[1].red + a[1].amber))
              .map(([stateId, agg]) => {
                const tile = INDIA_TILE_GRID.find((t) => t.id === stateId);
                const rate = breachRate(agg);
                return (
                  <li
                    key={stateId}
                    className="flex items-center justify-between gap-2"
                  >
                    <span className="truncate text-[11px] text-ink-700">
                      {tile?.name ?? stateId}
                    </span>
                    <span
                      className={cn(
                        "text-[9px] font-medium rounded-input px-1.5 py-0.5",
                        complianceBandFor(agg.avgScore) === "ok"
                          ? "bg-ok-soft text-ok-strong"
                          : complianceBandFor(agg.avgScore) === "watch"
                            ? "bg-watch-soft text-watch-strong"
                            : "bg-breach-soft text-breach-strong",
                      )}
                    >
                      {Math.round(agg.avgScore)}
                    </span>
                    <span className="text-ink-500">
                      {agg.count} inst · {Math.round(rate)}% non-GREEN
                    </span>
                  </li>
                );
              })}
          </ul>
        )}
      </div>
    </section>
  );
}
