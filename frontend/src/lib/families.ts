/**
 * Family and member types used across the UI. All data comes from the backend (GET /families);
 * nothing here is invented. See src/lib/api.ts.
 */
import type { ApiFamily, ApiMember, TimeMachineControls } from "./types";

export type Gen = 1 | 2 | 3;
export type FamilyId = string;
export type Timing = "now" | "10y" | "inheritance";

export type Member = {
  id: string;
  /** first name, used in headings ("Next 90 Days for Tomasz") */
  name: string;
  fullName: string;
  family: FamilyId;
  age: number;
  gen: Gen;
  role: string;
  languages: string[];
  speaksPolish: boolean;
};

export type Family = {
  id: FamilyId;
  name: string;
  members: Member[];
  tm: {
    giverId: string;
    receiverId: string;
    region: string;
    depositPct: number;
    targetYear: number;
    inheritanceYears: number;
    controls: TimeMachineControls;
  };
};

export const GEN_LABEL: Record<Gen, string> = { 1: "Grandparent", 2: "Parent", 3: "Young Adult" };
export const GEN_VAR: Record<Gen, string> = { 1: "var(--gen1)", 2: "var(--gen2)", 3: "var(--gen3)" };

export const LANGUAGE_NAME: Record<string, string> = { en: "English", pl: "Polish", ms: "Malay", zh: "Mandarin" };

function toMember(m: ApiMember): Member {
  return {
    id: m.id,
    name: m.first_name,
    fullName: m.name,
    family: m.family,
    age: m.age,
    gen: m.generation,
    role: m.role,
    languages: m.languages,
    speaksPolish: m.languages.includes("pl"),
  };
}

export function toFamily(f: ApiFamily): Family {
  return {
    id: f.id,
    name: f.name,
    members: f.members.map(toMember),
    tm: {
      giverId: f.time_machine.grandparent,
      receiverId: f.time_machine.young_adult,
      region: f.time_machine.region,
      depositPct: f.time_machine.deposit_pct,
      targetYear: f.time_machine.target_year,
      inheritanceYears: f.time_machine.inheritance_expected_years,
      controls: f.time_machine.controls,
    },
  };
}

export function parentOf(family: Family) {
  return family.members.find((m) => m.gen === 2) ?? family.members[0];
}
