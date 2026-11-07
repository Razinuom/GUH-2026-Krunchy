import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { getFamilies, snapshot } from "@/lib/api";
import { parentOf, toFamily, type Family, type FamilyId, type Member, type Timing } from "@/lib/families";
import type { DataSource } from "@/lib/types";

export type TMState = { gift: number; timing: Timing; monthly: number; lisa: boolean };

type HeirloomContextValue = {
  families: Family[];
  familiesSource: DataSource;
  family: FamilyId;
  familyData: Family;
  memberId: string;
  member: Member;
  night: boolean;
  large: boolean;
  tm: TMState;
  setFamily: (f: FamilyId) => void;
  setMemberId: (id: string) => void;
  toggleNight: () => void;
  toggleLarge: () => void;
  setTm: (patch: Partial<TMState>) => void;
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

function tmDefaults(f: Family): TMState {
  const c = f.tm.controls;
  return { gift: c.gift, timing: c.timing, monthly: c.monthly_saving, lisa: c.lisa };
}

// The saved snapshot (real backend output) gives the first render something real to show;
// it is replaced by GET /families as soon as the backend answers.
const INITIAL = snapshot.families.map(toFamily);

export function HeirloomProvider({ children }: { children: ReactNode }) {
  const [families, setFamilies] = useState<Family[]>(INITIAL);
  const [familiesSource, setFamiliesSource] = useState<DataSource>("snapshot");
  const [family, setFamilyState] = useState<FamilyId>(INITIAL[0].id);
  const [memberId, setMemberIdState] = useState(parentOf(INITIAL[0]).id);
  const [night, setNight] = useState(readTheme);
  const [large, setLarge] = useState(false);
  const [tm, setTmState] = useState<TMState>(tmDefaults(INITIAL[0]));
  const [helpOpen, setHelpOpen] = useState(false);

  useEffect(() => {
    getFamilies()
      .then((r) => {
        setFamilies(r.families.map(toFamily));
        setFamiliesSource(r.source);
      })
      .catch(() => setFamiliesSource("snapshot"));
  }, []);

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

  const byId = useCallback((id: FamilyId) => families.find((f) => f.id === id) ?? families[0], [families]);

  const setFamily = useCallback(
    (f: FamilyId) => {
      const fam = byId(f);
      setFamilyState(fam.id);
      setMemberIdState(parentOf(fam).id);
      setTmState(tmDefaults(fam));
    },
    [byId],
  );

  const setMemberId = useCallback(
    (id: string) => {
      const fam = families.find((f) => f.members.some((m) => m.id === id));
      if (fam && fam.id !== family) {
        setFamilyState(fam.id);
        setTmState(tmDefaults(fam));
      }
      setMemberIdState(id);
    },
    [families, family],
  );

  const value = useMemo<HeirloomContextValue>(() => {
    const familyData = byId(family);
    const member = familyData.members.find((m) => m.id === memberId) ?? parentOf(familyData);
    return {
      families, familiesSource, family: familyData.id, familyData, memberId: member.id, member, night, large, tm,
      setFamily, setMemberId,
      toggleNight: () => setNight((n) => !n),
      toggleLarge: () => setLarge((l) => !l),
      setTm: (patch) => setTmState((s) => ({ ...s, ...patch })),
      helpOpen, setHelpOpen,
      openHelp: () => setHelpOpen(true),
    };
  }, [families, familiesSource, family, memberId, night, large, tm, helpOpen, byId, setFamily, setMemberId]);

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useHeirloom() {
  const v = useContext(Ctx);
  if (!v) throw new Error("useHeirloom must be used inside HeirloomProvider");
  return v;
}
