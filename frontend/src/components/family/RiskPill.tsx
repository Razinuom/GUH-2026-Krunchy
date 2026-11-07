import { pct } from "@/lib/format";
import { RISK_LABEL, riskLevel, type RiskLevel } from "@/lib/simulate";
import { cn } from "@/lib/utils";

export const RISK_STYLE: Record<RiskLevel, { fg: string; bg: string }> = {
  low: { fg: "var(--good)", bg: "var(--good-soft)" },
  watch: { fg: "var(--warn)", bg: "var(--warn-soft)" },
  high: { fg: "var(--critical)", bg: "var(--critical-soft)" },
};

export function RiskPill({ p, long, className }: { p: number; long?: boolean; className?: string }) {
  const level = riskLevel(p);
  const s = RISK_STYLE[level];
  return (
    <span
      className={cn("num inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[.8rem] font-semibold", className)}
      style={{ color: s.fg, background: s.bg }}
    >
      <span className="h-1.5 w-1.5 rounded-full" style={{ background: s.fg }} aria-hidden="true" />
      {RISK_LABEL[level]}
      {long && <span className="font-normal">· {pct(p)} chance below £0</span>}
    </span>
  );
}
