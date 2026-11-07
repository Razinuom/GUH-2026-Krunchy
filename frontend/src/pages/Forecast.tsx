import { LifeBuoy } from "lucide-react";
import { BandChart, Legend } from "@/components/charts/BandChart";
import { RiskPill, RISK_STYLE } from "@/components/family/RiskPill";
import { PersonPicker } from "@/components/family/PersonPicker";
import { Disclaimer, Page } from "@/components/layout/Page";
import { PageHeader } from "@/components/layout/PageHeader";
import { addDays, money, pct, shortDate, TODAY } from "@/lib/format";
import { useForecast } from "@/lib/hooks";
import { riskLevel, type ForecastResult } from "@/lib/simulate";
import { useHeirloom } from "@/state/HeirloomContext";

function Stat({ label, value, sub, color, pill }: { label: string; value: string; sub: string; color?: string; pill?: React.ReactNode }) {
  return (
    <div className="px-6 py-5 first:pl-0 sm600:px-0">
      <p className="text-[.78rem] text-muted">{label}</p>
      <p className="num mt-1 font-display text-[2.2rem] font-extrabold leading-tight tracking-[-0.035em]" style={{ color }}>
        {value}
      </p>
      {pill}
      <p className="mt-1 text-[.78rem] text-muted">{sub}</p>
    </div>
  );
}

function EarlyWarning({ forecast, name }: { forecast: ForecastResult; name: string }) {
  const { openHelp } = useHeirloom();
  const level = riskLevel(forecast.overdraft_probability);
  const max = Math.max(...forecast.reasons.map((r) => Math.abs(r.impact)), 0.01);
  const lowDate = shortDate(addDays(TODAY, forecast.lowest_point.day));

  return (
    <div>
      <h2 className="font-display text-[1.35rem] font-bold tracking-[-0.02em]">Why This Risk Level</h2>
      <ul className="mt-4 space-y-3.5">
        {forecast.reasons.map((r) => {
          const up = r.impact > 0;
          return (
            <li key={r.feature}>
              <p className="text-[.9rem]">{r.feature}</p>
              <div className="mt-1.5 flex items-center gap-3">
                <div className="h-2 flex-1 rounded-full bg-sunk">
                  <div
                    className="h-2 rounded-full"
                    style={{ width: `${(Math.abs(r.impact) / max) * 100}%`, background: up ? "var(--critical)" : "var(--good)" }}
                  />
                </div>
                <span className="num w-12 text-right text-[.82rem] font-semibold" style={{ color: up ? "var(--critical)" : "var(--good)" }}>
                  {up ? "+" : "−"}
                  {Math.abs(r.impact).toFixed(2)}
                </span>
              </div>
            </li>
          );
        })}
      </ul>
      <p className="mt-3 text-[.76rem] text-muted">
        Contribution of each factor to the overdraft risk score (SHAP values from the hardship model). Red pushes risk up; green pulls it down.
      </p>

      {level === "high" ? (
        <div className="mt-7 rounded-2xl p-5" style={{ background: "var(--critical-soft)" }}>
          <p className="font-display text-[1.1rem] font-bold" style={{ color: RISK_STYLE.high.fg }}>
            Guardian: High Risk Detected
          </p>
          <p className="mt-1.5">
            There is a {pct(forecast.overdraft_probability)} chance {name}&rsquo;s balance drops below £0 in the next 90 days. Free, confidential help from a debt
            charity can set up a budget or a breathing space before that happens.
          </p>
          <button onClick={openHelp} className="mt-4 inline-flex items-center gap-2 rounded-full bg-ink px-4 py-2 font-semibold text-surface hover:opacity-90">
            <LifeBuoy className="h-4 w-4" /> See Free Help
          </button>
        </div>
      ) : level === "watch" ? (
        <div className="mt-7 rounded-2xl bg-accent-soft p-5">
          <p className="font-display text-[1.1rem] font-bold text-accent">Suggested Next Step</p>
          <p className="mt-1.5">
            The tightest days are around {lowDate}. Moving a bill payment until after payday, or keeping a small buffer of about £150, would bring the risk
            down to low.
          </p>
        </div>
      ) : (
        <div className="mt-7 rounded-2xl bg-accent-soft p-5">
          <p className="font-display text-[1.1rem] font-bold text-accent">Looking Steady</p>
          <p className="mt-1.5">
            {name}&rsquo;s money covers the next 90 days in almost every scenario. Anything left at the end of the month could go into savings.
          </p>
        </div>
      )}
    </div>
  );
}

export default function Forecast() {
  const { familyData, member, setMemberId } = useHeirloom();
  const forecast = useForecast(member.id);
  const level = riskLevel(forecast.overdraft_probability);
  const color = "var(--sel)";
  const lowDate = addDays(TODAY, forecast.lowest_point.day);
  const end = forecast.days[forecast.days.length - 1];
  const ticks = [0, 30, 60, 90].filter((d) => d < forecast.days.length);

  return (
    <Page>
      <PageHeader
        page="forecast"
        label="Next 90 Days"
        title={`Next 90 Days for ${member.name}`}
        lead="Every payday, bill and day-to-day spend, run 800 times to show the likely range."
        aside={<PersonPicker members={familyData.members} value={member.id} onChange={setMemberId} />}
      />

      <div className="grid grid-cols-[1.7fr_1fr] lg960:grid-cols-1">
        <div className="min-w-0 pr-10 lg960:pr-0">
          <BandChart
            data={forecast.days}
            color={color}
            height={320}
            zeroLine
            lowest={{ x: forecast.lowest_point.day, y: forecast.lowest_point.p50 }}
            xTicks={ticks}
            xLabel={(d) => (d === 0 ? "Today" : shortDate(addDays(TODAY, d)))}
            ariaLabel={`Forecast balance for ${member.name} over 90 days. Most likely lowest point ${money(forecast.lowest_point.p50)} around ${shortDate(lowDate)}. ${pct(forecast.overdraft_probability)} chance of going below £0.`}
          />
          <Legend color={color} items={["range", "median", "zero"]} />

          <div className="mt-7 grid grid-cols-3 divide-x divide-line border-y border-line sm600:grid-cols-1 sm600:divide-x-0 sm600:divide-y">
            <Stat label="Lowest Point" value={money(forecast.lowest_point.p50)} sub={`Around ${shortDate(lowDate)}`} />
            <Stat
              label="Chance Below £0"
              value={pct(forecast.overdraft_probability)}
              color={RISK_STYLE[level].fg}
              pill={<RiskPill p={forecast.overdraft_probability} className="mt-1" />}
              sub="At any point in 90 days"
            />
            <Stat label="Balance in 90 Days" value={money(end.p50)} sub={`Likely ${money(end.p10)} to ${money(end.p90)}`} />
          </div>
          <Disclaimer className="mt-4" />
          <p className="mt-1 text-[.76rem] text-muted">
            {forecast.source === "api" ? "Live result from the Heirloom forecaster." : "Offline simulation (the forecaster API is not reachable)."} Dates pinned to{" "}
            {TODAY.toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric" })} for the demo.
          </p>
        </div>

        <aside className="border-l border-line pl-10 lg960:mt-10 lg960:border-l-0 lg960:border-t lg960:pl-0 lg960:pt-8">
          <EarlyWarning forecast={forecast} name={member.name} />
        </aside>
      </div>
    </Page>
  );
}
