import { ArrowRight } from "lucide-react";
import { GEN_LABEL, GEN_VAR, LANGUAGE_NAME, type Member } from "@/lib/families";
import { money, parseDate, shortDate } from "@/lib/format";
import type { ForecastResult } from "@/lib/types";
import { RiskPill } from "./RiskPill";

export function Avatar({ member, size = 64 }: { member: Member; size?: number }) {
  return (
    <span
      aria-hidden="true"
      className="grid shrink-0 place-items-center rounded-full font-display font-extrabold text-white"
      style={{ width: size, height: size, background: GEN_VAR[member.gen], fontSize: size * 0.42 }}
    >
      {member.name[0]}
    </span>
  );
}

export function PersonCard({ member, forecast, onSelect }: { member: Member; forecast?: ForecastResult | null; onSelect: () => void }) {
  const color = GEN_VAR[member.gen];
  const otherLanguages = member.languages.filter((l) => l !== "en").map((l) => LANGUAGE_NAME[l] ?? l);
  return (
    <button
      onClick={onSelect}
      className="group flex w-full flex-col items-start gap-3 px-8 py-2 text-left first:pl-0 last:pr-0 md720:px-0 md720:py-7"
    >
      <Avatar member={member} />
      <div>
        <p className="text-[.88rem] font-semibold" style={{ color }}>
          {GEN_LABEL[member.gen]}
        </p>
        <h2 className="font-display text-[1.6rem] font-extrabold leading-tight tracking-[-0.03em]">
          <span className="decoration-2 underline-offset-4 group-hover:underline" style={{ textDecorationColor: color }}>
            {member.name}, {member.age}
          </span>
        </h2>
        <p className="mt-0.5 text-muted">
          {member.role}
          {otherLanguages.length > 0 && ` · speaks ${otherLanguages.join(", ")}`}
        </p>
      </div>
      {forecast ? (
        <>
          <p>
            Balance today <strong className="num">{money(forecast.start_balance)}</strong>
            <br />
            Lowest point <strong className="num">{money(forecast.lowest_point.p50)}</strong> around {shortDate(parseDate(forecast.lowest_point.date))}
          </p>
          <RiskPill level={forecast.risk_band} p={forecast.overdraft_probability} long />
        </>
      ) : forecast === null ? (
        <p className="text-muted">Forecast unavailable (backend offline)</p>
      ) : (
        <p className="text-muted">Loading forecast…</p>
      )}
      <span className="mt-1 inline-flex items-center gap-1.5 font-semibold text-accent">
        See Next 90 Days <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-1" />
      </span>
    </button>
  );
}
