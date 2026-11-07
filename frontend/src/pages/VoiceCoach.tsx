import { Conversation } from "@elevenlabs/client";
import { Mic, PhoneOff } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { RiskPill } from "@/components/family/RiskPill";
import { PersonPicker } from "@/components/family/PersonPicker";
import { Disclaimer, Page } from "@/components/layout/Page";
import { PageHeader } from "@/components/layout/PageHeader";
import { voiceEventsUrl, voiceSession, voiceStatus } from "@/lib/api";
import { LANGUAGE_NAME } from "@/lib/families";
import { money, parseDate, pct, shortDate } from "@/lib/format";
import type { ForecastResult, HelpResource, Source, VoiceEvent } from "@/lib/types";
import { cn } from "@/lib/utils";
import { useHeirloom } from "@/state/HeirloomContext";

type Line = { id: string; role: "user" | "agent" | "system"; text: string };
type CallState = "idle" | "connecting" | "listening" | "speaking";
type Availability = "checking" | "ready" | "not-configured" | "offline";

/** Things to try saying, in the agent's four languages (prompts only; answers come from the backend). */
const TRY: Record<string, string[]> = {
  en: ["Will my money last until the end of January?", "Can I give Zofia £300 for Christmas?", "How does the Lifetime ISA bonus work?"],
  pl: ["Czy starczy mi pieniędzy do końca stycznia?", "Czy mogę dać Zofii 300 funtów na święta?"],
  ms: ["Adakah wang saya cukup sampai hujung Januari?"],
  zh: ["我的钱够用到一月底吗？"],
};

const EVENT_TYPES: VoiceEvent["type"][] = ["forecast", "what_if", "rules_lookup", "escalation", "call_ended"];

function EventCard({ ev }: { ev: VoiceEvent }) {
  const { setMemberId } = useHeirloom();
  const d = ev.data as Record<string, unknown>;
  const lang = d.spoken_language as { name?: string } | undefined;
  const when = new Date(ev.ts * 1000).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
  const head = (title: string) => (
    <p className="flex justify-between gap-3 text-[.78rem] text-muted">
      <span className="font-semibold text-ink">
        {title}
        {lang?.name && lang.name !== "English" ? ` · asked in ${lang.name}` : ""}
      </span>
      <span className="num">{when}</span>
    </p>
  );

  if (ev.type === "forecast") {
    const f = d.forecast as ForecastResult;
    return (
      <li className="rounded-2xl border border-line p-4">
        {head(`Forecast for ${String(d.member_name)}`)}
        <div className="mt-2 flex flex-wrap items-center gap-3">
          <RiskPill level={f.risk_band} p={f.overdraft_probability} long />
        </div>
        <p className="mt-2 text-[.9rem]">
          Balance {money(f.start_balance)} today. Lowest point about <strong className="num">{money(f.lowest_point.p50)}</strong> around{" "}
          {shortDate(parseDate(f.lowest_point.date))}.
        </p>
        {f.reasons.length > 0 && (
          <ul className="mt-1 list-disc pl-5 text-[.85rem] text-muted">
            {f.reasons.slice(0, 3).map((r) => (
              <li key={r.feature}>
                {r.feature}: {r.detail}
              </li>
            ))}
          </ul>
        )}
        <Link to="/forecast" onClick={() => setMemberId(f.member_id)} className="mt-2 inline-block text-[.85rem] font-semibold">
          Open the full forecast →
        </Link>
      </li>
    );
  }
  if (ev.type === "what_if") {
    const before = d.before as { overdraft_probability: number };
    const after = d.after_forecast as ForecastResult;
    const pay = d.payment as { amount: number; date: string; description: string };
    return (
      <li className="rounded-2xl border border-line p-4">
        {head(`What if: ${pay.description}`)}
        <p className="mt-2 text-[.9rem]">
          {money(pay.amount)} on {shortDate(parseDate(pay.date))}: chance of going below £0 goes from{" "}
          <strong className="num">{pct(before.overdraft_probability)}</strong> to <strong className="num">{pct(after.overdraft_probability)}</strong>.
        </p>
        <p className="mt-1 text-[.8rem] text-muted">Current account only; savings are not included.</p>
      </li>
    );
  }
  if (ev.type === "rules_lookup") {
    const sources = (d.sources as (Source & { section?: string })[]) ?? [];
    return (
      <li className="rounded-2xl border border-line p-4">
        {head("Looked up official guidance")}
        <p className="mt-1 text-[.85rem] text-muted">&ldquo;{String(d.query_en)}&rdquo;</p>
        <ul className="mt-1 space-y-0.5 text-[.85rem]">
          {sources.map((s) => (
            <li key={s.url + (s.section ?? "")}>
              <a href={s.url} target="_blank" rel="noreferrer">
                {s.title}
              </a>
              {s.section && <span className="text-muted"> · {s.section}</span>}
            </li>
          ))}
        </ul>
      </li>
    );
  }
  if (ev.type === "escalation") {
    const contacts = (d.contacts as HelpResource[]) ?? [];
    return (
      <li className="rounded-2xl p-4" style={{ background: "var(--critical-soft)" }}>
        {head(`Talk to a person (${String(d.reason)})`)}
        <ul className="mt-2 space-y-0.5 text-[.9rem]">
          {contacts.map((c) => (
            <li key={c.name}>
              <strong>{c.name}</strong>
              {c.phone && <span className="num"> · {c.phone}</span>}
            </li>
          ))}
        </ul>
      </li>
    );
  }
  if (ev.type === "call_ended" && d.summary) {
    return (
      <li className="rounded-2xl border border-line p-4">
        {head("Call summary")}
        <p className="mt-1 text-[.9rem]">{String(d.summary)}</p>
      </li>
    );
  }
  return null;
}

