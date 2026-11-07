import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "var(--bg)", surface: "var(--surface)", sunk: "var(--sunk)",
        ink: "var(--ink)", muted: "var(--muted)", line: "var(--line)",
        accent: "var(--accent)", "accent-soft": "var(--accent-soft)", "on-accent": "var(--on-accent)",
        gold: "var(--gold)",
        gen1: "var(--gen1)", gen2: "var(--gen2)", gen3: "var(--gen3)",
        good: "var(--good)", warn: "var(--warn)", critical: "var(--critical)",
        "good-soft": "var(--good-soft)", "warn-soft": "var(--warn-soft)", "critical-soft": "var(--critical-soft)",
        sel: "var(--sel)",
      },
      fontFamily: {
        display: ['"Bricolage Grotesque"', '"Segoe UI"', "system-ui", "sans-serif"],
        body: ['"IBM Plex Sans"', '"Segoe UI"', "system-ui", "sans-serif"],
        mono: ['"IBM Plex Mono"', "ui-monospace", "Menlo", "monospace"],
      },
      boxShadow: { soft: "var(--shadow)" },
      spacing: { 18: "4.5rem" },
      screens: { sm600: { max: "600px" }, md720: { max: "720px" }, lg960: { max: "960px" } },
    },
  },
  plugins: [],
} satisfies Config;
