/** Response shapes from the Heirloom FastAPI backend (backend/heirloom/schemas.py, backend/hardship). */

export type Source = { title: string; url: string };
/** where a result came from: the live API, or the saved snapshot of real API output (offline mode) */
export type DataSource = "live" | "snapshot";
export type RiskLevel = "low" | "watch" | "high";

export type Band = { p10: number; p25?: number | null; p50: number; p75?: number | null; p90: number };

/* ---------- /families ---------- */
export type ApiMember = {
  id: string;
  name: string;
  first_name: string;
  family: string;
  age: number;
  role: string;
  generation: 1 | 2 | 3;
  languages: string[];
};

export type TimeMachineControls = {
  gift: number;
  timing: "now" | "10y" | "inheritance";
  monthly_saving: number;
  lisa: boolean;
  gift_max: number;
  monthly_max: number;
};

export type ApiFamily = {
  id: string;
  name: string;
  members: ApiMember[];
  time_machine: {
    grandparent: string;
    young_adult: string;
    region: string;
    deposit_pct: number;
    target_year: number;
    inheritance_expected_years: number;
    controls: TimeMachineControls;
  };
};

/* ---------- /forecast ---------- */
export type ForecastDay = Band & { d: number; date: string };
export type ForecastReason = { feature: string; impact: number; detail: string; kind: string };

export type ForecastResult = {
  member_id: string;
  start_date: string;
  start_balance: number;
  days: ForecastDay[];
  overdraft_probability: number;
  overdraft_probability_by_horizon: Record<string, number>;
  risk_band: RiskLevel;
  lowest_point: { day: number; date: string; p10: number; p50: number; p90: number };
  reasons: ForecastReason[];
  upcoming: { date: string; merchant: string; amount: number; category: string }[];
  assumptions: { method: string; paths?: number; disclaimer: string } & Record<string, unknown>;
  sources: Source[];
  source: DataSource;
};

/* ---------- /hardship ---------- */
export type HardshipReason = {
  feature: string;
  key: string;
  impact: number;
  direction: "raises risk" | "lowers risk";
  detail: string;
  value: number;
  tip?: string;
  source?: string;
};

export type HelpResource = { id?: string; name: string; phone?: string; url?: string; note?: string; what?: string };

export type HardshipResult = {
  member_id: string;
  balance: number;
  risk_score: number;
  band: RiskLevel;
  overdraft_probability: number;
  baseline_probability: number;
  reasons: HardshipReason[];
  guardian: { escalate: boolean; signals: string[]; message: string; resources: HelpResource[] };
  model: { type: string; test_auc_90d?: number };
  disclaimer: string;
  source: DataSource;
};

/* ---------- /timemachine ---------- */
export type TimeMachineRequest = {
  family_id: string;
  gift: number;
  timing: "now" | "10y" | "inheritance";
  monthly_saving: number;
  lisa: boolean;
};

export type TimeMachineResult = {
  family_id: string;
  grandparent: { id: string; name: string; first_name: string; age: number };
  young_adult: { id: string; name: string; first_name: string; age: number };
  gift: number;
  timing: "now" | "10y" | "inheritance";
  monthly_saving: number;
  lisa: boolean;
  years: number[];
  genz_band: Band[];
  giver_band: Band[];
  deposit_goal: number[];
  target_year: number;
  p_deposit_by_target: number;
  p_deposit_within_horizon: number;
  p_parent_floor_safe: number;
  baseline: { p_deposit_by_target: number; p_parent_floor_safe: number } | null;
  deposit_target: { region: string; pct: number; amount: number; ftb_price: number; as_of: string };
  safety_floor: number;
  inheritance_expected_years: number;
  starting_savings: { grandparent: number; young_adult: number };
  assumptions: Record<string, unknown>;
  sources: Source[];
  source: DataSource;
};

/* ---------- /claimcheck, /escalate, /voice ---------- */
export type ClaimRating = "red" | "amber" | "green";
export type ClaimEvidence = { title: string; url: string; quote: string; figures: string[] };
export type ClaimFirm = { name: string; checked: boolean; warning: boolean; registered?: boolean; url: string; title?: string };

export type ClaimResult = {
  rating: ClaimRating;
  label: string;
  summary: string;
  signals: string[];
  sources: Source[];
  /** sentences quoted from GOV.UK / MoneyHelper / FCA pages */
  evidence: ClaimEvidence[];
  figures: { found: string[]; missing: string[] };
  firms: ClaimFirm[];
  /** firecrawl = live search of official sites; saved = saved official pages; rules = warning signs only */
  researcher: "firecrawl" | "saved" | "rules";
  source: DataSource;
};

export type VoiceStatus = { configured: boolean; api_key_set: boolean; agent_id_set: boolean };
export type VoiceSession = {
  signed_url: string;
  agent_id: string;
  dynamic_variables: { member_id: string; member_name: string; family_id: string };
};

/** Server-Sent Event from GET /voice/events */
export type VoiceEvent = {
  type: "forecast" | "what_if" | "rules_lookup" | "escalation" | "session_started" | "call_ended";
  family_id: string | null;
  ts: number;
  data: Record<string, unknown>;
};
