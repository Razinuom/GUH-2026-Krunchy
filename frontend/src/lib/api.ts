/**
 * Every number on the site comes from the Heirloom FastAPI backend.
 *
 * If the backend can't be reached, pages fall back to src/data/snapshot.json: real backend output saved
 * by `python scripts/export_frontend_snapshot.py`, and labelled "offline snapshot" on screen.
 * Nothing is simulated or invented in the browser.
 */
import rawSnapshot from "@/data/snapshot.json";
import type {
  ApiFamily,
  ClaimResult,
  ForecastResult,
  HardshipResult,
  HelpResource,
  Source,
  TimeMachineRequest,
  TimeMachineResult,
  VoiceSession,
  VoiceStatus,
} from "./types";

export const API_URL = ((import.meta as unknown as { env?: Record<string, string> }).env?.VITE_API_URL ?? "http://localhost:8000").replace(
  /\/$/,
  "",
);
const TIMEOUT_MS = 8000;

type Snapshot = {
  generated_at: string;
  as_of: string;
  families: ApiFamily[];
  forecasts: Record<string, Omit<ForecastResult, "source">>;
  hardship: Record<string, Omit<HardshipResult, "source">>;
  timemachine: Record<string, Omit<TimeMachineResult, "source">>;
  claims: Record<string, Omit<ClaimResult, "source">>;
  help: Record<string, HelpResource[]>;
};
export const snapshot = rawSnapshot as unknown as Snapshot;

/** After a failed call, skip the network for a short while so every page stays snappy offline. */
let offlineUntil = 0;

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status?: number,
  ) {
    super(message);
  }
}

async function request<T>(method: "GET" | "POST", path: string, body?: unknown, alwaysTry = false, timeoutMs = TIMEOUT_MS): Promise<T> {
  if (!alwaysTry && Date.now() < offlineUntil) throw new ApiError("offline");
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), timeoutMs);
  try {
    const res = await fetch(`${API_URL}${path}`, {
      method,
      headers: body === undefined ? undefined : { "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: ctrl.signal,
    });
    if (!res.ok) {
      const detail = await res.json().then((j) => j?.detail).catch(() => undefined);
      throw new ApiError(typeof detail === "string" ? detail : `HTTP ${res.status}`, res.status);
    }
    offlineUntil = 0; // the backend answered, so stop skipping the network
    return (await res.json()) as T;
  } catch (err) {
    // HTTP errors mean the backend is up; only network failures switch to offline mode
    if (!(err instanceof ApiError)) {
      offlineUntil = Date.now() + 15_000;
      throw new ApiError("offline");
    }
    throw err;
  } finally {
    clearTimeout(timer);
  }
}

const isOffline = (err: unknown) => err instanceof ApiError && err.message === "offline";

/** live result, or the snapshot entry when the backend is unreachable (null if there is none) */
async function withSnapshot<T>(call: () => Promise<T>, saved: T | undefined): Promise<(T & { source: "live" | "snapshot" }) | null> {
  try {
    return { ...(await call()), source: "live" };
  } catch (err) {
    if (isOffline(err) && saved) return { ...saved, source: "snapshot" };
    if (isOffline(err)) return null;
    throw err;
  }
}

/* ---------- data endpoints ---------- */

export async function getFamilies(): Promise<{ families: ApiFamily[]; source: "live" | "snapshot" }> {
  try {
    return { families: await request<ApiFamily[]>("GET", "/families"), source: "live" };
  } catch (err) {
    if (isOffline(err)) return { families: snapshot.families, source: "snapshot" };
    throw err;
  }
}

export function getForecast(memberId: string) {
  return withSnapshot(() => request<Omit<ForecastResult, "source">>("POST", "/forecast", { member_id: memberId }), snapshot.forecasts[memberId]);
}

export function getHardship(memberId: string) {
  return withSnapshot(() => request<Omit<HardshipResult, "source">>("POST", "/hardship", { member_id: memberId }), snapshot.hardship[memberId]);
}

/** Must match tm_key() in scripts/export_frontend_snapshot.py */
export function timeMachineKey(r: TimeMachineRequest) {
  return `${r.family_id}|${r.gift}|${r.timing}|${r.monthly_saving}|${r.lisa}`;
}

export function getTimeMachine(req: TimeMachineRequest) {
  return withSnapshot(() => request<Omit<TimeMachineResult, "source">>("POST", "/timemachine", req), snapshot.timemachine[timeMachineKey(req)]);
}

/** A first-time live search of GOV.UK, MoneyHelper and the FCA (Firecrawl) can take 15-20 seconds; repeats are cached. */
export function checkClaim(claim: string) {
  return withSnapshot(
    () => request<Omit<ClaimResult, "source">>("POST", "/claimcheck", { claim }, false, 60_000),
    snapshot.claims[claim],
  );
}

export async function ask(question: string, lang = "en") {
  return request<{ answer: string; sources: Source[]; refused: boolean }>("POST", "/ask", { question, lang });
}

/** Logs a "talk to a person" handoff and returns free help lines (falls back to the saved list offline). */
export async function escalate(memberId: string, reason: "debt" | "scam" | "advice" | "distress" | "other" = "other") {
  try {
    const r = await request<{ contacts: HelpResource[] }>("POST", "/escalate", { member_id: memberId, reason });
    return { contacts: r.contacts, source: "live" as const };
  } catch (err) {
    if (isOffline(err)) return { contacts: snapshot.help[reason] ?? snapshot.help.other, source: "snapshot" as const };
    throw err;
  }
}

/* ---------- voice ---------- */

/** always hits the network, so the Voice Coach page notices as soon as the backend comes up */
export function voiceStatus() {
  return request<VoiceStatus>("GET", "/voice/status", undefined, true);
}

export function voiceSession(memberId: string) {
  return request<VoiceSession>("GET", `/voice/session?member_id=${encodeURIComponent(memberId)}`);
}

export function voiceEventsUrl(familyId: string) {
  return `${API_URL}/voice/events?family_id=${encodeURIComponent(familyId)}`;
}
