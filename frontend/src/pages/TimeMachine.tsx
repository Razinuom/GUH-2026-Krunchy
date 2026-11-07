import { BandChart, Legend } from "@/components/charts/BandChart";
import { ErrorNote, Loading, SourceNote } from "@/components/DataState";
import { Disclaimer, Page } from "@/components/layout/Page";
import { PageHeader } from "@/components/layout/PageHeader";
import type { Timing } from "@/lib/families";
import { money, pct } from "@/lib/format";
import { useTimeMachine } from "@/lib/hooks";
import type { TimeMachineResult } from "@/lib/types";
import { cn } from "@/lib/utils";
import { useHeirloom } from "@/state/HeirloomContext";

function Slider({
  label, value, min, max, step, onChange, format,
}: { label: string; value: number; min: number; max: number; step: number; onChange: (v: number) => void; format: (v: number) => string }) {
  const id = label.replace(/\W+/g, "-").toLowerCase();
  return (
    <div>
      <div className="flex items-baseline justify-between gap-3">
        <label htmlFor={id} className="font-semibold">
          {label}
        </label>
        <span className="num font-display text-[1.25rem] font-extrabold tracking-[-0.02em]">{format(value)}</span>
      </div>
      <input
        id={id}
        type="range"
        className="range mt-3"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        style={{ ["--range" as string]: "var(--gen3)", ["--fill" as string]: `${((value - min) / (max - min)) * 100}%` }}
      />
      <div className="num mt-1 flex justify-between text-[.74rem] text-muted">
        <span>{format(min)}</span>
        <span>{format(max)}</span>
      </div>
    </div>
  );
}

function Change({ now, base, hasGift }: { now: number; base: number | undefined; hasGift: boolean }) {
  if (!hasGift || base === undefined) return <p className="mt-1 text-[.82rem] text-muted">No gift set</p>;
  const d = Math.round((now - base) * 100);
  return (
    <p className="num mt-1 text-[.82rem] text-muted">
      {d === 0 ? "No change" : `${d > 0 ? "+" : "−"}${Math.abs(d)} pts`} vs no gift
    </p>
  );
}

function mix(m: unknown) {
  const x = (m ?? {}) as { eq?: number; bond?: number };
  return `${Math.round((x.eq ?? 0) * 100)}% shares, ${Math.round((x.bond ?? 0) * 100)}% bonds`;
}

/** The backend's assumptions, in plain words (every value comes from the /timemachine response). */
function assumptionRows(r: TimeMachineResult, giver: string, receiver: string): [string, string][] {
  const a = r.assumptions as Record<string, unknown>;
  const iht = (a.inheritance_tax ?? {}) as { seven_year_rule?: string };
  const rows: [string, string][] = [
    ["Deposit goal", String(a.deposit_goal ?? "")],
    ["Starting savings", String(a.starting_savings ?? "")],
    ["Lifetime ISA", String(a.lifetime_isa_bonus ?? "")],
    ["Investments", `${receiver}: ${mix(a.young_adult_asset_mix)}. ${giver}: ${mix(a.grandparent_asset_mix)}.`],
    ["Safety floor", `${money(r.safety_floor)}: ${String(a.safety_floor_method ?? "")}`],
    [r.timing === "inheritance" ? "Inheritance" : "Inheritance Tax", r.timing === "inheritance" ? String(a.inheritance_mortality ?? "") : String(iht.seven_year_rule ?? "")],
    ["Method", String(a.method ?? "")],
  ];
  return rows.filter(([, v]) => v.trim().length > 0);
}

