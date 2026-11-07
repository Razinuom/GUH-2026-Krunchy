export type Gen = 1 | 2 | 3;
export type FamilyId = "nowak" | "okafor";

export type IncomeRule =
  | { kind: "monthly"; day: number; amount: number; label: string; sd?: number }
  | { kind: "weekly"; weekday: number; amount: number; label: string; sd: number };

export type Bill = { day: number; amount: number; label: string };

export type Member = {
  id: string;
  name: string;
  age: number;
  gen: Gen;
  role: string;
  speaksPolish?: boolean;
  /** cash-flow inputs for the local fallback simulation */
  cash: {
    balance: number;
    income: IncomeRule[];
    bills: Bill[];
    dailySpend: number;
    dailySd: number;
    /** chance on any day of a one-off cost (car, boiler, school trip) */
    shockChance: number;
    shockSize: number;
  };
  /** hardship-model explanations (SHAP), used when the backend is offline */
  reasons: { feature: string; impact: number }[];
};

export type TimeMachineConfig = {
  receiverId: string;
  giverId: string;
  region: string;
  /** deposit target today, from HM Land Registry UK HPI (first-time-buyer price) */
  depositToday: number;
  depositPct: number;
  houseGrowth: number;
  targetYears: number;
  receiverSavings: number;
  giverSavings: number;
  giverDrawPerYear: number;
  safetyFloor: number;
  inheritanceYears: number;
  giftMax: number;
  monthlyMax: number;
  defaults: { gift: number; timing: Timing; monthly: number; lisa: boolean };
};

export type Timing = "now" | "10y" | "inheritance";

export type Family = {
  id: FamilyId;
  name: string;
  members: Member[];
  tm: TimeMachineConfig;
};

export const GEN_LABEL: Record<Gen, string> = { 1: "Grandparent", 2: "Parent", 3: "Young Adult" };
export const GEN_VAR: Record<Gen, string> = { 1: "var(--gen1)", 2: "var(--gen2)", 3: "var(--gen3)" };

