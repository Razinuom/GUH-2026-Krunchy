import { LifeBuoy } from "lucide-react";
import { BandChart, Legend } from "@/components/charts/BandChart";
import { ErrorNote, Loading, SourceNote } from "@/components/DataState";
import { RiskPill, RISK_LABEL, RISK_STYLE } from "@/components/family/RiskPill";
import { PersonPicker } from "@/components/family/PersonPicker";
import { Disclaimer, Page } from "@/components/layout/Page";
import { PageHeader } from "@/components/layout/PageHeader";
import { longDate, money, parseDate, pct, shortDate } from "@/lib/format";
import { useForecast, useHardship } from "@/lib/hooks";
import type { ForecastResult, HardshipResult } from "@/lib/types";
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

const points = (impact: number) => `${impact > 0 ? "+" : "−"}${Math.abs(impact * 100).toFixed(1)} pts`;

/** Early warning: the hardship model's SHAP reasons, plus the Guardian handoff when risk is high. */
function EarlyWarning({ forecast, hardship, name }: { forecast: ForecastResult; hardship: HardshipResult | null; name: string }) {
  const { openHelp } = useHeirloom();
  const level = forecast.risk_band;
  const lowDate = shortDate(parseDate(forecast.lowest_point.date));
  const reasons = hardship?.reasons ?? [];
  const max = Math.max(...reasons.map((r) => Math.abs(r.impact)), 0.01);
  const tip = reasons.find((r) => r.impact > 0 && r.tip);

  return (
    <div>
      <h2 className="font-display text-[1.35rem] font-bold tracking-[-0.02em]">Why This Risk Level</h2>
      {!hardship ? (
        <p className="mt-4 text-muted">Loading the early-warning model…</p>
      ) : (
        <>
          <p className="mt-1 text-[.82rem] text-muted">
            Early-warning score <strong className="num text-ink">{hardship.risk_score}/100</strong> ({RISK_LABEL[hardship.band]}), from the last 12 months of
            spending patterns.
          </p>
          <ul className="mt-4 space-y-3.5">
            {reasons.map((r) => {
              const up = r.impact > 0;
              return (
                <li key={r.key}>
                  <p className="text-[.9rem]">{r.feature}</p>
                  <p className="text-[.76rem] text-muted">{r.detail}</p>
                  <div className="mt-1.5 flex items-center gap-3">
                    <div className="h-2 flex-1 rounded-full bg-sunk">
                      <div
                        className="h-2 rounded-full"
                        style={{ width: `${(Math.abs(r.impact) / max) * 100}%`, background: up ? "var(--critical)" : "var(--good)" }}
                      />
                    </div>
                    <span className="num w-16 text-right text-[.82rem] font-semibold" style={{ color: up ? "var(--critical)" : "var(--good)" }}>
                      {points(r.impact)}
                    </span>
                  </div>
                </li>
              );
            })}
          </ul>
          <p className="mt-3 text-[.76rem] text-muted">
            How much each factor moves the risk score compared with an average household (SHAP values from the {hardship.model.type} hardship model). Red pushes
            risk up; green pulls it down.
          </p>
        </>
      )}

      {level === "high" ? (
        <div className="mt-7 rounded-2xl p-5" style={{ background: "var(--critical-soft)" }}>
          <p className="font-display text-[1.1rem] font-bold" style={{ color: RISK_STYLE.high.fg }}>
            Guardian: High Risk Detected
          </p>
          <p className="mt-1.5">
            There is {/^(8|11|18)/.test(pct(forecast.overdraft_probability)) ? "an" : "a"} {pct(forecast.overdraft_probability)} chance {name}&rsquo;s balance
            drops below £0 in the next 90 days.{" "}
            {hardship?.guardian.message}
          </p>
          {hardship && hardship.guardian.resources.length > 0 && (
            <ul className="mt-3 space-y-1 text-[.9rem]">
              {hardship.guardian.resources.map((r) => (
                <li key={r.name}>
                  {r.url ? (
                    <a href={r.url} target="_blank" rel="noreferrer" className="font-semibold">
                      {r.name}
                    </a>
                  ) : (
                    <span className="font-semibold">{r.name}</span>
                  )}
                  {r.phone && <span className="num"> · {r.phone}</span>}
                  {r.note && <span className="text-muted"> · {r.note}</span>}
                </li>
              ))}
            </ul>
          )}
          <button onClick={openHelp} className="mt-4 inline-flex items-center gap-2 rounded-full bg-ink px-4 py-2 font-semibold text-surface hover:opacity-90">
            <LifeBuoy className="h-4 w-4" /> Talk to a Person
          </button>
        </div>
      ) : level === "watch" ? (
        <div className="mt-7 rounded-2xl bg-accent-soft p-5">
          <p className="font-display text-[1.1rem] font-bold text-accent">Suggested Next Step</p>
          <p className="mt-1.5">
            The tightest days are around {lowDate}, when the balance is most likely to be about {money(forecast.lowest_point.p50)}.
            {forecast.reasons[0] && (
              <>
                {" "}
                Biggest driver: {forecast.reasons[0].feature} ({forecast.reasons[0].detail}).
              </>
            )}
          </p>
          {tip && (
            <p className="mt-2 text-[.9rem]">
              {tip.tip}{" "}
              {tip.source && (
                <a href={tip.source} target="_blank" rel="noreferrer">
                  Source
                </a>
              )}
            </p>
          )}
        </div>
      ) : (
        <div className="mt-7 rounded-2xl bg-accent-soft p-5">
          <p className="font-display text-[1.1rem] font-bold text-accent">Looking Steady</p>
          <p className="mt-1.5">
            {name}&rsquo;s balance stays above £0 in {pct(1 - forecast.overdraft_probability)} of the simulated next 90 days. Anything left at the end of
            the month could go into savings.
          </p>
        </div>
      )}
    </div>
  );
}