export default function TimeMachine() {
  const { familyData, tm, setTm } = useHeirloom();
  const cfg = familyData.tm;
  const ctl = cfg.controls;
  const receiver = familyData.members.find((m) => m.id === cfg.receiverId)!;
  const giver = familyData.members.find((m) => m.id === cfg.giverId)!;
  const { data: result, updating, unavailable, error } = useTimeMachine({
    family_id: familyData.id,
    gift: tm.gift,
    timing: tm.timing,
    monthly_saving: tm.monthly,
    lisa: tm.lisa,
  });
  // ignore a result left over from the other family while the new one loads
  const shown = result && result.family_id === familyData.id ? result : null;

  const timings: { id: Timing; label: string }[] = [
    { id: "now", label: "Now" },
    { id: "10y", label: "In 10 Years" },
    { id: "inheritance", label: `As Inheritance (About ${cfg.inheritanceYears} Years)` },
  ];

  return (
    <Page>
      <PageHeader
        page="tm"
        label="Time Machine"
        title={`${giver.name} and ${receiver.name}, 25 Years Ahead`}
        lead={
          familyData.id === "okafor"
            ? `Even with nothing to inherit, small steps add up. See how ${receiver.name}'s saving and a Lifetime ISA change the picture.`
            : `When should ${giver.name} give? See how the timing changes ${receiver.name}'s chance of a home deposit, and whether ${giver.name} stays safe.`
        }
      />

      <div className="grid grid-cols-[270px_1fr] lg960:grid-cols-1">
        <div className="space-y-8 border-r border-line pr-10 lg960:border-r-0 lg960:pr-0">
          <Slider
            label="Gift Amount"
            value={tm.gift}
            min={0}
            max={ctl.gift_max}
            step={ctl.gift_max > 5000 ? 500 : 100}
            onChange={(gift) => setTm({ gift })}
            format={money}
          />
          <fieldset>
            <legend className="font-semibold">When to Give It</legend>
            <div className="mt-3 space-y-2">
              {timings.map((t) => {
                const on = tm.timing === t.id;
                return (
                  <label
                    key={t.id}
                    className={cn(
                      "flex cursor-pointer items-center gap-3 rounded-xl border px-3.5 py-2.5 text-[.9rem] transition-colors has-[:focus-visible]:outline has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-accent",
                      on ? "border-transparent font-semibold" : "border-line hover:bg-sunk",
                    )}
                    style={on ? { background: "var(--p-tm)", boxShadow: "inset 0 0 0 1.5px var(--gen3)" } : undefined}
                  >
                    <input
                      type="radio"
                      name="timing"
                      className="sr-only"
                      checked={on}
                      onChange={() => setTm({ timing: t.id })}
                    />
                    <span
                      aria-hidden="true"
                      className="grid h-4 w-4 shrink-0 place-items-center rounded-full border-2"
                      style={{ borderColor: on ? "var(--gen3)" : "var(--muted)" }}
                    >
                      {on && <span className="h-2 w-2 rounded-full" style={{ background: "var(--gen3)" }} />}
                    </span>
                    {t.label}
                  </label>
                );
              })}
            </div>
          </fieldset>
          <Slider
            label={`${receiver.name} Saves Each Month`}
            value={tm.monthly}
            min={0}
            max={ctl.monthly_max}
            step={10}
            onChange={(monthly) => setTm({ monthly })}
            format={money}
          />
          <label className="flex cursor-pointer items-start gap-3">
            <input
              type="checkbox"
              checked={tm.lisa}
              onChange={(e) => setTm({ lisa: e.target.checked })}
              className="mt-1 h-[18px] w-[18px] shrink-0"
              style={{ accentColor: "var(--gen3)" }}
            />
            <span>
              <span className="block font-semibold">Use a Lifetime ISA</span>
              <span className="block text-[.82rem] text-muted">The government adds 25% on up to £4,000 a year.</span>
            </span>
          </label>
        </div>

        <div className="min-w-0 pl-10 lg960:mt-10 lg960:border-t lg960:border-line lg960:pl-0 lg960:pt-8">
          {!shown ? (
            error ? (
              <ErrorNote message={error} />
            ) : unavailable ? (
              <ErrorNote message="The Time Machine needs the backend for this scenario, and there is no saved result for it. Start the backend, or switch family to reset the controls to the saved scenario." />
            ) : (
              <Loading label={`Running 25 years of scenarios for ${receiver.name} and ${giver.name}…`} />
            )
          ) : (
            <div className={cn("transition-opacity", updating && "opacity-60")} aria-busy={updating}>
              {unavailable && (
                <p className="mb-4 rounded-xl p-3 text-[.85rem]" style={{ background: "var(--warn-soft)" }}>
                  Offline: the backend is not reachable, so these results are for the last scenario that ran, not the current controls.
                </p>
              )}
              <div className="grid grid-cols-2 divide-x divide-line border-b border-line pb-6 sm600:grid-cols-1 sm600:divide-x-0 sm600:divide-y">
                <div className="pr-6 sm600:pb-5 sm600:pr-0">
                  <p className="text-[.85rem] text-muted">
                    Chance {receiver.name} has a home deposit by {shown.target_year}
                  </p>
                  <p className="num font-display text-[3.2rem] font-extrabold leading-tight tracking-[-0.04em]" style={{ color: "var(--gen3)" }}>
                    {pct(shown.p_deposit_by_target)}
                  </p>
                  <Change now={shown.p_deposit_by_target} base={shown.baseline?.p_deposit_by_target} hasGift={shown.gift > 0} />
                </div>
                <div className="pl-6 sm600:pl-0 sm600:pt-5">
                  <p className="text-[.85rem] text-muted">
                    Chance {giver.name}&rsquo;s savings stay above {money(shown.safety_floor)}
                  </p>
                  <p className="num font-display text-[3.2rem] font-extrabold leading-tight tracking-[-0.04em]" style={{ color: "var(--gen1)" }}>
                    {pct(shown.p_parent_floor_safe)}
                  </p>
                  <Change now={shown.p_parent_floor_safe} base={shown.baseline?.p_parent_floor_safe} hasGift={shown.gift > 0} />
                </div>
              </div>

              <div className="mt-7 grid grid-cols-[1.6fr_1fr] gap-8 lg960:grid-cols-1">
                <div className="min-w-0">
                  <h2 className="font-display text-[1.1rem] font-bold tracking-[-0.02em]">{receiver.name}&rsquo;s Savings</h2>
                  <BandChart
                    data={shown.genz_band}
                    color="var(--gen3)"
                    height={260}
                    inner
                    goal={shown.deposit_goal}
                    vLine={{ x: shown.target_year - shown.years[0], label: String(shown.target_year) }}
                    xTicks={[0, 5, 10, 15, 20, 25].filter((t) => t < shown.years.length)}
                    xLabel={(i) => String(shown.years[i])}
                    ariaLabel={`${receiver.name}'s savings over ${shown.years.length - 1} years against a rising deposit goal. ${pct(shown.p_deposit_by_target)} chance of reaching the deposit by ${shown.target_year}.`}
                  />
                  <Legend color="var(--gen3)" items={["range", "inner", "median", "goal"]} />
                </div>
                <div className="min-w-0">
                  <h2 className="font-display text-[1.1rem] font-bold tracking-[-0.02em]">{giver.name}&rsquo;s Savings</h2>
                  <BandChart
                    data={shown.giver_band}
                    color="var(--gen1)"
                    height={260}
                    inner
                    floor={shown.safety_floor}
                    xTicks={[0, Math.round(shown.giver_band.length / 2) - 1, shown.giver_band.length - 1]}
                    xLabel={(i) => String(shown.years[i])}
                    ariaLabel={`${giver.name}'s savings over ${shown.giver_band.length - 1} years. ${pct(shown.p_parent_floor_safe)} chance of staying above the ${money(shown.safety_floor)} safety floor.`}
                  />
                  <Legend color="var(--gen1)" items={["range", "inner", "median", "floor"]} />
                </div>
              </div>

              <hr className="my-7 border-line" />
              <h2 className="font-display text-[1.1rem] font-bold tracking-[-0.02em]">Assumptions</h2>
              <dl className="mt-3 grid grid-cols-[max-content_1fr] gap-x-6 gap-y-1.5 text-[.8rem] sm600:grid-cols-1">
                {assumptionRows(shown, giver.name, receiver.name).map(([k, v]) => (
                  <div key={k} className="contents">
                    <dt className="font-semibold text-muted">{k}</dt>
                    <dd className="text-muted sm600:mb-2">{v}</dd>
                  </div>
                ))}
              </dl>
              <h2 className="mt-5 font-display text-[1rem] font-bold tracking-[-0.02em]">Sources</h2>
              <ul className="mt-2 space-y-1 text-[.8rem]">
                {shown.sources.map((s) => (
                  <li key={s.url}>
                    <a href={s.url} target="_blank" rel="noreferrer">
                      {s.title}
                    </a>
                  </li>
                ))}
              </ul>
              <Disclaimer className="mt-5" />
              <SourceNote className="mt-1" source={shown.source} live="Live result from the Heirloom Time Machine." />
            </div>
          )}
        </div>
      </div>
    </Page>
  );
}
