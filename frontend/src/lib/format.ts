/** Pinned demo date so "14%, Watch" stays the same on stage. Set VITE_DEMO_TODAY to override, or "live" for the real date. */
const pinned = ((import.meta as unknown as { env?: Record<string, string> }).env?.VITE_DEMO_TODAY) ?? "2026-11-07";
export const TODAY: Date = pinned === "live" ? startOfDay(new Date()) : new Date(`${pinned}T00:00:00`);

function startOfDay(d: Date) {
  return new Date(d.getFullYear(), d.getMonth(), d.getDate());
}

export function addDays(d: Date, n: number) {
  const x = new Date(d);
  x.setDate(x.getDate() + n);
  return x;
}

const gbp0 = new Intl.NumberFormat("en-GB", { style: "currency", currency: "GBP", maximumFractionDigits: 0 });

/** £1,234 */
export function money(n: number) {
  return gbp0.format(Math.round(n)).replace("-£", "−£");
}

/** £1.2k, £45k, £1.1m */
export function moneyShort(n: number) {
  const sign = n < 0 ? "−" : "";
  const a = Math.abs(n);
  if (a >= 1_000_000) return `${sign}£${(a / 1_000_000).toFixed(a >= 10_000_000 ? 0 : 1)}m`;
  if (a >= 10_000) return `${sign}£${Math.round(a / 1000)}k`;
  if (a >= 1000) return `${sign}£${(a / 1000).toFixed(1).replace(/\.0$/, "")}k`;
  return `${sign}£${Math.round(a)}`;
}

export function pct(p: number) {
  return `${Math.round(p * 100)}%`;
}

/** "24 Jan" */
export function shortDate(d: Date, lang: "en" | "pl" = "en") {
  return d.toLocaleDateString(lang === "pl" ? "pl-PL" : "en-GB", { day: "numeric", month: "short" });
}

export function longDate(d: Date, lang: "en" | "pl" = "en") {
  return d.toLocaleDateString(lang === "pl" ? "pl-PL" : "en-GB", { day: "numeric", month: "long" });
}