export const FAMILIES: Record<FamilyId, Family> = {
  nowak: {
    id: "nowak",
    name: "Nowak Family",
    members: [
      {
        id: "halina", name: "Halina", age: 71, gen: 1, role: "Retired, state and work pension", speaksPolish: true,
        cash: {
          balance: 730,
          income: [
            { kind: "monthly", day: 1, amount: 425, label: "Work pension" },
            { kind: "monthly", day: 9, amount: 960, label: "State Pension" },
          ],
          bills: [
            { day: 2, amount: 160, label: "Council tax" },
            { day: 12, amount: 140, label: "Energy" },
            { day: 15, amount: 38, label: "Phone and TV" },
            { day: 20, amount: 45, label: "Water" },
          ],
          dailySpend: 27, dailySd: 11, shockChance: 0.012, shockSize: 220,
        },
        reasons: [
          { feature: "Two guaranteed pensions", impact: -0.06 },
          { feature: "Savings buffer of £62k", impact: -0.05 },
          { feature: "Winter energy bills", impact: 0.02 },
          { feature: "Spending steady for 12 months", impact: -0.02 },
        ],
      },
      {
        id: "tomasz", name: "Tomasz", age: 46, gen: 2, role: "Warehouse supervisor, monthly salary",
        cash: {
          balance: 1630,
          income: [{ kind: "monthly", day: 28, amount: 2480, label: "Salary" }],
          bills: [
            { day: 1, amount: 1050, label: "Rent" },
            { day: 3, amount: 168, label: "Council tax" },
            { day: 8, amount: 182, label: "Car finance" },
            { day: 12, amount: 136, label: "Energy" },
            { day: 18, amount: 62, label: "Phone and broadband" },
          ],
          dailySpend: 19.5, dailySd: 16, shockChance: 0.03, shockSize: 240,
        },
        reasons: [
          { feature: "Rent rose £85 in September", impact: 0.06 },
          { feature: "Rent leaves 27 days before payday", impact: 0.04 },
          { feature: "Grocery spend up 12% on last year", impact: 0.03 },
          { feature: "Same salary every month", impact: -0.05 },
          { feature: "No missed payments in 12 months", impact: -0.03 },
        ],
      },
      {
        id: "zofia", name: "Zofia", age: 22, gen: 3, role: "Junior designer, saving for a first home",
        cash: {
          balance: 840,
          income: [{ kind: "monthly", day: 25, amount: 1940, label: "Salary" }],
          bills: [
            { day: 1, amount: 720, label: "Room rent" },
            { day: 26, amount: 200, label: "Transfer to savings" },
            { day: 5, amount: 48, label: "Travel pass" },
            { day: 14, amount: 28, label: "Phone" },
            { day: 22, amount: 15, label: "Subscriptions" },
          ],
          dailySpend: 22.5, dailySd: 12, shockChance: 0.01, shockSize: 160,
        },
        reasons: [
          { feature: "Saves £200 a month", impact: -0.04 },
          { feature: "Payday close to rent day", impact: -0.03 },
          { feature: "Buy now, pay later used twice", impact: 0.02 },
          { feature: "Short credit history", impact: 0.01 },
        ],
      },
    ],
    tm: {
      receiverId: "zofia", giverId: "halina",
      region: "West Midlands", depositToday: 21300, depositPct: 10, houseGrowth: 0.03,
      targetYears: 6,
      receiverSavings: 3200, giverSavings: 62000, giverDrawPerYear: 2000, safetyFloor: 20000,
      inheritanceYears: 16, giftMax: 20000, monthlyMax: 800,
      defaults: { gift: 8000, timing: "now", monthly: 200, lisa: false },
    },
  },
  okafor: {
    id: "okafor",
    name: "Okafor Family",
    members: [
      {
        id: "grace", name: "Grace", age: 68, gen: 1, role: "Retired care worker, State Pension",
        cash: {
          balance: 1280,
          income: [
            { kind: "monthly", day: 6, amount: 1010, label: "State Pension" },
            { kind: "monthly", day: 20, amount: 140, label: "Pension Credit" },
          ],
          bills: [
            { day: 8, amount: 395, label: "Housing association rent" },
            { day: 4, amount: 92, label: "Council tax" },
            { day: 10, amount: 110, label: "Energy" },
            { day: 18, amount: 30, label: "Phone" },
          ],
          dailySpend: 14, dailySd: 7, shockChance: 0.012, shockSize: 120,
        },
        reasons: [
          { feature: "Small cash buffer", impact: 0.05 },
          { feature: "Winter energy bills", impact: 0.03 },
          { feature: "Guaranteed State Pension", impact: -0.05 },
          { feature: "Pension Credit claimed", impact: -0.03 },
        ],
      },
      {
        id: "daniel", name: "Daniel", age: 44, gen: 2, role: "Self-employed courier, income varies week to week",
        cash: {
          balance: 970,
          income: [{ kind: "weekly", weekday: 5, amount: 545, sd: 0.38, label: "Delivery app payout" }],
          bills: [
            { day: 1, amount: 930, label: "Rent" },
            { day: 3, amount: 128, label: "Council tax" },
            { day: 7, amount: 215, label: "Van lease" },
            { day: 11, amount: 112, label: "Energy" },
            { day: 15, amount: 96, label: "Van insurance" },
            { day: 21, amount: 75, label: "Credit card minimum" },
          ],
          dailySpend: 20, dailySd: 16, shockChance: 0.025, shockSize: 220,
        },
        reasons: [
          { feature: "Income varies 38% week to week", impact: 0.12 },
          { feature: "Cash buffer under two weeks of costs", impact: 0.08 },
          { feature: "Credit card balance growing", impact: 0.05 },
          { feature: "Van costs due mid-month", impact: 0.03 },
          { feature: "Works most days of the week", impact: -0.04 },
        ],
      },
      {
        id: "ada", name: "Ada", age: 19, gen: 3, role: "Apprentice electrician, lives at home",
        cash: {
          balance: 850,
          income: [{ kind: "monthly", day: 28, amount: 1150, label: "Apprentice wage" }],
          bills: [
            { day: 1, amount: 250, label: "Board to Dad" },
            { day: 4, amount: 95, label: "Bus and tools" },
            { day: 12, amount: 32, label: "Phone" },
            { day: 16, amount: 60, label: "Buy now, pay later" },
          ],
          dailySpend: 19.5, dailySd: 12, shockChance: 0.015, shockSize: 110,
        },
        reasons: [
          { feature: "Buy now, pay later plans", impact: 0.06 },
          { feature: "Small starting balance", impact: 0.04 },
          { feature: "Fixed apprentice wage", impact: -0.04 },
          { feature: "Low housing costs", impact: -0.03 },
        ],
      },
    ],
    tm: {
      receiverId: "ada", giverId: "grace",
      region: "North West", depositToday: 9600, depositPct: 5, houseGrowth: 0.03,
      targetYears: 10,
      receiverSavings: 300, giverSavings: 3800, giverDrawPerYear: 150, safetyFloor: 1500,
      inheritanceYears: 18, giftMax: 2000, monthlyMax: 400,
      defaults: { gift: 0, timing: "now", monthly: 60, lisa: true },
    },
  },
};

export function findMember(id: string): { family: Family; member: Member } | undefined {
  for (const family of Object.values(FAMILIES)) {
    const member = family.members.find((m) => m.id === id);
    if (member) return { family, member };
  }
  return undefined;
}

export function parentOf(family: Family) {
  return family.members.find((m) => m.gen === 2)!;
}
