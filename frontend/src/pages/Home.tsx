import { motion, useReducedMotion } from "framer-motion";
import { ArrowRight } from "lucide-react";
import { Link } from "react-router-dom";
import { Crown } from "@/components/Crown";
import { Disclaimer, Page } from "@/components/layout/Page";

const rise = {
  hidden: { opacity: 0, y: 18 },
  show: { opacity: 1, y: 0, transition: { duration: 0.6, ease: [0.2, 0.8, 0.2, 1] } },
};

function Circles() {
  const circles = [
    { cx: 200, cy: 150, color: "var(--gen1)", label: "Grandparent", lx: 200, ly: 92, cls: "drift-a" },
    { cx: 130, cy: 270, color: "var(--gen2)", label: "Parent", lx: 96, ly: 318, cls: "drift-b" },
    { cx: 270, cy: 270, color: "var(--gen3)", label: "Young Adult", lx: 306, ly: 318, cls: "drift-c" },
  ];
  return (
    <svg viewBox="0 0 400 420" className="mx-auto w-full max-w-[460px]" role="img" aria-label="Three overlapping circles for the grandparent, parent and young adult, meeting in one plan">
      {circles.map((c) => (
        <g key={c.label} className={c.cls}>
          <circle cx={c.cx} cy={c.cy} r={118} fill={c.color} fillOpacity={0.2} stroke={c.color} strokeWidth={3} />
        </g>
      ))}
      {circles.map((c) => (
        <text key={c.label} x={c.lx} y={c.ly} textAnchor="middle" fontSize="17" fontWeight={700} fill="var(--ink)" fontFamily='"Bricolage Grotesque", system-ui'>
          {c.label}
        </text>
      ))}
      <text x={200} y={236} textAnchor="middle" fontSize="15" fontWeight={800} fill="var(--ink)" fontFamily='"Bricolage Grotesque", system-ui'>
        One Plan
      </text>
    </svg>
  );
}

export default function Home() {
  const reduced = useReducedMotion();
  return (
    <Page>
      <div className="grid min-h-[calc(100vh-220px)] grid-cols-[1.1fr_1fr] items-center gap-10 py-6 lg960:grid-cols-1">
        <motion.div initial={reduced ? false : "hidden"} animate="show" variants={{ show: { transition: { staggerChildren: 0.06 } } }}>
          <motion.div variants={rise}>
            <Crown size={76} />
          </motion.div>
          <motion.h1
            variants={rise}
            className="mt-5 font-display text-[clamp(3.8rem,10.5vw,8rem)] font-extrabold leading-[0.9] tracking-[-0.06em]"
          >
            Heirloom
          </motion.h1>
          <motion.p variants={rise} className="mt-5 max-w-[30ch] font-display text-[clamp(1.3rem,2.4vw,1.75rem)] font-semibold leading-snug tracking-[-0.02em]">
            Every family deserves a financial plan at the kitchen table.
          </motion.p>
          <motion.div variants={rise} className="mt-7 flex flex-wrap gap-3">
            <Link to="/family" className="inline-flex items-center gap-2 rounded-full bg-ink px-5 py-2.5 font-semibold text-surface no-underline hover:opacity-90">
              Meet the Family <ArrowRight className="h-4 w-4" />
            </Link>
            <Link to="/about" className="inline-flex items-center rounded-full border border-line px-5 py-2.5 font-semibold text-ink no-underline hover:bg-sunk">
              How It Works
            </Link>
          </motion.div>
          <motion.hr variants={rise} className="my-8 border-line" />
          <motion.dl variants={rise} className="grid grid-cols-3 gap-6 sm600:grid-cols-1">
            {[
              ["3", "generations, one plan"],
              ["90 days", "to 25 years ahead"],
              ["4", "languages by voice"],
            ].map(([n, t]) => (
              <div key={t}>
                <dt className="num font-display text-[2.2rem] font-extrabold leading-none tracking-[-0.035em]">{n}</dt>
                <dd className="mt-1.5 text-muted">{t}</dd>
              </div>
            ))}
          </motion.dl>
          <motion.div variants={rise}>
            <Disclaimer className="mt-8" />
          </motion.div>
        </motion.div>
        <Circles />
      </div>
    </Page>
  );
}
