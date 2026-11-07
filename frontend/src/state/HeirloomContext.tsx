import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { FAMILIES, parentOf, type Family, type FamilyId, type Member, type Timing } from "@/lib/families";

export type TMState = { gift: number; timing: Timing; monthly: number; lisa: boolean };

type HeirloomState = {
  family: FamilyId;
  memberId: string;
  night: boolean;
  large: boolean;
  tm: TMState;
  lang: "en" | "pl";
};

type HeirloomContextValue = HeirloomState & {
  familyData: Family;
  member: Member;
  setFamily: (f: FamilyId) => void;
  setMemberId: (id: string) => void;
  toggleNight: () => void;
  toggleLarge: () => void;
  setTm: (patch: Partial<TMState>) => void;
  setLang: (l: "en" | "pl") => void;
  helpOpen: boolean;
  openHelp: () => void;
  setHelpOpen: (open: boolean) => void;
};

const Ctx = createContext<HeirloomContextValue | null>(null);

function readTheme() {
  try {
    return localStorage.getItem("heirloom-theme") === "night";
  } catch {
    return false;
  }
}

export function HeirloomProvider({ children }: { children: ReactNode }) {
  const [family, setFamilyState] = useState<FamilyId>("nowak");
  const [memberId, setMemberIdState] = useState(parentOf(FAMILIES.nowak).id);
  const [night, setNight] = useState(readTheme);
  const [large, setLarge] = useState(false);
  const [tm, setTmState] = useState<TMState>(FAMILIES.nowak.tm.defaults);
  const [lang, setLang] = useState<"en" | "pl">("en");
  const [helpOpen, setHelpOpen] = useState(false);

  useEffect(() => {
    document.documentElement.classList.toggle("night", night);
    try {
      localStorage.setItem("heirloom-theme", night ? "night" : "day");
    } catch {
      /* storage may be blocked */
    }
  }, [night]);

  useEffect(() => {
    document.documentElement.classList.toggle("large", large);
  }, [large]);

  const setFamily = useCallback((f: FamilyId) => {
    setFamilyState(f);
    setMemberIdState(parentOf(FAMILIES[f]).id);
    setTmState(FAMILIES[f].tm.defaults);
    setLang("en");
  }, []);

  const setMemberId = useCallback((id: string) => {
    setMemberIdState(id);
    const m = Object.values(FAMILIES).flatMap((f) => f.members).find((x) => x.id === id);
    if (!m?.speaksPolish) setLang("en");
  }, []);

  const value = useMemo<HeirloomContextValue>(() => {
    const familyData = FAMILIES[family];
    const member = familyData.members.find((m) => m.id === memberId) ?? parentOf(familyData);
    return {
      family, memberId: member.id, night, large, tm, lang, familyData, member,
      setFamily, setMemberId,
      toggleNight: () => setNight((n) => !n),
      toggleLarge: () => setLarge((l) => !l),
      setTm: (patch) => setTmState((s) => ({ ...s, ...patch })),
      setLang,
      helpOpen, setHelpOpen,
      openHelp: () => setHelpOpen(true),
    };
  }, [family, memberId, night, large, tm, lang, helpOpen, setFamily, setMemberId]);

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useHeirloom() {
  const v = useContext(Ctx);
  if (!v) throw new Error("useHeirloom must be used inside HeirloomProvider");
  return v;
}