export default function VoiceCoach() {
  const { familyData, family, member, setMemberId } = useHeirloom();
  const [availability, setAvailability] = useState<Availability>("checking");
  const [call, setCall] = useState<CallState>("idle");
  const [lines, setLines] = useState<Line[]>([]);
  const [events, setEvents] = useState<VoiceEvent[]>([]);
  const conv = useRef<Conversation | null>(null);

  // check the backend now, then keep re-checking until the voice agent is ready (no page refresh needed)
  useEffect(() => {
    if (availability === "ready") return;
    let live = true;
    const check = () =>
      voiceStatus()
        .then((s) => live && setAvailability(s.configured ? "ready" : "not-configured"))
        .catch(() => live && setAvailability("offline"));
    check();
    const timer = window.setInterval(check, 5000);
    return () => {
      live = false;
      window.clearInterval(timer);
    };
  }, [availability]);

  // English dashboard: tool calls made by the agent arrive here as Server-Sent Events.
  useEffect(() => {
    if (availability !== "ready") return;
    const es = new EventSource(voiceEventsUrl(family));
    const onEvent = (e: MessageEvent) => {
      try {
        const ev = JSON.parse(e.data) as VoiceEvent;
        setEvents((prev) => [ev, ...prev].slice(0, 20));
      } catch {
        /* ignore malformed events */
      }
    };
    EVENT_TYPES.forEach((t) => es.addEventListener(t, onEvent as EventListener));
    return () => es.close();
  }, [family, availability]);

  // end the call when the person changes or the page closes
  useEffect(() => {
    return () => {
      conv.current?.endSession().catch(() => undefined);
      conv.current = null;
    };
  }, [member.id]);

  const say = (role: Line["role"], text: string, id = `${Date.now()}-${Math.random()}`) =>
    setLines((prev) => {
      const i = prev.findIndex((l) => l.id === id);
      if (i >= 0) return prev.map((l, j) => (j === i ? { ...l, text } : l));
      return [...prev, { id, role, text }];
    });

  async function start() {
    setCall("connecting");
    try {
      await navigator.mediaDevices.getUserMedia({ audio: true });
      const s = await voiceSession(member.id);
      conv.current = await Conversation.startSession({
        signedUrl: s.signed_url,
        connectionType: "websocket",
        dynamicVariables: s.dynamic_variables,
        onConnect: () => {
          setCall("listening");
          say("system", `Call started with ${member.name}`);
        },
        onDisconnect: () => {
          setCall("idle");
          conv.current = null;
          say("system", "Call ended");
        },
        onModeChange: ({ mode }) => setCall(mode === "speaking" ? "speaking" : "listening"),
        onMessage: (m) => say(m.role === "user" ? "user" : "agent", m.message, m.response_id ? `r-${m.response_id}` : `e-${m.event_id}`),
        onError: (message) => say("system", `Error: ${message}`),
      });
    } catch (err) {
      setCall("idle");
      const msg = (err as Error).message || String(err);
      say("system", /permission|denied|NotAllowed/i.test(msg) ? "Microphone access was blocked. Allow it in the browser and try again." : `Could not start: ${msg}`);
    }
  }

  async function stop() {
    await conv.current?.endSession();
  }

  const otherLanguages = member.languages.filter((l) => l !== "en");
  const tryLangs = ["en", ...otherLanguages, ...["ms", "zh"].filter((l) => !otherLanguages.includes(l))];

  return (
    <Page>
      <PageHeader
        page="coach"
        label="Voice Coach"
        title="Ask in Your Own Words"
        lead={`Talk to the coach in English, Polish, Malay or Mandarin. It looks up ${member.name}'s real numbers before it answers, while the dashboard below stays in English for the rest of the family.`}
        aside={<PersonPicker members={familyData.members} value={member.id} onChange={setMemberId} />}
      />

      {availability === "offline" && (
        <p className="mb-6 rounded-2xl p-4" style={{ background: "var(--warn-soft)" }}>
          The voice coach needs the Heirloom backend and an internet connection. Start the backend with <code>uvicorn backend.main:app --port 8000</code>.
        </p>
      )}
      {availability === "not-configured" && (
        <p className="mb-6 rounded-2xl p-4" style={{ background: "var(--warn-soft)" }}>
          The backend is running, but the voice agent isn&rsquo;t set up: add <code>ELEVENLABS_API_KEY</code> and <code>ELEVENLABS_AGENT_ID</code> to{" "}
          <code>.env</code> and restart it (see backend/voice/README.md).
        </p>
      )}

      <div className="flex flex-wrap items-center gap-4">
        {call === "idle" ? (
          <button
            onClick={start}
            disabled={availability !== "ready"}
            className="inline-flex items-center gap-2 rounded-full bg-ink px-5 py-2.5 font-semibold text-surface hover:opacity-90 disabled:opacity-40"
          >
            <Mic className="h-4 w-4" /> Talk to the Coach as {member.name}
          </button>
        ) : (
          <button
            onClick={stop}
            disabled={call === "connecting"}
            className="inline-flex items-center gap-2 rounded-full px-5 py-2.5 font-semibold text-white hover:opacity-90 disabled:opacity-40"
            style={{ background: "var(--critical)" }}
          >
            <PhoneOff className="h-4 w-4" /> End Call
          </button>
        )}
        <span className="inline-flex items-center gap-2 text-[.9rem] text-muted" role="status">
          <span className={cn("wave flex h-[22px] items-center gap-[3px]", call === "speaking" && "on")} aria-hidden="true">
            <span />
            <span />
            <span />
            <span />
            <span />
          </span>
          {{ idle: "Not connected", connecting: "Connecting…", listening: "Listening", speaking: "Coach speaking" }[call]}
        </span>
      </div>

      <div className="mt-4 flex flex-wrap gap-2">
        {tryLangs.flatMap((l) =>
          (TRY[l] ?? []).map((t) => (
            <span key={t} lang={l} className="rounded-full border border-line px-3.5 py-1.5 text-[.85rem] text-muted" title={LANGUAGE_NAME[l]}>
              &ldquo;{t}&rdquo;
            </span>
          )),
        )}
      </div>

      <div className="mt-7 grid grid-cols-2 gap-6 lg960:grid-cols-1">
        <section className="min-w-0 rounded-[22px] border border-line bg-surface p-[clamp(18px,3vw,26px)]" aria-live="polite">
          <h2 className="font-display text-[1.1rem] font-bold tracking-[-0.02em]">Conversation</h2>
          {lines.length === 0 ? (
            <p className="py-8 text-center text-muted">Start a call and ask a question out loud.</p>
          ) : (
            <ul className="mt-3 flex max-h-[460px] flex-col gap-2 overflow-auto">
              {lines.map((l) =>
                l.role === "system" ? (
                  <li key={l.id} className="self-center text-[.8rem] text-muted">
                    {l.text}
                  </li>
                ) : (
                  <li
                    key={l.id}
                    className={cn(
                      "max-w-[88%] rounded-[18px] px-4 py-2.5",
                      l.role === "user" ? "self-end rounded-br-[5px] bg-sunk" : "self-start rounded-bl-[5px]",
                    )}
                    style={l.role === "agent" ? { background: "var(--p-coach)" } : undefined}
                  >
                    {l.text}
                  </li>
                ),
              )}
            </ul>
          )}
        </section>
        <section className="min-w-0 rounded-[22px] border border-line bg-surface p-[clamp(18px,3vw,26px)]" aria-live="polite">
          <h2 className="font-display text-[1.1rem] font-bold tracking-[-0.02em]">Family Dashboard (English)</h2>
          {events.length === 0 ? (
            <p className="py-8 text-center text-muted">When the coach looks something up, the result appears here in English.</p>
          ) : (
            <ul className="mt-3 flex max-h-[460px] flex-col gap-3 overflow-auto">
              {events.map((ev) => (
                <EventCard key={`${ev.type}-${ev.ts}`} ev={ev} />
              ))}
            </ul>
          )}
        </section>
      </div>
      <p className="mt-3 text-[.76rem] text-muted">
        Voice is opt-in and starts only when you press the button. The ElevenLabs agent detects the language and calls the same Heirloom backend as these
        pages; your API key stays on the server.
      </p>
      <Disclaimer className="mt-1" />
    </Page>
  );
}
