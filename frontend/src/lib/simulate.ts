/**
 * Local simulation used whenever the FastAPI backend is offline or slow.
 * Every run is seeded, so the demo shows the same numbers each time.
 */
import { FAMILIES, findMember, type FamilyId, type Timing } from "./families";
import { TODAY, addDays } from "./format";

/* ---------- seeded randomness ---------- */

function mulberry32(seed: number) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function hash(s: string) {
  let h = 2166136261;
  for (let i = 0; i < s.length; i++) h = Math.imul(h ^ s.charCodeAt(i), 16777619);
  return h >>> 0;
}

function normal(rand: () => number) {
  const u = Math.max(rand(), 1e-12);
  const v = rand();
  return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v);
}

function quantile(sorted: number[], q: number) {
  const i = (sorted.length - 1) * q;
  const lo = Math.floor(i);
  const hi = Math.ceil(i);
  return sorted[lo] + (sorted[hi] - sorted[lo]) * (i - lo);
}

/* ---------- 90-day forecast ---------- */

export type Band = { p10: number; p25?: number; p50: number; p75?: number; p90: number };
export type ForecastDay = Band & { d: number };

export type ForecastResult = {
  member_id: string;
  days: ForecastDay[];
  overdraft_probability: number;
  lowest_point: { day: number; p50: number };
  reasons: { feature: string; impact: number }[];
  source: "api" | "local";
};

const FORECAST_DAYS = 90;
const FORECAST_PATHS = 800;

export function simulateForecast(memberId: string): ForecastResult {
  const found = findMember(memberId);
  if (!found) throw new Error(`Unknown member ${memberId}`);
  const { cash, reasons } = found.member;
  const rand = mulberry32(hash(memberId));

  const columns: number[][] = Array.from({ length: FORECAST_DAYS + 1 }, () => []);
  let below = 0;

  for (let p = 0; p < FORECAST_PATHS; p++) {
    let bal = cash.balance;
    let min = bal;
    columns[0].push(bal);
    for (let d = 1; d <= FORECAST_DAYS; d++) {
      const date = addDays(TODAY, d);
      const dom = date.getDate();
      const dow = date.getDay();
      for (const inc of cash.income) {
        if (inc.kind === "monthly" && inc.day === dom) bal += inc.amount * (1 + normal(rand) * (inc.sd ?? 0));
        if (inc.kind === "weekly" && inc.weekday === dow) bal += Math.max(0, inc.amount * (1 + normal(rand) * inc.sd));
      }
      for (const b of cash.bills) if (b.day === dom) bal -= b.amount;
      const weekend = dow === 0 || dow === 6 ? 1.35 : 1;
      bal -= Math.max(0, (cash.dailySpend + normal(rand) * cash.dailySd) * weekend);
      // December costs more
      if (date.getMonth() === 11 && dom <= 24) bal -= cash.dailySpend * 0.25;
      if (rand() < cash.shockChance) bal -= cash.shockSize * (0.5 + rand());
      columns[d].push(bal);
      if (bal < min) min = bal;
    }
    if (min < 0) below++;
  }

  const days: ForecastDay[] = columns.map((col, d) => {
    const s = col.sort((a, b) => a - b);
    return { d, p10: quantile(s, 0.1), p50: quantile(s, 0.5), p90: quantile(s, 0.9) };
  });
  let lowest = days[1];
  for (const day of days.slice(1)) if (day.p50 < lowest.p50) lowest = day;

  return {
    member_id: memberId,
    days,
    overdraft_probability: below / FORECAST_PATHS,
    lowest_point: { day: lowest.d, p50: lowest.p50 },
    reasons,
    source: "local",
  };
}

export type RiskLevel = "low" | "watch" | "high";

export function riskLevel(p: number): RiskLevel {
  if (p < 0.1) return "low";
  if (p <= 0.3) return "watch";
  return "high";
}

export const RISK_LABEL: Record<RiskLevel, string> = { low: "Low Risk", watch: "Watch", high: "High Risk" };

