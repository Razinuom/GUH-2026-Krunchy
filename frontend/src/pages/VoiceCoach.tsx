import { Link } from "react-router-dom";
import { Play, Square } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { PersonPicker } from "@/components/family/PersonPicker";
import { Disclaimer, Page } from "@/components/layout/Page";
import { PageHeader } from "@/components/layout/PageHeader";
import { ask } from "@/lib/api";
import { questionsFor, type CoachQuestion } from "@/lib/coach";
import { cn } from "@/lib/utils";
import { useHeirloom } from "@/state/HeirloomContext";

type Turn = {
  q: CoachQuestion;
  question: string;
  answer?: string;
  sources: { title: string; url: string }[];
  lang: "en" | "pl";
  updatedTm?: boolean;
};

function LangSwitch({ value, onChange }: { value: "en" | "pl"; onChange: (l: "en" | "pl") => void }) {
  return (
    <div role="radiogroup" aria-label="Language" className="inline-flex rounded-full bg-surface/65 p-[3px]">
      {(
        [
          ["en", "English"],
          ["pl", "Polski"],
        ] as const
      ).map(([id, label]) => (
        <button
          key={id}
          role="radio"
          aria-checked={value === id}
          lang={id}
          onClick={() => onChange(id)}
          className={cn("rounded-full px-3.5 py-1.5 text-[.88rem]", value === id ? "bg-ink font-semibold text-surface" : "text-ink/80")}
        >
          {label}
        </button>
      ))}
    </div>
  );
}

