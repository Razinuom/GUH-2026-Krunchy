# Heirloom: Design Spec for the React Build

Heirloom is a family money coach for the NatWest "AI for financial fairness and social mobility" track. This document describes the approved prototype design so the React frontend can match it exactly. The prototype is a single HTML page; this spec turns it into React components, tokens and behaviour.

---

## 1. Stack

| Choice | Why |
|---|---|
| React + TypeScript (Vite, or Next.js App Router) | Matches the brief |
| Tailwind CSS + shadcn/ui | Components live in `/components/ui`, which is where the shadcn CLI and copied components expect them |
| `framer-motion` | Dock magnification and page transitions |
| `lucide-react` | Every icon in the dock comes from Lucide |
| `react-router-dom` (Vite) or file routes (Next) | One route per page |

```bash
npm create vite@latest heirloom -- --template react-ts
cd heirloom
npx shadcn@latest init        # sets up Tailwind, /components/ui and lib/utils.ts (the cn helper)
npm i framer-motion lucide-react react-router-dom
```

### Folder structure

```
src/
  app/
    App.tsx              # router + providers
    routes.tsx
  components/
    ui/                  # shadcn + dock.tsx live here
      dock.tsx
    layout/
      TopBar.tsx
      PageHeader.tsx
    family/
      PersonCard.tsx
      PersonPicker.tsx
    charts/
      BandChart.tsx      # shared fan/band chart
    Crown.tsx
  pages/
    Home.tsx
    Family.tsx
    Forecast.tsx
    TimeMachine.tsx
    VoiceCoach.tsx
    ClaimCheck.tsx
    About.tsx
  state/
    HeirloomContext.tsx  # family, member, theme, text size
  lib/
    api.ts               # calls the FastAPI endpoints, falls back to local simulation
    simulate.ts          # forecast + Monte Carlo used as the fallback
    format.ts            # money(), moneyShort(), dates
  styles/
    globals.css          # design tokens below
```

---

## 2. Design principles

These came out of design review. Keep to them when adding anything new.