/* ---------- 25-year Time Machine ---------- */

export type TimeMachineInput = {
  family_id: FamilyId;
  gift: number;
  timing: Timing;
  monthly_saving: number;
  lisa: boolean;
};

export type TimeMachineResult = {
  years: number[];
  genz_band: Band[];
  giver_band: Band[];
  deposit_goal: number[];
  p_deposit_by_target: number;
  p_parent_floor_safe: number;
  baseline: { p_deposit_by_target: number; p_parent_floor_safe: number };
  target_year: number;
  safety_floor: number;
  assumptions: Record<string, string>;
  source: "api" | "local";
};

const HORIZON = 25;
const TM_PATHS = 1500;
// Annual nominal returns, roughly in line with a long-run UK balanced fund (JST dataset) and a cautious pension pot.
const RECEIVER_RETURN = { mean: 0.045, sd: 0.1 };
const GIVER_RETURN = { mean: 0.035, sd: 0.07 };
const LISA_CAP = 4000;

function giftYear(timing: Timing, inheritanceYears: number) {
  return timing === "now" ? 0 : timing === "10y" ? 10 : inheritanceYears;
}

function runTimeMachine(input: TimeMachineInput, seed: number) {
  const cfg = FAMILIES[input.family_id].tm;
  const receiver = FAMILIES[input.family_id].members.find((m) => m.id === cfg.receiverId)!;
  const rand = mulberry32(seed);
  const gYear = giftYear(input.timing, cfg.inheritanceYears);
  const giverYears = cfg.inheritanceYears;

  const recCols: number[][] = Array.from({ length: HORIZON + 1 }, () => []);
  const givCols: number[][] = Array.from({ length: giverYears + 1 }, () => []);
  let hitDeposit = 0;
  let floorSafe = 0;

  const goal = Array.from({ length: HORIZON + 1 }, (_, t) => cfg.depositToday * (1 + cfg.houseGrowth) ** t);

  for (let p = 0; p < TM_PATHS; p++) {
    // receiver
    let pot = cfg.receiverSavings + (gYear === 0 ? input.gift : 0);
    recCols[0].push(pot);
    for (let t = 1; t <= HORIZON; t++) {
      const r = RECEIVER_RETURN.mean + normal(rand) * RECEIVER_RETURN.sd;
      const yearly = input.monthly_saving * 12;
      const age = receiver.age + t;
      const bonus = input.lisa && age <= 50 ? 0.25 * Math.min(yearly, LISA_CAP) : 0;
      pot = pot * (1 + r) + yearly + bonus;
      if (t === gYear) pot += input.gift;
      recCols[t].push(pot);
    }
    if (recCols[cfg.targetYears][p] >= goal[cfg.targetYears]) hitDeposit++;

    // giver
    let g = cfg.giverSavings - (gYear === 0 ? input.gift : 0);
    let safe = g >= cfg.safetyFloor;
    givCols[0].push(g);
    for (let t = 1; t <= giverYears; t++) {
      const r = GIVER_RETURN.mean + normal(rand) * GIVER_RETURN.sd;
      g = g * (1 + r) - cfg.giverDrawPerYear * 1.025 ** t;
      if (t === gYear && gYear < giverYears) g -= input.gift;
      if (g < cfg.safetyFloor) safe = false;
      givCols[t].push(g);
    }
    if (safe) floorSafe++;
  }

  const band = (cols: number[][]): Band[] =>
    cols.map((c) => {
      const s = c.sort((a, b) => a - b);
      return { p10: quantile(s, 0.1), p25: quantile(s, 0.25), p50: quantile(s, 0.5), p75: quantile(s, 0.75), p90: quantile(s, 0.9) };
    });

  return {
    genz_band: band(recCols),
    giver_band: band(givCols),
    goal,
    p_deposit: hitDeposit / TM_PATHS,
    p_floor: floorSafe / TM_PATHS,
  };
}