export default function VoiceCoach() {
  const { familyData, member, setMemberId, lang, setLang, tm, setTm } = useHeirloom();
  const useLang = member.speaksPolish ? lang : "en";
  const questions = useMemo(() => questionsFor(member, familyData.id, tm), [member, familyData.id, tm]);
  const [turn, setTurn] = useState<Turn | null>(null);
  const [speaking, setSpeaking] = useState(false);
  const timer = useRef<number>();

  useEffect(() => {
    setTurn(null);
  }, [member.id]);

  useEffect(() => () => stop(), []);

  function stop() {
    window.clearTimeout(timer.current);
    if ("speechSynthesis" in window) window.speechSynthesis.cancel();
    setSpeaking(false);
  }

  async function choose(q: CoachQuestion) {
    stop();
    const question = q.q[useLang] || q.q.en;
    setTurn({ q, question, sources: [], lang: useLang });
    const local = q.answer();
    let text = local.text[useLang] || local.text.en;
    let sources = local.sources;
    if (q.tool.path === "/ask") {
      const remote = await ask(question, useLang);
      if (remote) {
        text = remote.answer;
        sources = remote.sources;
      }
    } else {
      await new Promise((r) => setTimeout(r, 450));
    }
    if (local.tm) setTm(local.tm);
    setTurn({ q, question, answer: text, sources, lang: useLang, updatedTm: !!local.tm });
  }

  function play() {
    if (!turn?.answer) return;
    if (speaking) return stop();
    setSpeaking(true);
    const synth = "speechSynthesis" in window ? window.speechSynthesis : null;
    if (synth) {
      const u = new SpeechSynthesisUtterance(turn.answer);
      u.lang = turn.lang === "pl" ? "pl-PL" : "en-GB";
      const voice = synth.getVoices().find((v) => v.lang.toLowerCase().startsWith(u.lang.slice(0, 2).toLowerCase()));
      if (voice) u.voice = voice;
      u.rate = 0.95;
      u.onend = () => setSpeaking(false);
      u.onerror = () => setSpeaking(false);
      synth.cancel();
      synth.speak(u);
    } else {
      timer.current = window.setTimeout(() => setSpeaking(false), Math.min(15000, turn.answer.length * 60));
    }
  }

  const toolBody = turn ? JSON.stringify(turn.q.tool.path === "/ask" ? { question: turn.question, lang: turn.lang } : turn.q.tool.body) : "";

  return (
    <Page>
      <PageHeader
        page="coach"
        label="Voice Coach"
        title={`Ask in Your Own Words`}
        lead={
          member.speaksPolish
            ? `${member.name} can ask in Polish. The coach answers in Polish while the dashboard stays in English for the rest of the family.`
            : "Tap a question or speak to the coach. It looks up the family's real numbers before it answers."
        }
        aside={
          <div className="flex flex-col items-start gap-3">
            <PersonPicker members={familyData.members} value={member.id} onChange={setMemberId} />
            {member.speaksPolish && <LangSwitch value={lang} onChange={setLang} />}
          </div>
        }
      />

      <h2 className="font-display text-[1.35rem] font-bold tracking-[-0.02em]">Questions {member.name} Might Ask</h2>
      <div className="mt-4 flex flex-wrap gap-2.5">
        {questions.map((q) => {
          const on = turn?.q.id === q.id;
          const text = q.q[useLang] || q.q.en;
          return (
            <button
              key={q.id}
              onClick={() => choose(q)}
              lang={useLang}
              aria-pressed={on}
              className={cn(
                "rounded-full border px-4 py-2 text-left text-[.9rem] transition-colors",
                on ? "border-ink bg-ink text-surface" : "border-line hover:border-ink",
              )}
            >
              {text}
            </button>
          );
        })}
      </div>

      <div className="mt-7 rounded-[22px] border border-line bg-surface p-[clamp(18px,3vw,28px)]" aria-live="polite">
        {!turn ? (
          <p className="py-8 text-center text-muted">Pick a question above to hear how the coach answers.</p>
        ) : (
          <div className="space-y-4">
            <div className="flex justify-end">
              <p lang={turn.lang} className="max-w-[min(560px,85%)] rounded-[18px] rounded-br-[5px] bg-sunk px-4 py-3">
                {turn.question}
              </p>
            </div>
            <p className="break-all font-mono text-[.74rem] text-muted">
              → tool call · POST {turn.q.tool.path} {toolBody}
            </p>
            <div className="flex justify-start">
              <div lang={turn.lang} className="max-w-[min(640px,92%)] rounded-[18px] rounded-bl-[5px] px-4 py-3" style={{ background: "var(--p-coach)" }}>
                {turn.answer ?? <span className="text-muted">Thinking…</span>}
                {turn.sources.length > 0 && (
                  <p className="mt-2 text-[.78rem]">
                    Source:{" "}
                    {turn.sources.map((s, i) => (
                      <span key={s.url}>
                        {i > 0 && " · "}
                        <a href={s.url} target="_blank" rel="noreferrer">
                          {s.title}
                        </a>
                      </span>
                    ))}
                  </p>
                )}
              </div>
            </div>
            {turn.answer && (
              <div className="flex flex-wrap items-center gap-4 pt-1">
                <button onClick={play} className="inline-flex items-center gap-2 rounded-full bg-ink px-4 py-2 font-semibold text-surface hover:opacity-90">
                  {speaking ? <Square className="h-4 w-4" /> : <Play className="h-4 w-4" />}
                  {speaking ? "Stop" : "Play Answer"}
                </button>
                <span className={cn("wave flex h-[22px] items-center gap-[3px]", speaking && "on")} aria-hidden="true">
                  <span />
                  <span />
                  <span />
                  <span />
                  <span />
                </span>
                {turn.updatedTm && (
                  <Link to="/time-machine" className="text-[.88rem] font-semibold">
                    Time Machine updated · See It →
                  </Link>
                )}
              </div>
            )}
          </div>
        )}
      </div>
      <p className="mt-3 text-[.76rem] text-muted">
        Voice is opt-in. In the full build an ElevenLabs agent listens, detects the language and calls these same tools; here the answer is read aloud by your browser.
      </p>
      <Disclaimer className="mt-1" />
    </Page>
  );
}
