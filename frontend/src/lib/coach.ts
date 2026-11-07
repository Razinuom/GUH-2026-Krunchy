/**
 * Scripted Voice Coach questions. Each one names the backend tool the ElevenLabs agent would call,
 * and builds its answer from that tool's result, so the numbers match the rest of the dashboard.
 */
import { FAMILIES, type FamilyId, type Member } from "./families";
import { addDays, longDate, money, pct, TODAY } from "./format";
import { riskLevel, simulateForecast, simulateTimeMachine, SOURCES } from "./simulate";
import type { TMState } from "@/state/HeirloomContext";

type Lang = "en" | "pl";
type Source = { title: string; url: string };

export type CoachAnswer = {
  text: Record<Lang, string>;
  sources: Source[];
  /** a Time Machine scenario to show on the dashboard */
  tm?: Partial<TMState>;
};

export type CoachQuestion = {
  id: string;
  q: Record<Lang, string>;
  tool: { path: "/forecast" | "/timemachine" | "/ask"; body: Record<string, unknown> };
  answer: () => CoachAnswer;
};

const NOT_ADVICE = {
  en: "This is guidance, not regulated financial advice.",
  pl: "To wskazówki i scenariusze, a nie regulowana porada finansowa.",
};

function forecastQuestion(m: Member): CoachQuestion {
  return {
    id: "forecast",
    q: {
      en: "Will my money last until the end of the month?",
      pl: "Czy moje pieniądze wystarczą do końca miesiąca?",
    },
    tool: { path: "/forecast", body: { member_id: m.id } },
    answer: () => {
      const f = simulateForecast(m.id);
      const level = riskLevel(f.overdraft_probability);
      const low = money(f.lowest_point.p50);
      const date = addDays(TODAY, f.lowest_point.day);
      const p = pct(f.overdraft_probability);
      const en = {
        low: `Yes, it looks steady. Your lowest point is likely to be about ${low} around ${longDate(date)}, and there is only a ${p} chance of dropping below zero in the next 90 days.`,
        watch: `Mostly, but it is tight. Your balance is likely to dip to about ${low} around ${longDate(date)}, and there is a ${p} chance of going below zero in the next 90 days. Moving one bill until after payday would help.`,
        high: `It will be difficult. There is a ${p} chance of going below zero in the next 90 days, with the lowest point around ${longDate(date)}. Free debt advice from StepChange or Citizens Advice could help now, before it gets harder. I can connect you to a person if you like.`,
      }[level];
      const pl = {
        low: `Tak, wygląda to stabilnie. Najniższy stan konta to prawdopodobnie około ${low} w okolicach ${longDate(date, "pl")}, a szansa na spadek poniżej zera w ciągu 90 dni wynosi tylko ${p}.`,
        watch: `Raczej tak, ale będzie ciasno. Saldo może spaść do około ${low} w okolicach ${longDate(date, "pl")}, a szansa na spadek poniżej zera w ciągu 90 dni wynosi ${p}. Przesunięcie jednego rachunku na dzień po wypłacie pomoże.`,
        high: `Będzie trudno. Szansa na spadek poniżej zera w ciągu 90 dni wynosi ${p}, a najtrudniejszy moment przypada około ${longDate(date, "pl")}. Bezpłatna pomoc z StepChange lub Citizens Advice może pomóc już teraz. Mogę połączyć Panią z doradcą.`,
      }[level];
      return { text: { en: `${en} ${NOT_ADVICE.en}`, pl: `${pl} ${NOT_ADVICE.pl}` }, sources: [] };
    },
  };
}

function giftQuestion(family: FamilyId, gift: number, tm: TMState): CoachQuestion {
  const fam = FAMILIES[family];
  const cfg = fam.tm;
  const receiver = fam.members.find((m) => m.id === cfg.receiverId)!;
  const req = { family_id: family, gift, timing: "now" as const, monthly_saving: tm.monthly, lisa: tm.lisa };
  return {
    id: "gift",
    q: {
      en: `If I give ${receiver.name} ${money(gift)} now, will I still be safe?`,
      pl: `Jeśli dam ${receiver.name === "Zofia" ? "Zofii" : receiver.name} ${gift} funtów teraz, czy nadal będę bezpieczna?`,
    },
    tool: { path: "/timemachine", body: req },
    answer: () => {
      const r = simulateTimeMachine(req);
      const floor = money(cfg.safetyFloor);
      return {
        text: {
          en: `If you give ${receiver.name} ${money(gift)} now, her chance of saving a home deposit by ${r.target_year} rises to ${pct(r.p_deposit_by_target)}, up from ${pct(r.baseline.p_deposit_by_target)} with no gift. Your savings stay above your ${floor} safety floor in ${pct(r.p_parent_floor_safe)} of scenarios. I have put this on the Time Machine so the family can see it. ${NOT_ADVICE.en}`,
          pl: `Jeśli da Pani ${receiver.name === "Zofia" ? "Zofii" : receiver.name} ${money(gift)} teraz, jej szansa na zebranie wkładu własnego na mieszkanie do ${r.target_year} roku wzrośnie do ${pct(r.p_deposit_by_target)} (bez prezentu: ${pct(r.baseline.p_deposit_by_target)}). Pani oszczędności pozostaną powyżej progu bezpieczeństwa ${floor} w ${pct(r.p_parent_floor_safe)} scenariuszy. Pokazałam to w Wehikule Czasu, żeby rodzina mogła to zobaczyć. ${NOT_ADVICE.pl}`,
        },
        sources: [SOURCES.iht],
        tm: { gift, timing: "now" },
      };
    },
  };
}

