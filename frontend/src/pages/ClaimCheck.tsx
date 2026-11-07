import { useState } from "react";
import { Search } from "lucide-react";
import { Disclaimer, Page } from "@/components/layout/Page";
import { PageHeader } from "@/components/layout/PageHeader";
import { ErrorNote, SourceNote } from "@/components/DataState";
import { checkClaim } from "@/lib/api";
import type { ClaimRating, ClaimResult } from "@/lib/types";

const EXAMPLES = [
  "This stock is guaranteed to 10x by Christmas. DM me to join before it's too late!",
  "The Lifetime ISA adds a 25% bonus on up to £4,000 a year.",
  "You can give away £3,000 a year with no inheritance tax, and anything else is tax-free after 7 years.",
];

const RATING: Record<ClaimRating, { bg: string; fg: string }> = {
  red: { bg: "var(--critical-soft)", fg: "var(--critical)" },
  amber: { bg: "var(--warn-soft)", fg: "var(--warn)" },
  green: { bg: "var(--good-soft)", fg: "var(--good)" },
};

export default function ClaimCheck() {
  const [claim, setClaim] = useState("");
  const [result, setResult] = useState<ClaimResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function run(text = claim) {
    if (!text.trim()) return;
    setClaim(text);
    setBusy(true);
    setError(null);
    try {
      const r = await checkClaim(text);
      setResult(r);
      if (!r) setError("Claim Check needs the Heirloom backend, which is not reachable. The three example claims still work offline.");
    } catch (e) {
      setResult(null);
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Page>
      <PageHeader
        page="claims"
        label="Claim Check"
        title="Seen It on Social Media?"
        lead="Paste a money claim. We check it for the FCA's scam warning signs, look up any firm it names in the FCA's published warnings, and check its figures against GOV.UK, MoneyHelper and the FCA."
      />

      <form
        onSubmit={(e) => {
          e.preventDefault();
          run();
        }}
        className="flex items-center gap-2 rounded-full border border-line bg-surface py-2 pl-5 pr-2 focus-within:border-accent"
      >
        <Search className="h-5 w-5 shrink-0 text-muted" aria-hidden="true" />
        <label htmlFor="claim" className="sr-only">
          Money claim to check
        </label>
        <input
          id="claim"
          value={claim}
          onChange={(e) => setClaim(e.target.value)}
          placeholder="For example: this coin is guaranteed to double in a week"
          className="min-w-0 flex-1 bg-transparent py-2 text-[1.05rem] outline-none placeholder:text-muted focus-visible:outline-none"
        />
        <button
          type="submit"
          disabled={busy || !claim.trim()}
          className="rounded-full bg-accent px-6 py-2.5 font-semibold text-on-accent hover:opacity-90 disabled:opacity-50"
        >
          {busy ? "Checking…" : "Check"}
        </button>
      </form>

      <div className="mt-4 flex flex-wrap gap-2.5">
        {EXAMPLES.map((ex) => (
          <button key={ex} onClick={() => run(ex)} className="max-w-full rounded-full border border-line px-4 py-2 text-left text-[.86rem] hover:border-ink">
            {ex}
          </button>
        ))}
      </div>

      <div aria-live="polite">
        {busy && <p className="mt-8 text-muted">Searching GOV.UK, MoneyHelper and the FCA… a new claim can take up to 20 seconds.</p>}
        {error && <ErrorNote className="mt-8" message={error} />}
        {result && (
          <div className="mt-8 rounded-[22px] p-[clamp(20px,3.5vw,32px)]" style={{ background: RATING[result.rating].bg }}>
            <span
              className="inline-flex items-center gap-2 rounded-full bg-surface px-3 py-1 text-[.85rem] font-bold"
              style={{ color: RATING[result.rating].fg }}
            >
              <span className="h-2 w-2 rounded-full" style={{ background: RATING[result.rating].fg }} aria-hidden="true" />
              {result.label}
            </span>
            <p className="mt-4 max-w-[70ch] text-[1.05rem]">{result.summary}</p>
            {result.signals.length > 0 && (
              <>
                <h2 className="mt-6 font-display text-[1.1rem] font-bold">What We Found</h2>
                <ul className="mt-2 list-disc space-y-1 pl-5">
                  {result.signals.map((s) => (
                    <li key={s}>{s}</li>
                  ))}
                </ul>
              </>
            )}
            {result.evidence.length > 0 && (
              <>
                <h2 className="mt-6 font-display text-[1.1rem] font-bold">What Official Sources Say</h2>
                <ul className="mt-2 space-y-3">
                  {result.evidence.map((e) => (
                    <li key={e.url}>
                      <blockquote className="border-l-2 border-ink/30 pl-3 text-[.95rem]">&ldquo;{e.quote}&rdquo;</blockquote>
                      <a href={e.url} target="_blank" rel="noreferrer" className="mt-0.5 inline-block pl-3 text-[.82rem] font-medium">
                        {e.title}
                      </a>
                    </li>
                  ))}
                </ul>
              </>
            )}
            {result.sources.length > 0 && (
              <>
                <h2 className="mt-6 font-display text-[1.1rem] font-bold">Sources</h2>
                <ul className="mt-2 space-y-1">
                  {result.sources.map((s) => (
                    <li key={s.url}>
                      <a href={s.url} target="_blank" rel="noreferrer" className="font-medium">
                        {s.title}
                      </a>
                    </li>
                  ))}
                </ul>
              </>
            )}
            <p className="mt-6 text-[.76rem] text-muted">
              If you have already sent money, call your bank straight away (or call 159) and report it to Action Fraud.
            </p>
            <SourceNote
              className="mt-1"
              source={result.source}
              live={
                result.researcher === "firecrawl"
                  ? "Checked against GOV.UK, MoneyHelper and FCA pages found with a Firecrawl search (searches are cached for up to a week)."
                  : result.researcher === "saved"
                    ? "Checked against saved GOV.UK, FCA and Citizens Advice pages (live search unavailable)."
                    : "Rated on the FCA's scam warning signs."
              }
            />
          </div>
        )}
      </div>
      <Disclaimer className="mt-8" />
    </Page>
  );
}
