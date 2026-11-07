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

To set the backend URL or demo date for one session:

```powershell
$env:VITE_API_URL = "http://localhost:8000"
$env:VITE_DEMO_TODAY = "live"
npm run dev
```

## Backend

`src/lib/api.ts` calls the FastAPI endpoints from the build brief (`/forecast`, `/timemachine`, `/claimcheck`, `/ask`, `/escalate`).
Set the URL with `VITE_API_URL` (default `http://localhost:8000`, see `.env.example`).

If a call fails or takes longer than 2 seconds, the page uses the local simulation in `src/lib/simulate.ts`,
so the demo works with no backend and no Wi-Fi. Each page notes whether it is showing live or offline results.

## Demo date

Forecasts are pinned to 7 November 2026 so the numbers stay fixed on stage (Tomasz: 14%, Watch; Daniel: 42%, High Risk).
Override with `VITE_DEMO_TODAY=2026-12-01`, or `VITE_DEMO_TODAY=live` for the real date.

## Where things live

| Path | What |
|---|---|
| `src/components/ui/dock.tsx` | Top-bar dock (framer-motion magnification) |
| `src/components/charts/BandChart.tsx` | Every chart (bands, median, £0, goal, floor) |
| `src/lib/families.ts` | The two demo families and their cash-flow inputs |
| `src/lib/coach.ts` | Voice Coach questions and English / Polish answers |
| `src/state/HeirloomContext.tsx` | Family, person, theme, text size, Time Machine state |