1. **One page per tool.** No long scrolling dashboard. The dock switches pages.
2. **No boxes around sections.** Separate content with space and 1px hairlines. Only things that really are objects get a container: chat bubbles, the scam verdict, advice callouts and controls.
3. **Colour has a meaning.** Each page has its own hue for its header. Each person has one colour everywhere they appear. Red and amber only ever mean risk.
4. **Light by default, with a night mode switch.** No gradients, glows, grid backgrounds or outlined text.
5. **Title Case** for titles, headings, labels, buttons and nav items. Sentence case for full sentences (descriptions, the coach's answers, notes).

---

## 3. Design tokens

Put these in `styles/globals.css`. Night mode is the `.night` class on `<html>`, set by the theme switch (not by the OS setting).

```css
:root {
  /* surfaces and text */
  --bg: #F6F8F7; --surface: #FFFFFF; --sunk: #EFF3F1;
  --ink: #10201A; --muted: #5A6A63; --line: #E2E8E4;

  /* brand */
  --accent: #0E7A5C; --accent-soft: #DDF3EA; --on-accent: #FFFFFF;
  --gold: #D39A1E;

  /* one colour per generation */
  --gen1: #E39A0E;   /* grandparent: marigold */
  --gen2: #2F6FE4;   /* parent: blue */
  --gen3: #8A55E8;   /* young adult: violet */

  /* risk only */
  --good: #13865B; --warn: #B45309; --critical: #C2281D;
  --good-soft: #E1F5EB; --warn-soft: #FDF0DB; --critical-soft: #FDE6E3;

  /* page header fill (--p-*) and its label colour (--k-*) */
  --p-family: #FFEFD0;   --k-family: #8F5B00;
  --p-forecast: #E2ECFF; --k-forecast: #1C4DAE;
  --p-tm: #EEE5FF;       --k-tm: #6236BE;
  --p-coach: #FFE4DC;    --k-coach: #A93A22;
  --p-claims: #D9F3E6;   --k-claims: #0B6B50;
  --p-about: #ECEFEA;    --k-about: #45524C;

  --shadow: 0 18px 40px -22px rgba(16, 32, 26, .35);
  color-scheme: light;
}

html.night {
  --bg: #0E1613; --surface: #16211D; --sunk: #1F2C27;
  --ink: #EEF4F1; --muted: #9DB1A9; --line: #2A3A33;
  --accent: #3FC596; --accent-soft: #163A2D; --on-accent: #0E1613;
  --gold: #EDB94D;
  --gen1: #F2B23A; --gen2: #6E9CFF; --gen3: #AA8BFF;
  --good: #4FD19A; --warn: #F5A84B; --critical: #FF7B6E;
  --good-soft: #153A2B; --warn-soft: #3D2B11; --critical-soft: #46201C;
  --p-family: #33270F;   --k-family: #F5C463;
  --p-forecast: #15244A; --k-forecast: #93B4FF;
  --p-tm: #271D47;       --k-tm: #C6ADFF;
  --p-coach: #3F1F18;    --k-coach: #FF9F84;
  --p-claims: #113528;   --k-claims: #72DDB2;
  --p-about: #1F2925;    --k-about: #BAC7C1;
  --shadow: 0 18px 40px -20px rgba(0, 0, 0, .7);
  color-scheme: dark;
}

html.large { font-size: 112.5%; }   /* "Larger Text" button */

body {
  background: var(--bg);
  color: var(--ink);
  font-family: "IBM Plex Sans", "Segoe UI", system-ui, sans-serif;
  font-size: .9375rem;
  line-height: 1.55;
  transition: background-color .3s, color .3s;
}
```

Map them in `tailwind.config` so components can use `bg-surface`, `text-muted`, `border-line` and so on:

```ts
// tailwind.config.ts (extend)
colors: {
  bg: "var(--bg)", surface: "var(--surface)", sunk: "var(--sunk)",
  ink: "var(--ink)", muted: "var(--muted)", line: "var(--line)",
  accent: "var(--accent)", gold: "var(--gold)",
  gen1: "var(--gen1)", gen2: "var(--gen2)", gen3: "var(--gen3)",
  good: "var(--good)", warn: "var(--warn)", critical: "var(--critical)",
},
fontFamily: {
  display: ['"Bricolage Grotesque"', '"Segoe UI"', "system-ui", "sans-serif"],
  body: ['"IBM Plex Sans"', '"Segoe UI"', "system-ui", "sans-serif"],
  mono: ['"IBM Plex Mono"', "ui-monospace", "Menlo", "monospace"],
},
```

### Page colours

| Page | Route | Header fill | Label colour | Dock icon colour when active |
|---|---|---|---|---|
| Home | `/` | none | none | `--gold` |
| The Family | `/family` | `--p-family` | `--k-family` | `#C77F00` |
| Next 90 Days | `/forecast` | `--p-forecast` | `--k-forecast` | `--gen2` |
| Time Machine | `/time-machine` | `--p-tm` | `--k-tm` | `--gen3` |
| Voice Coach | `/coach` | `--p-coach` | `--k-coach` | `#D9532F` |
| Claim Check | `/claims` | `--p-claims` | `--k-claims` | `--accent` |
| How It Works | `/about` | `--p-about` | `--k-about` | `--muted` |

### Person colours

The selected person's colour is exposed as `--sel` on `<main>` (`data-gen="1|2|3"`), so the forecast chart, its legend and the person picker all follow whoever is selected.

```css
main[data-gen="1"] { --sel: var(--gen1); }
main[data-gen="2"] { --sel: var(--gen2); }
main[data-gen="3"] { --sel: var(--gen3); }
```

In the Time Machine, the young adult (receiver) is always `--gen3` and the grandparent (giver) is always `--gen1`.

---

## 4. Typography

Load from Google Fonts:

```html
<link href="https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:wght@500;600;700;800&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap" rel="stylesheet">
```

| Use | Font | Size | Weight | Tracking |
|---|---|---|---|---|
| Home title "Heirloom" | Bricolage | `clamp(3.8rem, 10.5vw, 8rem)` | 800 | -0.06em, line-height 0.9 |
| Page title (`h1`) | Bricolage | `clamp(2.1rem, 4.6vw, 3.3rem)` | 800 | -0.04em |
| Section heading (`h2`) | Bricolage | 1.35rem | 700 | -0.02em |
| Big numbers (stats) | Bricolage | 2.2rem | 800 | -0.035em, tabular numbers |
| Time Machine percentages | Bricolage | 3.2rem | 800 | -0.04em |
| Page header label | Plex Sans | 0.95rem | 600 | normal, in `--k-*` |
| Body | Plex Sans | 0.9375rem | 400 | normal |
| Small print | Plex Sans | 0.76rem | 400 | in `--muted` |
| Tool-call trace in the coach | Plex Mono | 0.74rem | 400 | in `--muted` |

Use `font-variant-numeric: tabular-nums` on every number that sits in a row or column.

---

## 5. Layout

- Content width: `max-w-[1180px] mx-auto`, side padding `max(20px, env(safe-area-inset-left))`.
- Top bar: sticky, 76px tall, `bg-surface/90` with a 14px backdrop blur and a bottom hairline. Three columns: brand on the left, dock centred, family switcher on the right.
- Each page: `py-7` top, `pb-18` bottom. A **page header** first, then content.
- **Page header:** fill `--p-*`, radius 28px, padding `clamp(26px, 4vw, 44px)`. Left: label, `h1`, one-line lead. Right (optional): person picker and other page controls. Margin below: 36px.
- **Two-column pages** (Next 90 Days): `grid-cols-[1.7fr_1fr]`, left column `pr-10`, right column `pl-10 border-l border-line`.
- **Breakpoints:** at ≤960px the dock moves to a second row and all two-column layouts stack (the divider turns into a top hairline). At ≤720px the three people stack. At ≤600px the dock scrolls sideways, labels are hidden and the magnifying effect is off.

---

## 6. Components

### 6.1 Crown (logo)

A single gold crown with a vertical metallic gradient (`#FFE9A8` → `#E8B23E` → `#A9781A`), three pearls on the tips (`#FFF6DC`) and three gems on the band in `--gen1`, `--gen2`, `--gen3`: the three generations.

```tsx
// components/Crown.tsx
export function Crown({ size = 32 }: { size?: number }) {
  return (
    <svg width={size} viewBox="-1 0 30 28" aria-hidden="true" className="overflow-visible">
      <defs>
        <linearGradient id="crown-gold" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#FFE9A8" />
          <stop offset=".55" stopColor="#E8B23E" />
          <stop offset="1" stopColor="#A9781A" />
        </linearGradient>
      </defs>
      <g fill="url(#crown-gold)">
        <path d="M3.2 21.5 1.6 8.6c-.1-1 .9-1.5 1.6-1l5.6 4.3 4-8.4c.5-1.1 1.9-1.1 2.4 0l4 8.4 5.6-4.3c.7-.5 1.7 0 1.6 1l-1.6 12.9Z" />
        <rect x="3" y="22.4" width="22" height="4.6" rx="1.6" />
      </g>
      <rect x="3" y="22.4" width="22" height="4.6" rx="1.6" fill="#000" fillOpacity=".16" />
      <path d="M5.2 19.5 4.3 11.4 8.6 14.6" fill="none" stroke="#fff" strokeOpacity=".55" strokeWidth="1.1" strokeLinecap="round" />
      {[[2.4, 7.4, 1.8], [14, 2.4, 2.2], [25.6, 7.4, 1.8]].map(([cx, cy, r]) => (
        <circle key={cx} cx={cx} cy={cy} r={r} fill="#FFF6DC" stroke="#B98722" strokeWidth=".5" />
      ))}
      <circle cx="8.5" cy="24.7" r="1.25" fill="var(--gen1)" />
      <circle cx="14" cy="24.7" r="1.55" fill="var(--gen2)" />
      <circle cx="19.5" cy="24.7" r="1.25" fill="var(--gen3)" />
    </svg>
  );
}
```

Sizes: 32px in the top bar, 76px on the home page.

### 6.2 Dock (top navigation)

Based on the Apple-style `Dock` component (framer-motion), adapted for a **top** bar: items grow downward, labels appear **below** the icon, and the active page gets a filled icon plus a dot.

Tuned values from the prototype (deliberately calm, not bouncy):

| Setting | Value |
|---|---|
| Icon size at rest | 44px |
| Icon size under the pointer | 60px |
| Distance that affects neighbours | 130px |
| Spring | `{ mass: 0.1, stiffness: 170, damping: 16 }` |
| Panel | `bg-surface`, 1px `border-line`, radius 22px, padding `6px 10px`, gap 10px |
| Icon circle at rest | `bg-sunk`, icon `text-ink`, icon size = half the circle |
| Active | circle filled with the page's icon colour, white icon, 5px dot 7px below |
| Label | `bg-ink text-surface`, 0.74rem, weight 600, radius 8px, 12px below the icon, fades in over 160ms |

Copy the shadcn `dock.tsx` into `components/ui/dock.tsx`, then make these changes:

```tsx
// components/ui/dock.tsx: changes from the original
const DEFAULT_MAGNIFICATION = 60;   // was 80
const DEFAULT_DISTANCE = 130;       // was 150
const DEFAULT_PANEL_HEIGHT = 58;    // was 64

// Dock(): calmer spring, and align items to the TOP so they grow downward
spring = { mass: 0.1, stiffness: 170, damping: 16 },
// outer motion.div:  className="flex max-w-full items-start"
// inner panel:       className="mx-auto flex w-fit items-start gap-[10px] rounded-[22px] border border-line bg-surface px-[10px] py-[6px]"

// DockItem(): base size 44 instead of 40
const widthTransform = useTransform(mouseDistance, [-distance, 0, distance], [44, magnification, 44]);

// DockLabel(): show BELOW the icon
initial={{ opacity: 0, y: -6 }}
animate={{ opacity: 1, y: 0 }}
exit={{ opacity: 0, y: -6 }}
className="absolute top-[calc(100%+12px)] left-1/2 whitespace-pre rounded-lg bg-ink px-2 py-1 text-xs font-semibold text-surface"
```

Usage in the top bar:

```tsx
// components/layout/TopBar.tsx
import { NavLink, useLocation } from "react-router-dom";
import { Home, Users, Activity, Hourglass, Mic, ShieldCheck, Info, Type, Moon, Sun, LifeBuoy } from "lucide-react";
import { Dock, DockIcon, DockItem, DockLabel } from "@/components/ui/dock";
import { Crown } from "@/components/Crown";
import { useHeirloom } from "@/state/HeirloomContext";

const PAGES = [
  { to: "/",             title: "Home",         icon: Home,        color: "var(--gold)" },
  { to: "/family",       title: "The Family",   icon: Users,       color: "#C77F00" },
  { to: "/forecast",     title: "Next 90 Days", icon: Activity,    color: "var(--gen2)" },
  { to: "/time-machine", title: "Time Machine", icon: Hourglass,   color: "var(--gen3)" },
  { to: "/coach",        title: "Voice Coach",  icon: Mic,         color: "#D9532F" },
  { to: "/claims",       title: "Claim Check",  icon: ShieldCheck, color: "var(--accent)" },
  { to: "/about",        title: "How It Works", icon: Info,        color: "var(--muted)" },
];

export function TopBar() {
  const { pathname } = useLocation();
  const { night, toggleNight, large, toggleLarge, openHelp, family, setFamily } = useHeirloom();

  return (
    <div className="sticky top-0 z-10 border-b border-line bg-surface/90 backdrop-blur-md">
      <div className="mx-auto grid h-[76px] max-w-[1180px] grid-cols-[1fr_auto_1fr] items-center gap-4 px-5">
        <NavLink to="/" className="flex items-center gap-2.5 text-ink no-underline">
          <Crown size={32} />
          <span>
            <strong className="block font-display text-xl font-extrabold tracking-tight">Heirloom</strong>
            <small className="block text-xs text-muted">Family Money Coach</small>
          </span>
        </NavLink>

        <Dock>
          {PAGES.map(({ to, title, icon: Icon, color }) => {
            const active = pathname === to;
            return (
              <NavLink key={to} to={to} aria-current={active ? "page" : undefined}>
                <DockItem
                  className="relative aspect-square rounded-full"
                  style={{ background: active ? color : "var(--sunk)", color: active ? "#fff" : "var(--ink)" }}
                >
                  <DockLabel>{title}</DockLabel>
                  <DockIcon><Icon className="h-full w-full" /></DockIcon>
                </DockItem>
              </NavLink>
            );
          })}
          <span className="mx-0.5 h-[30px] w-px self-center bg-line" aria-hidden="true" />
          <button onClick={toggleLarge} aria-pressed={large}>
            <DockItem className="aspect-square rounded-full bg-sunk">
              <DockLabel>Larger Text</DockLabel>
              <DockIcon><Type className="h-full w-full" /></DockIcon>
            </DockItem>
          </button>
          <button onClick={toggleNight} aria-pressed={night}>
            <DockItem className="aspect-square rounded-full bg-sunk">
              <DockLabel>{night ? "Day Mode" : "Night Mode"}</DockLabel>
              <DockIcon>{night ? <Sun className="h-full w-full" /> : <Moon className="h-full w-full" />}</DockIcon>
            </DockItem>
          </button>
          <button onClick={openHelp}>
            <DockItem className="aspect-square rounded-full bg-ink text-surface">
              <DockLabel>Talk to a Person</DockLabel>
              <DockIcon><LifeBuoy className="h-full w-full" /></DockIcon>
            </DockItem>
          </button>
        </Dock>

        <FamilySwitch value={family} onChange={setFamily} />
      </div>
    </div>
  );
}
```

> The original `DockItem` doesn't accept `style`. Add `style?: React.CSSProperties` to its props and merge it with `{ width }`. Also add the active dot: a 5px circle at `bottom: -7px`, centred, filled with the page colour.

**Rules:**
- Turn the magnifying effect off when `prefers-reduced-motion: reduce` is set, and on screens narrower than 600px.
- The dock's outer width should stay at its resting width, so the brand and family switcher don't shift when icons grow. Position the panel absolutely inside a fixed-width wrapper.
- Every item needs a text label (the tooltip) and must be reachable by keyboard. The label also shows on `:focus-visible`.

### 6.3 Family switch

A segmented control: `bg-sunk`, 1px border, fully rounded, 3px padding. Options "Nowak Family" and "Okafor Family", never wrapping. Selected: `bg-ink text-surface font-semibold`. Switching family resets the selected person to the parent and the Time Machine to that family's defaults.

### 6.4 Page header

```tsx
// components/layout/PageHeader.tsx
type Props = { page: "family" | "forecast" | "tm" | "coach" | "claims" | "about";
               label: string; title: string; lead?: string; aside?: React.ReactNode };

export function PageHeader({ page, label, title, lead, aside }: Props) {
  return (
    <header
      className="mb-9 flex flex-wrap items-end justify-between gap-x-7 gap-y-5 rounded-[28px] p-[clamp(26px,4vw,44px)]"
      style={{ background: `var(--p-${page})` }}
    >
      <div className="min-w-0 max-w-[62ch]">
        <p className="mb-2 text-[.95rem] font-semibold" style={{ color: `var(--k-${page})` }}>{label}</p>
        <h1 className="font-display text-[clamp(2.1rem,4.6vw,3.3rem)] font-extrabold leading-[1.02] tracking-[-0.04em]">{title}</h1>
        {lead && <p className="mt-3 text-[1.05rem] opacity-80">{lead}</p>}
      </div>
      {aside}
    </header>
  );
}
```

### 6.5 Person card (The Family page)

Three columns divided by vertical hairlines, no boxes. Each column is a single button:

- 64px circle avatar in the person's colour with their initial (white, Bricolage 800)
- generation ("Grandparent" / "Parent" / "Young Adult") in the person's colour
- name and age, Bricolage 800 at 1.6rem
- role in `--muted`, plus "· speaks Polish" where relevant
- "Lowest point **£251** around 24 Jan"
- risk pill: "Watch · 14% chance below £0"
- "See Next 90 Days →" in `--accent`; the arrow nudges 4px right on hover

Hover: the name gets a 2px underline in the person's colour. Click: select that person and go to `/forecast`.

### 6.6 Person picker (page headers)

Used on Next 90 Days and Voice Coach. Small pills: 28px avatar plus the name, `bg-surface/65`. Selected: solid `bg-surface` with a 2px ring in the person's colour. Clicking only changes the selected person; it doesn't navigate.

### 6.7 Stat row

Three figures in a row, top and bottom hairlines, vertical hairlines between them, **no boxes**. Label (0.78rem, muted), value (Bricolage 800, 2.2rem), sub-line (0.78rem, muted). For the overdraft chance, colour the value by risk (`--good` / `--warn` / `--critical`) and add the matching pill.

Risk levels: below 10% = **Low Risk**, 10–30% = **Watch**, above 30% = **High Risk**.

### 6.8 Charts

One `BandChart` component draws every chart as SVG:

- Gridlines in `--line`; axis text 11px in `--muted`.
- Uncertainty bands (p10–p90 at 20% opacity, plus p25–p75 at 22% on the Time Machine) and the median line (2.4px) in the person's colour.
- A dot at the end of the median line.
- £0 line in `--critical`; deposit goal dashed in `--ink`; safety floor dashed in `--critical`; target year as a dashed vertical line in `--muted`.
- The forecast marks its lowest point with a hollow `--critical` circle.

Legend labels: "Likely Range (10th–90th Percentile)", "Most Likely Balance", "£0".

### 6.9 Early warning (Next 90 Days, right column)

- Heading "Why This Risk Level".
- One row per reason: the label, then an 8px bar (`bg-sunk` track) and a signed number. Red bars push risk up; green bars pull it down.
- Small print: "Contribution of each factor to the overdraft risk score (SHAP values from the hardship model)."
- A callout below, radius 16px:
  - High risk: `--critical-soft`, title "Guardian: High Risk Detected", with a "See Free Help" button.
  - Watch: `--accent-soft`, title "Suggested Next Step".
  - Low: `--accent-soft`, title "Looking Steady".

### 6.10 Time Machine

- Left column (270px, right hairline): "Gift Amount" slider, "When to Give It" options (Now / In 10 Years / As Inheritance (About 16 Years)), "Zofia Saves Each Month" slider, and the Lifetime ISA checkbox. Sliders and the selected option use `--gen3`, and the selected option is filled with `--p-tm`.
- Right column: two big percentages divided by a hairline. Deposit chance in `--gen3`, the giver's safety-floor chance in `--gen1`, each with a "+50 pts vs no gift" style change underneath. Then the two charts side by side (receiver 1.6fr, giver 1fr). Then the assumptions in small print.

### 6.11 Voice Coach

- Header aside: person picker, plus an English / Polski switch when the person speaks Polish.
- Question chips: outlined pills. Selected: `bg-ink text-surface`.
- Transcript: `bg-surface`, 1px border, radius 22px. The user's bubble is on the right in `bg-sunk`; the coach's bubble is on the left in `--p-coach`. Bubbles have radius 18px with a 5px "tail" corner. Between them, the tool call in mono, for example `→ tool call · POST /timemachine {...}`.
- "▶ Play Answer" button (`bg-ink`), with a five-bar waveform beside it that animates while speech is playing.

### 6.12 Claim Check

- A large rounded input with a "Check" button.
- Three example claims as chips.
- Verdict panel, radius 22px, filled by rating (`--critical-soft` / `--warn-soft` / `--good-soft`). It contains the label pill ("Likely Scam", "Mostly Supported, With Caveats", "Accurate", "Warning Signs Found", "Needs Evidence"), a summary, the list of signals, and sources as links.

### 6.13 Home

Two columns:
- Left: the crown (76px), "Heirloom", the tagline "Every family deserves a financial plan at the kitchen table.", then a hairline and three facts: **3** generations, one plan · **90 days** to 25 years ahead · **4** languages by voice.
- Right: three overlapping circles (radius 118, 3px stroke in the person colour, fill at 18–22%) labelled "Grandparent", "Parent" and "Young Adult", with "One Plan" where they meet. Each circle drifts gently, a few pixels over 7–9 seconds.

On load, the left column rises in with a 60ms stagger.

### 6.14 Talk to a Person dialog

A modal (shadcn `Dialog`): radius 24px, links to MoneyHelper, StepChange and Citizens Advice, and a note that in the full build the voice agent can transfer the call with the user's permission. Open it from the dock button and from the Guardian callout.

---

## 7. Motion

| Where | What | Timing |
|---|---|---|
| Page change | fade in and rise 14px | 380ms, `cubic-bezier(.2,.8,.2,1)` |
| Dock | spring magnification (6.2) | spring |
| Dock label | fade in and slide 6px | 160ms |
| Home | content rises in; circles drift | 600ms; 7–9s loops |
| Voice waveform | bars between 6px and 22px | 0.9s loop, only while speaking |
| Theme switch | background and text colour | 300ms |

Everything is disabled under `prefers-reduced-motion: reduce`.

With framer-motion, wrap the routes in `<AnimatePresence mode="wait">` and give each page:

```tsx
<motion.section
  initial={{ opacity: 0, y: 14 }}
  animate={{ opacity: 1, y: 0 }}
  exit={{ opacity: 0 }}
  transition={{ duration: 0.38, ease: [0.2, 0.8, 0.2, 1] }}
/>
```

---

## 8. State and data

```ts
// state/HeirloomContext.tsx (shape)
type HeirloomState = {
  family: "nowak" | "okafor";
  memberId: string;               // defaults to the family's parent
  night: boolean;                 // saved to localStorage("heirloom-theme")
  large: boolean;                 // adds .large to <html>
  tm: { gift: number; timing: "now" | "10y" | "inheritance"; monthly: number; lisa: boolean };
  lang: "en" | "pl";
};
```

`lib/api.ts` calls the backend endpoints from the build brief and **falls back to the local simulation** if a call fails or takes longer than about 2 seconds. That way the demo still works if the Wi-Fi drops.

| Page | Endpoint |
|---|---|
| Next 90 Days | `POST /forecast { member_id }` |
| Time Machine | `POST /timemachine { family_id, gift, timing, monthly_saving }` |
| Claim Check | `POST /claimcheck { claim }` |
| Voice Coach | `POST /ask { question, lang }` (plus the ElevenLabs agent) |

**Pin the date for the demo.** The forecast places paydays and bills relative to today's date, so the numbers shift from day to day. Use a fixed `TODAY` in demo mode so "14%, Watch" stays the same on stage.

---

## 9. Accessibility checklist

- [ ] Every dock item has a text label and works with the keyboard (Tab, Enter, visible focus ring).
- [ ] The active page has `aria-current="page"`.
- [ ] "Larger Text" scales the whole interface (use `rem`, not `px`, for type).
- [ ] Charts have `role="img"` and an `aria-label`.
- [ ] The coach transcript is an `aria-live="polite"` region.
- [ ] Colour is never the only signal: risk always has a text label too.
- [ ] Contrast stays readable in both day and night mode.
- [ ] Reduced motion is respected.

---

## 10. Copy rules

- **Title Case:** page titles, headings, labels, buttons, dock labels, pills and status names. Examples: "Next 90 Days for Tomasz", "Why This Risk Level", "See Next 90 Days", "Low Risk".
- **Sentence case:** descriptions, the coach's answers, notes and small print.
- Always say "guidance and scenarios, not regulated financial advice" somewhere visible.
- Name things the way families do: "Talk to a Person", not "Escalate"; "Next 90 Days", not "Cash-flow forecast".