export function simulateTimeMachine(input: TimeMachineInput): TimeMachineResult {
  const fam = FAMILIES[input.family_id];
  const cfg = fam.tm;
  const seed = hash(input.family_id);
  const run = runTimeMachine(input, seed);
  const base = input.gift > 0 ? runTimeMachine({ ...input, gift: 0 }, seed) : run;
  const startYear = TODAY.getFullYear();
  const receiver = fam.members.find((m) => m.id === cfg.receiverId)!;
  const giver = fam.members.find((m) => m.id === cfg.giverId)!;

  return {
    years: Array.from({ length: HORIZON + 1 }, (_, t) => startYear + t),
    genz_band: run.genz_band,
    giver_band: run.giver_band,
    deposit_goal: run.goal,
    p_deposit_by_target: run.p_deposit,
    p_parent_floor_safe: run.p_floor,
    baseline: { p_deposit_by_target: base.p_deposit, p_parent_floor_safe: base.p_floor },
    target_year: startYear + cfg.targetYears,
    safety_floor: cfg.safetyFloor,
    assumptions: {
      "Deposit goal": `${cfg.depositPct}% of the average first-time-buyer price in the ${cfg.region} (HM Land Registry UK HPI, Aug 2026), rising ${Math.round(cfg.houseGrowth * 100)}% a year`,
      "Target year": `${startYear + cfg.targetYears}, when ${receiver.name} is ${receiver.age + cfg.targetYears}`,
      [`${receiver.name}'s savings`]: `Start at £${cfg.receiverSavings.toLocaleString("en-GB")}, growing ${+(RECEIVER_RETURN.mean * 100).toFixed(1)}% a year on average (±${+(RECEIVER_RETURN.sd * 100).toFixed(1)}%)`,
      [`${giver.name}'s savings`]: `Start at £${cfg.giverSavings.toLocaleString("en-GB")}, drawing £${cfg.giverDrawPerYear.toLocaleString("en-GB")} a year (rising with inflation), growing ${+(GIVER_RETURN.mean * 100).toFixed(1)}% a year on average`,
      "Safety floor": `£${cfg.safetyFloor.toLocaleString("en-GB")}, checked every year for ${cfg.inheritanceYears} years (ONS National Life Tables)`,
      "Lifetime ISA": "25% government bonus on up to £4,000 a year, paid until age 50",
      Scenarios: `${TM_PATHS.toLocaleString("en-GB")} Monte Carlo paths, fixed seed`,
    },
    source: "local",
  };
}

/* ---------- Claim Check fallback ---------- */

export type ClaimRating = "red" | "amber" | "green";
export type ClaimResult = {
  rating: ClaimRating;
  label: string;
  summary: string;
  signals: string[];
  sources: { title: string; url: string }[];
  source: "api" | "local";
};

const SRC = {
  scamsmart: { title: "FCA ScamSmart: avoid investment scams", url: "https://www.fca.org.uk/scamsmart/how-avoid-investment-scams" },
  register: { title: "FCA Financial Services Register", url: "https://register.fca.org.uk/" },
  crypto: { title: "FCA: cryptoassets", url: "https://www.fca.org.uk/consumers/cryptoassets" },
  recovery: { title: "FCA: recovery room scams", url: "https://www.fca.org.uk/consumers/recovery-room-scams" },
  loanfee: { title: "FCA: loan fee fraud", url: "https://www.fca.org.uk/consumers/loan-fee-fraud" },
  pension: { title: "FCA: pension scams", url: "https://www.fca.org.uk/consumers/pension-scams" },
  ca: { title: "Citizens Advice: check if something might be a scam", url: "https://www.citizensadvice.org.uk/consumer/scams/check-if-something-might-be-a-scam/" },
  lisa: { title: "GOV.UK: Lifetime ISA", url: "https://www.gov.uk/lifetime-isa" },
  isa: { title: "GOV.UK: Individual Savings Accounts", url: "https://www.gov.uk/individual-savings-accounts" },
  iht: { title: "GOV.UK: gifts and Inheritance Tax", url: "https://www.gov.uk/inheritance-tax/gifts" },
  pensionCredit: { title: "GOV.UK: Pension Credit", url: "https://www.gov.uk/pension-credit" },
  debt: { title: "GOV.UK: options for paying off your debts", url: "https://www.gov.uk/options-for-paying-off-your-debts" },
};

