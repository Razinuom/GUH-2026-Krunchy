# Heirloom Frontend

React + TypeScript + Vite + Tailwind, built from [transcripts/DESIGN.md](../transcripts/DESIGN.md).

```bash
cd frontend
npm install
npm run dev        # http://localhost:5173
npm run build      # type-check + production build
```

### On Windows (PowerShell)

Windows PowerShell 5.1 doesn't support `&&`, so run the commands one at a time:

```powershell
cd frontend
npm install
npm run dev
```

If you see `npm.ps1 cannot be loaded because running scripts is disabled`, use `npm.cmd install` and `npm.cmd run dev`,
or allow scripts for your user once: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.

To set the backend URL for one session:

```powershell
$env:VITE_API_URL = "http://localhost:8000"
npm run dev
```

## Backend (required)

Every number on the site comes from the FastAPI backend: start it first from the repo root.

```bash
uvicorn backend.main:app --port 8000      # set VITE_API_URL if you use another port
```

`src/lib/api.ts` calls `/families`, `/forecast`, `/hardship`, `/timemachine`, `/claimcheck`, `/escalate` and the
`/voice/*` endpoints. The demo date is pinned on the server (`HEIRLOOM_AS_OF=2026-11-07` in `.env`), so on stage
Tomasz shows 14% (Watch) and Daniel 88% (High Risk).

## Offline snapshot

If the backend can't be reached, pages show `src/data/snapshot.json`: real backend output, labelled
"Offline snapshot" on screen. Nothing is simulated or invented in the browser. It covers the family, every forecast
and early-warning result, the default Time Machine scenarios and the Claim Check examples; anything else shows a
clear "needs the backend" message. The voice coach always needs the backend and internet.

After changing personas or models, refresh it (a backend test fails if it is out of date):

```bash
python scripts/export_frontend_snapshot.py
```

## Where things live

| Path | What |
|---|---|
| `src/lib/api.ts` | All backend calls, with the offline-snapshot fallback |
| `src/lib/types.ts` | Response types matching `backend/heirloom/schemas.py` and `backend/hardship` |
| `src/lib/hooks.ts` | Data hooks (forecast, early warning, Time Machine) |
| `src/data/snapshot.json` | Saved backend results for offline mode (generated, don't edit) |
| `src/state/HeirloomContext.tsx` | Families (from `GET /families`), selected person, theme, text size, Time Machine controls |
| `src/pages/VoiceCoach.tsx` | Live ElevenLabs agent (`@elevenlabs/client`) plus the English dashboard fed by `/voice/events` |
| `src/components/ui/dock.tsx` | Top-bar dock (framer-motion magnification) |
| `src/components/charts/BandChart.tsx` | Every chart (bands, median, £0, goal, floor) |