function Drivers({ forecast }: { forecast: ForecastResult }) {
  if (forecast.reasons.length === 0) return null;
  return (
    <div className="mt-8">
      <h2 className="font-display text-[1.1rem] font-bold tracking-[-0.02em]">Biggest Drivers in the Next 90 Days</h2>
      <ul className="mt-3 divide-y divide-line border-y border-line">
        {forecast.reasons.map((r) => (
          <li key={r.feature} className="flex items-baseline justify-between gap-4 py-2.5">
            <span>
              <span className="font-semibold">{r.feature}</span>
              <span className="text-muted"> · {r.detail}</span>
            </span>
            <span className="num shrink-0 text-[.85rem] font-semibold" style={{ color: "var(--critical)" }}>
              {points(r.impact)}
            </span>
          </li>
        ))}
      </ul>
      <p className="mt-2 text-[.76rem] text-muted">Each driver&rsquo;s share of the chance of going below £0 (Shapley attribution over the simulation).</p>
    </div>
  );
}

export default function Forecast() {
  const { familyData, member, setMemberId } = useHeirloom();
  const { data: forecast, loading, error } = useForecast(member.id);
  const { data: hardship } = useHardship(member.id);
  const color = "var(--sel)";
  const paths = forecast?.assumptions.paths?.toLocaleString("en-GB") ?? "2,000";

  return (
    <Page>
      <PageHeader
        page="forecast"
        label="Next 90 Days"
        title={`Next 90 Days for ${member.name}`}
        lead={`Every payday, bill and day-to-day spend, simulated ${paths} times to show the likely range.`}
        aside={<PersonPicker members={familyData.members} value={member.id} onChange={setMemberId} />}
      />

      {!forecast ? (
        error ? <ErrorNote message={error} /> : <Loading label={loading ? `Running ${member.name}'s forecast…` : ""} />
      ) : (
        <div className="grid grid-cols-[1.7fr_1fr] lg960:grid-cols-1">
          <div className="min-w-0 pr-10 lg960:pr-0">
            <BandChart
              data={forecast.days}
              color={color}
              height={320}
              zeroLine
              lowest={{ x: forecast.lowest_point.day, y: forecast.lowest_point.p50 }}
              xTicks={[0, 30, 60, 90].filter((d) => d < forecast.days.length)}
              xLabel={(d) => (d === 0 ? "Today" : shortDate(parseDate(forecast.days[d].date)))}
              ariaLabel={`Forecast balance for ${member.name} over 90 days. Most likely lowest point ${money(forecast.lowest_point.p50)} around ${shortDate(parseDate(forecast.lowest_point.date))}. ${pct(forecast.overdraft_probability)} chance of going below £0.`}
            />
            <Legend color={color} items={["range", "median", "zero"]} />

            <div className="mt-7 grid grid-cols-3 divide-x divide-line border-y border-line sm600:grid-cols-1 sm600:divide-x-0 sm600:divide-y">
              <Stat
                label="Lowest Point"
                value={money(forecast.lowest_point.p50)}
                sub={`Around ${shortDate(parseDate(forecast.lowest_point.date))} (bad case ${money(forecast.lowest_point.p10)})`}
              />
              <Stat
                label="Chance Below £0"
                value={pct(forecast.overdraft_probability)}
                color={RISK_STYLE[forecast.risk_band].fg}
                pill={<RiskPill level={forecast.risk_band} p={forecast.overdraft_probability} className="mt-1" />}
                sub="At any point in 90 days"
              />
              <Stat
                label="Balance in 90 Days"
                value={money(forecast.days[forecast.days.length - 1].p50)}
                sub={`Likely ${money(forecast.days[forecast.days.length - 1].p10)} to ${money(forecast.days[forecast.days.length - 1].p90)} · today ${money(forecast.start_balance)}`}
              />
            </div>
            <Drivers forecast={forecast} />
            <Disclaimer className="mt-4" />
            <SourceNote
              className="mt-1"
              source={forecast.source}
              live={`Live result from the Heirloom forecaster, starting ${longDate(parseDate(forecast.start_date))}.`}
            />
          </div>

          <aside className="border-l border-line pl-10 lg960:mt-10 lg960:border-l-0 lg960:border-t lg960:pl-0 lg960:pt-8">
            <EarlyWarning forecast={forecast} hardship={hardship} name={member.name} />
          </aside>
        </div>
      )}
    </Page>
  );
}
