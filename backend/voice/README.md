# Voice coach (ElevenLabs): backend

Someone (e.g. Halina) speaks Polish to the ElevenLabs agent. The agent calls our webhook tools, which return the numbers in English, and answers in Polish. Each tool call is also pushed to the dashboard over Server-Sent Events, so the screen updates in English at the same time.

```
Browser ──GET /voice/session──► backend ──signed URL──► ElevenLabs (key never reaches the browser)
Browser ◄═══ voice (WebRTC/WS) ═══► ElevenLabs agent ──POST /voice/tools/*──► backend
Dashboard ◄──GET /voice/events (SSE, English)── backend
ElevenLabs ──POST /voice/webhooks/post-call (HMAC)──► backend → data/voice/conversations.jsonl
```

## Setup (about 10 minutes)
1. `cp .env.example .env` and set `ELEVENLABS_API_KEY`, plus a long random `HEIRLOOM_TOOL_SECRET`.
2. Run the API (`uvicorn backend.main:app --port 8000`) and expose it: `ngrok http 8000`. Put the https URL in `PUBLIC_BASE_URL`.
3. `python -m backend.voice.provision --dry-run` to check the payloads, then `python -m backend.voice.provision`.
   Paste the printed `ELEVENLABS_AGENT_ID` into `.env` and restart the API. Re-running updates the agent and tools in place.
4. Optional: in the ElevenLabs dashboard, add a post-call webhook pointing to `PUBLIC_BASE_URL/voice/webhooks/post-call` and copy its secret into `ELEVENLABS_WEBHOOK_SECRET`.
5. `GET /voice/status` shows what is configured (it never returns the secrets themselves).

If ngrok's URL changes, update `PUBLIC_BASE_URL` and re-run `provision`.

## Endpoints
| Endpoint | Who calls it | What it does |
|---|---|---|
| `GET /voice/session?member_id=halina` | frontend | `{signed_url, dynamic_variables}` → `conversation.startSession({signedUrl, dynamicVariables})` |
| `GET /voice/events?family_id=nowak` | dashboard | SSE events: `forecast`, `what_if`, `rules_lookup`, `escalation`, `session_started`, `call_ended` |
| `GET /voice/events/recent` | dashboard | the last 50 events (for polling instead of SSE) |
| `POST /voice/tools/get_cash_forecast` | agent | 90-day forecast in a form that's easy to say aloud. The event carries the full `/forecast` payload |
| `POST /voice/tools/what_if_payment` | agent | "Can I give Zofia £500?": overdraft chance before and after (**current account only**) |
| `POST /voice/tools/lookup_money_rules` | agent | Search over `data/kb` (GOV.UK, FCA, Citizens Advice) with sources. Swap for `/ask` when the RAG is ready |
| `POST /voice/tools/talk_to_a_person` | agent | Logs the handoff and returns free help lines (StepChange, MoneyHelper, 159, Samaritans…) |
| `POST /voice/webhooks/post-call` | ElevenLabs | HMAC-verified transcript log |

Prompt, guardrails, languages and tool schemas live in [agent_spec.py](agent_spec.py).

**Languages:** English (default), Polish, Malay and Mandarin Chinese. ElevenLabs' language detection switches to whichever one the person speaks. To add another (e.g. Ukrainian, `uk`), add one entry to `LANGUAGES` with a greeting and a short style note, then re-run `provision`. The TTS model must be multilingual (`eleven_flash_v2_5` is set in `.env.example`).

## Dashboard snippet
```js
const es = new EventSource(`${API}/voice/events?family_id=nowak`);
es.addEventListener("forecast", e => { const ev = JSON.parse(e.data); setForecast(ev.data.forecast); setCaption(ev.data.summary_en); });
es.addEventListener("what_if", e => showScenario(JSON.parse(e.data).data));
es.addEventListener("escalation", e => showHelpCard(JSON.parse(e.data).data.contacts));
```
Run uvicorn with a single worker: the event bus lives in one process.