function ask(id: string, en: string, pl: string, answerEn: string, answerPl: string, sources: Source[]): CoachQuestion {
  return {
    id,
    q: { en, pl },
    tool: { path: "/ask", body: { question: en } },
    answer: () => ({ text: { en: `${answerEn} ${NOT_ADVICE.en}`, pl: `${answerPl} ${NOT_ADVICE.pl}` }, sources }),
  };
}

export function questionsFor(member: Member, family: FamilyId, tm: TMState): CoachQuestion[] {
  const f = forecastQuestion(member);
  switch (member.id) {
    case "halina":
      return [
        giftQuestion(family, 8000, tm),
        ask(
          "iht",
          "Is there any tax if I give money to my granddaughter?",
          "Czy muszę płacić podatek, jeśli dam pieniądze wnuczce?",
          "Usually not. Everyone can give away £3,000 a year free of Inheritance Tax, and you can carry one unused year forward. Bigger gifts are normally tax-free if you live for seven years after giving them. It helps to write down the date and amount of each gift.",
          "Zwykle nie. Każdy może co roku podarować do £3000 bez podatku spadkowego, a niewykorzystany limit można przenieść o jeden rok. Większe prezenty są zwykle wolne od podatku, jeśli przeżyje Pani siedem lat od ich przekazania. Warto zapisać datę i kwotę każdego prezentu.",
          [SOURCES.iht],
        ),
        f,
      ];
    case "tomasz":
      return [
        f,
        ask(
          "lower-risk",
          "How can I lower my overdraft risk?",
          "",
          "Your rent leaves 27 days before payday, which is why the end of the month is tight. Asking your landlord to move rent to the 29th, or keeping about £150 back as a buffer, would bring your risk down to low. Check whether you could switch the car finance date too.",
          "",
          [SOURCES.debt],
        ),
        ask(
          "help-zofia",
          "How can I help Zofia buy a home?",
          "",
          "A Lifetime ISA is worth a look for Zofia. The government adds 25% to what she pays in, up to £1,000 a year, as long as she uses it for a first home under £450,000. Family can pay into it for her. If she takes money out for anything else, there is a 25% charge.",
          "",
          [SOURCES.lisa],
        ),
      ];
    case "zofia":
    case "ada":
      return [
        ask(
          "lisa",
          "How does the Lifetime ISA bonus work?",
          "",
          "You can open one between 18 and 39 and pay in up to £4,000 a year. The government adds a 25% bonus, so up to £1,000 a year free. You can use it for a first home costing up to £450,000, or from age 60. Taking money out for anything else costs 25%.",
          "",
          [SOURCES.lisa, SOURCES.isa],
        ),
        f,
        {
          id: "when-deposit",
          q: { en: "When could I afford a home deposit?", pl: "" },
          tool: { path: "/timemachine", body: { family_id: family, gift: tm.gift, timing: tm.timing, monthly_saving: tm.monthly } },
          answer: () => {
            const r = simulateTimeMachine({ family_id: family, gift: tm.gift, timing: tm.timing, monthly_saving: tm.monthly, lisa: tm.lisa });
            const idx = r.genz_band.findIndex((b, i) => b.p50 >= r.deposit_goal[i]);
            const year = idx > 0 ? r.years[idx] : null;
            const en = year
              ? `Saving ${money(tm.monthly)} a month${tm.lisa ? " in a Lifetime ISA" : ""}, your most likely path reaches a ${money(r.deposit_goal[idx])} deposit around ${year}. By ${r.target_year} the chance is ${pct(r.p_deposit_by_target)}.`
              : `At ${money(tm.monthly)} a month, the deposit stays out of reach in most scenarios. Try the Time Machine with a little more each month${tm.lisa ? "" : " or a Lifetime ISA"}.`;
            return { text: { en: `${en} ${NOT_ADVICE.en}`, pl: "" }, sources: [SOURCES.lisa] };
          },
        },
      ];
    case "grace":
      return [
        ask(
          "pension-credit",
          "Am I getting all the money I am entitled to?",
          "",
          "You already get Pension Credit, which is worth keeping because it also unlocks help with council tax, heating and a free TV licence if you are over 75. It is worth checking your State Pension forecast on GOV.UK and asking the council about a Council Tax Reduction.",
          "",
          [SOURCES.pensionCredit],
        ),
        f,
        ask(
          "help-ada",
          "Can I help Ada even with small amounts?",
          "",
          "Yes. Even £10 a month into Ada's Lifetime ISA gets a 25% bonus from the government, so £120 a year becomes £150. Small, regular amounts matter more than one big gift, and you keep your own safety net.",
          "",
          [SOURCES.lisa],
        ),
      ];
    case "daniel":
      return [
        f,
        ask(
          "variable-income",
          "My income changes every week. What can I do?",
          "",
          "With income that goes up and down, the trick is to budget on your quietest week, not your average one. In good weeks, put the extra into a separate pot for rent and van costs. If your credit card is growing, StepChange can help for free and can ask lenders to freeze interest.",
          "",
          [SOURCES.debt],
        ),
        ask(
          "debt-help",
          "Where can I get free help with debt?",
          "",
          "StepChange, Citizens Advice and the National Debtline all give free, confidential debt advice. They can set up a plan with your lenders, and you may be able to get a Breathing Space, which pauses interest and charges for 60 days. Be careful of companies that charge fees for this.",
          "",
          [SOURCES.debt],
        ),
      ];
    default:
      return [f];
  }
}
