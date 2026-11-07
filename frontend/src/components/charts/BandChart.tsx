import { useLayoutEffect, useMemo, useRef, useState } from "react";
import type { Band } from "@/lib/simulate";
import { moneyShort } from "@/lib/format";

type Props = {
  data: Band[];
  color: string;
  ariaLabel: string;
  height?: number;
  /** label for an x index */
  xLabel: (i: number) => string;
  xTicks: number[];
  /** draw the inner p25–p75 band */
  inner?: boolean;
  zeroLine?: boolean;
  goal?: number[];
  floor?: number;
  vLine?: { x: number; label: string };
  lowest?: { x: number; y: number };
};

function useWidth<T extends HTMLElement>() {
  const ref = useRef<T>(null);
  const [w, setW] = useState(600);
  useLayoutEffect(() => {
    if (!ref.current) return;
    const ro = new ResizeObserver(([e]) => setW(Math.max(240, e.contentRect.width)));
    ro.observe(ref.current);
    return () => ro.disconnect();
  }, []);
  return [ref, w] as const;
}

function niceTicks(min: number, max: number, count = 4) {
  const span = max - min || 1;
  const step0 = span / count;
  const mag = 10 ** Math.floor(Math.log10(step0));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => s >= step0) ?? step0;
  const start = Math.floor(min / step) * step;
  const ticks: number[] = [];
  for (let v = start; v <= max + step * 0.01; v += step) ticks.push(Math.round(v * 100) / 100);
  return ticks;
}

export function BandChart({ data, color, ariaLabel, height = 300, xLabel, xTicks, inner, zeroLine, goal, floor, vLine, lowest }: Props) {
  const [ref, width] = useWidth<HTMLDivElement>();
  const pad = { top: 14, right: 16, bottom: 28, left: 48 };
  const iw = width - pad.left - pad.right;
  const ih = height - pad.top - pad.bottom;

  const { yTicks, y0, y1 } = useMemo(() => {
    let lo = Math.min(...data.map((d) => d.p10));
    let hi = Math.max(...data.map((d) => d.p90));
    if (zeroLine) lo = Math.min(lo, 0);
    if (goal) hi = Math.max(hi, ...goal);
    if (floor !== undefined) lo = Math.min(lo, floor);
    lo = Math.min(lo, 0);
    const t = niceTicks(lo, hi);
    return { yTicks: t, y0: t[0], y1: t[t.length - 1] };
  }, [data, zeroLine, goal, floor]);

  const n = data.length - 1;
  const x = (i: number) => pad.left + (i / n) * iw;
  const y = (v: number) => pad.top + ih - ((v - y0) / (y1 - y0 || 1)) * ih;

  const area = (lo: (b: Band) => number, hi: (b: Band) => number) =>
    data.map((b, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(hi(b)).toFixed(1)}`).join("") +
    data
      .map((b, i) => [i, b] as const)
      .reverse()
      .map(([i, b]) => `L${x(i).toFixed(1)},${y(lo(b)).toFixed(1)}`)
      .join("") +
    "Z";
  const line = (vals: number[]) => vals.map((v, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join("");

  return (
    <div ref={ref} className="w-full">
      <svg width={width} height={height} role="img" aria-label={ariaLabel} className="block overflow-visible">
        {yTicks.map((t) => (
          <g key={t}>
            <line x1={pad.left} x2={width - pad.right} y1={y(t)} y2={y(t)} stroke="var(--line)" />
            <text x={pad.left - 8} y={y(t) + 4} textAnchor="end" fontSize="11" fill="var(--muted)" className="num">
              {moneyShort(t)}
            </text>
          </g>
        ))}
        {xTicks.map((i) => (
          <text key={i} x={x(i)} y={height - 8} textAnchor="middle" fontSize="11" fill="var(--muted)" className="num">
            {xLabel(i)}
          </text>
        ))}

        <path d={area((b) => b.p10, (b) => b.p90)} fill={color} fillOpacity={0.2} />
        {inner && <path d={area((b) => b.p25 ?? b.p50, (b) => b.p75 ?? b.p50)} fill={color} fillOpacity={0.22} />}

        {zeroLine && y0 <= 0 && <line x1={pad.left} x2={width - pad.right} y1={y(0)} y2={y(0)} stroke="var(--critical)" strokeWidth={1.4} />}
        {floor !== undefined && (
          <g>
            <line x1={pad.left} x2={width - pad.right} y1={y(floor)} y2={y(floor)} stroke="var(--critical)" strokeWidth={1.6} strokeDasharray="6 5" />
            <text x={width - pad.right} y={y(floor) - 6} textAnchor="end" fontSize="11" fill="var(--critical)" fontWeight={600}>
              Safety Floor {moneyShort(floor)}
            </text>
          </g>
        )}
        {goal && (
          <g>
            <path d={line(goal)} fill="none" stroke="var(--ink)" strokeWidth={1.6} strokeDasharray="6 5" />
            <text x={x(n)} y={y(goal[n]) - 6} textAnchor="end" fontSize="11" fill="var(--ink)" fontWeight={600}>
              Deposit Goal
            </text>
          </g>
        )}
        {vLine && (
          <g>
            <line x1={x(vLine.x)} x2={x(vLine.x)} y1={pad.top} y2={pad.top + ih} stroke="var(--muted)" strokeDasharray="4 4" />
            <text x={x(vLine.x) + 6} y={pad.top + 10} fontSize="11" fill="var(--muted)" fontWeight={600}>
              {vLine.label}
            </text>
          </g>
        )}

        <path d={line(data.map((b) => b.p50))} fill="none" stroke={color} strokeWidth={2.4} strokeLinejoin="round" strokeLinecap="round" />
        <circle cx={x(n)} cy={y(data[n].p50)} r={4.5} fill={color} />
        {lowest && <circle cx={x(lowest.x)} cy={y(lowest.y)} r={7} fill="none" stroke="var(--critical)" strokeWidth={2} />}
      </svg>
    </div>
  );
}

export function Legend({ color, items }: { color: string; items: ("range" | "inner" | "median" | "zero" | "goal" | "floor")[] }) {
  const map = {
    range: { label: "Likely Range (10th–90th Percentile)", swatch: <span className="h-3 w-5 rounded-sm" style={{ background: color, opacity: 0.25 }} /> },
    inner: { label: "Middle Half (25th–75th)", swatch: <span className="h-3 w-5 rounded-sm" style={{ background: color, opacity: 0.45 }} /> },
    median: { label: "Most Likely Balance", swatch: <span className="h-[3px] w-5 rounded" style={{ background: color }} /> },
    zero: { label: "£0", swatch: <span className="h-[2px] w-5 bg-critical" /> },
    goal: { label: "Deposit Goal", swatch: <span className="w-5 border-t-2 border-dashed border-ink" /> },
    floor: { label: "Safety Floor", swatch: <span className="w-5 border-t-2 border-dashed border-critical" /> },
  };
  return (
    <ul className="mt-3 flex flex-wrap gap-x-5 gap-y-1.5 text-[.78rem] text-muted">
      {items.map((k) => (
        <li key={k} className="flex items-center gap-2">
          {map[k].swatch}
          {map[k].label}
        </li>
      ))}
    </ul>
  );
}