const RED_FLAGS: { re: RegExp; signal: string; src: keyof typeof SRC }[] = [
  { re: /guarantee|guaranteed|can'?t lose|no risk|risk[- ]free/i, signal: "Promises guaranteed returns or no risk", src: "scamsmart" },
  { re: /\b\d+\s?x\b|double your|triple your|1000%|\d{3,}%/i, signal: "Returns far above anything a regulated product offers", src: "scamsmart" },
  { re: /act now|today only|limited (spots|time)|before it'?s too late|last chance/i, signal: "Pressure to act quickly", src: "ca" },
  { re: /\b(dm|whatsapp|telegram|message me|link in bio)\b/i, signal: "Moves the conversation to private messages", src: "ca" },
  { re: /crypto|bitcoin|token|coin\b/i, signal: "Cryptoassets are largely unregulated in the UK", src: "crypto" },
  { re: /recover (your|lost)|get your money back/i, signal: "Offers to recover money already lost", src: "recovery" },
  { re: /upfront fee|pay a fee to (get|release)|loan.*fee/i, signal: "Asks for a fee before a loan is paid", src: "loanfee" },
  { re: /pension (release|unlock|liberation)|access your pension early/i, signal: "Offers early access to a pension", src: "pension" },
];

export function simulateClaimCheck(claim: string): ClaimResult {
  const text = claim.trim();
  const hits = RED_FLAGS.filter((f) => f.re.test(text));
  if (hits.length > 0) {
    const sources = [...new Set([...hits.map((h) => h.src), "register" as const])].map((k) => SRC[k]);
    const scam = hits.length >= 2;
    return {
      rating: "red",
      label: scam ? "Likely Scam" : "Warning Signs Found",
      summary: scam
        ? "This claim has several signs the FCA links to investment scams. No genuine investment can promise a fixed multiple of your money. Do not send money, and check any firm on the FCA Register first."
        : "This claim has a warning sign the FCA links to scams. Treat it with care and check any firm named on the FCA Register before you act.",
      signals: hits.map((h) => h.signal),
      sources,
      source: "local",
    };
  }
  if (/lifetime isa|\blisa\b/i.test(text) && /25%|bonus/i.test(text)) {
    return {
      rating: "green",
      label: "Accurate",
      summary: "Correct. The government adds a 25% bonus to Lifetime ISA savings, up to £1,000 a year on £4,000 paid in. You must be 18 to 39 to open one, and there is a 25% charge if you take money out for anything other than a first home or retirement.",
      signals: ["Matches GOV.UK guidance"],
      sources: [SRC.lisa, SRC.isa],
      source: "local",
    };
  }
  if (/inheritance tax|\biht\b|gift/i.test(text) && /3,?000|£3k|seven|7 years/i.test(text)) {
    return {
      rating: "amber",
      label: "Mostly Supported, With Caveats",
      summary: "Mostly right. Everyone can give away £3,000 a year free of Inheritance Tax, and larger gifts usually become tax-free after seven years. The details matter: unused allowance carries forward only one year, and gifts with strings attached do not count.",
      signals: ["Broadly matches GOV.UK", "Leaves out important conditions"],
      sources: [SRC.iht],
      source: "local",
    };
  }
  return {
    rating: "amber",
    label: "Needs Evidence",
    summary: "We could not match this claim to official guidance. That does not make it false, but ask where the figures come from and check any firm on the FCA Register before acting.",
    signals: ["No official source found for this claim"],
    sources: [SRC.register, SRC.ca],
    source: "local",
  };
}

export const SOURCES = SRC;
