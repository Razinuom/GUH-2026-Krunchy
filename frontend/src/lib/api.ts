/**
 * Calls the FastAPI backend from the build brief. If a call fails or takes longer than
 * about 2 seconds, it falls back to the local simulation so the demo keeps working offline.
 */
import type { FamilyId, Timing } from "./families";
import {
  simulateClaimCheck,
  simulateForecast,
  simulateTimeMachine,
  type ClaimResult,
  type ForecastResult,
  type TimeMachineResult,
} from "./simulate";

const API_URL = ((import.meta as unknown as { env?: Record<string, string> }).env?.VITE_API_URL ?? "http://localhost:8000").replace(/\/$/, "");
const TIMEOUT_MS = 2000;

/** Once one call fails, skip the network for a while so every page stays snappy. */
let offlineUntil = 0;

async function post<T>(path: string, body: unknown): Promise<T | null> {
  if (Date.now() < offlineUntil) return null;
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), TIMEOUT_MS);
  try {
    const res = await fetch(`${API_URL}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal: ctrl.signal,
    });
    if (!res.ok) throw new Error(`${res.status}`);
    return (await res.json()) as T;
  } catch {
    offlineUntil = Date.now() + 30_000;
    return null;
  } finally {
    clearTimeout(timer);
  }
}

export async function getForecast(memberId: string): Promise<ForecastResult> {
  const local = simulateForecast(memberId);
  const remote = await post<Partial<ForecastResult>>("/forecast", { member_id: memberId });
  if (!remote?.days?.length) return local;
  return { ...local, ...remote, reasons: remote.reasons ?? local.reasons, source: "api" };
}

export type TimeMachineRequest = { family_id: FamilyId; gift: number; timing: Timing; monthly_saving: number; lisa: boolean };

export async function getTimeMachine(req: TimeMachineRequest): Promise<TimeMachineResult> {
  const local = simulateTimeMachine(req);
  const remote = await post<Partial<TimeMachineResult>>("/timemachine", req);
  if (!remote?.genz_band?.length) return local;
  // the backend may not return the giver's band or the baseline; keep the local ones for those
  return { ...local, ...remote, assumptions: { ...local.assumptions, ...(remote.assumptions ?? {}) }, source: "api" };
}

export async function checkClaim(claim: string): Promise<ClaimResult> {
  const local = simulateClaimCheck(claim);
  const remote = await post<Partial<ClaimResult>>("/claimcheck", { claim });
  if (!remote?.rating) return local;
  const label =
    remote.label ?? (remote.rating === "red" ? "Warning Signs Found" : remote.rating === "green" ? "Accurate" : "Needs Evidence");
  return {
    rating: remote.rating,
    label,
    summary: remote.summary ?? local.summary,
    signals: remote.signals ?? [],
    sources: remote.sources ?? [],
    source: "api",
  };
}

export type AskResult = { answer: string; sources: { title: string; url: string }[]; source: "api" | "local" };

export async function ask(question: string, lang: "en" | "pl"): Promise<AskResult | null> {
  const remote = await post<{ answer?: string; sources?: { title: string; url: string }[] }>("/ask", { question, lang });
  if (!remote?.answer) return null;
  return { answer: remote.answer, sources: remote.sources ?? [], source: "api" };
}

export async function escalate(memberId: string, reason: string) {
  await post("/escalate", { member_id: memberId, reason });
}
