import { Disclaimer, Page } from "@/components/layout/Page";
import { PageHeader } from "@/components/layout/PageHeader";

const TOOLS = [
  {
    title: "Next 90 Days",
    color: "var(--gen2)",
    text: "Every payday, bill and everyday spend is simulated 2,000 times to give a likely range, the lowest point and the chance of going below £0, with the drivers behind it.",
  },
  {
    title: "Early Warning",
    color: "var(--critical)",
    text: "A LightGBM hardship model reads 12 months of spending patterns, scores the risk of going overdrawn and shows the reasons behind it (SHAP values), so no warning arrives without an explanation.",
  },
  {
    title: "Time Machine",
    color: "var(--gen3)",
    text: "A 25-year Monte Carlo run compares giving now, in 10 years or as an inheritance: the young adult's chance of a deposit and the grandparent's chance of staying above a safety floor.",
  },
  {
    title: "Voice Coach",
    color: "#D9532F",
    text: "An ElevenLabs voice agent answers in English, Polish, Malay or Mandarin, calling the same forecast, what-if and official-guidance tools the dashboard uses.",
  },
  {
    title: "Claim Check",
    color: "var(--accent)",
    text: "Paste a money claim from social media. It is checked for the FCA's scam warning signs, any firm it names is looked up in the FCA's published warnings, and its figures are checked live against GOV.UK, MoneyHelper and the FCA (Firecrawl). Every rating quotes its sources.",
  },
];

const DATA = [
  ["Transactions", "Synthetic families calibrated to the ONS Living Costs and Food Survey, ready for the NatWest Account and Transaction API"],
  ["House prices", "HM Land Registry UK House Price Index (regional first-time-buyer prices)"],
  ["Earnings", "ONS Annual Survey of Hours and Earnings (salaries by age), with 2026/27 income tax and National Insurance"],
  ["Pensions", "GOV.UK full new State Pension rate"],
  ["Life expectancy", "ONS National Life Tables (inheritance timing in the Time Machine)"],
  ["Market returns and inflation", "Jordà-Schularick-Taylor long-run UK share, bond and house-price returns, 1870-2020, in today's money"],
  ["Rules", "GOV.UK, MoneyHelper and FCA pages searched live with Firecrawl (cached), plus GOV.UK, FCA and Citizens Advice pages saved to disk"],
];

const GUARDRAILS = [
  "Guidance and scenarios, never regulated financial advice or stock tips.",
  "Every figure has a source or a visible assumption.",
  "Talk to a Person is always one tap away: MoneyHelper, StepChange and Citizens Advice.",
  "Voice is opt-in: the microphone only turns on when you start a call.",
  "Risk is never shown by colour alone; it always has a text label.",
];

export default function About() {
  return (
    <Page>
      <PageHeader
        page="about"
        label="How It Works"
        title="A Plan Every Family Can Have"
        lead="Wealthy families get an adviser and regular money conversations. Heirloom brings the same planning to everyone, across three generations."
      />

      <h2 className="font-display text-[1.35rem] font-bold tracking-[-0.02em]">Five Tools, One Plan</h2>
      <ul className="mt-4 divide-y divide-line border-y border-line">
        {TOOLS.map((t) => (
          <li key={t.title} className="grid grid-cols-[220px_1fr] gap-6 py-4 md720:grid-cols-1 md720:gap-1">
            <p className="flex items-center gap-2.5 font-semibold">
              <span className="h-2.5 w-2.5 rounded-full" style={{ background: t.color }} aria-hidden="true" />
              {t.title}
            </p>
            <p className="text-muted">{t.text}</p>
          </li>
        ))}
      </ul>

      <div className="mt-12 grid grid-cols-2 lg960:grid-cols-1">
        <div className="pr-10 lg960:pr-0">
          <h2 className="font-display text-[1.35rem] font-bold tracking-[-0.02em]">Where the Numbers Come From</h2>
          <dl className="mt-4 space-y-3">
            {DATA.map(([k, v]) => (
              <div key={k}>
                <dt className="font-semibold">{k}</dt>
                <dd className="text-muted">{v}</dd>
              </div>
            ))}
          </dl>
        </div>
        <div className="border-l border-line pl-10 lg960:mt-10 lg960:border-l-0 lg960:border-t lg960:pl-0 lg960:pt-8">
          <h2 className="font-display text-[1.35rem] font-bold tracking-[-0.02em]">Guardrails</h2>
          <ul className="mt-4 space-y-3">
            {GUARDRAILS.map((g) => (
              <li key={g} className="flex gap-3">
                <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-accent" aria-hidden="true" />
                {g}
              </li>
            ))}
          </ul>
          <h2 className="mt-10 font-display text-[1.35rem] font-bold tracking-[-0.02em]">Behind the Scenes</h2>
          <p className="mt-3 text-muted">
            Four agents share the work. The Researcher finds and cites official rules, the Forecaster runs the models, the Guardian filters out advice it
            should not give and spots scams and distress, and the Coach speaks to the family.
          </p>
        </div>
      </div>
      <hr className="mb-5 mt-12 border-line" />
      <Disclaimer />
    </Page>
  );
}
