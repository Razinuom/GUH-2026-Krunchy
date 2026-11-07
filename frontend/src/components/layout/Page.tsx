import { motion, useReducedMotion } from "framer-motion";
import type { ReactNode } from "react";

/** Every page fades in and rises 14px. */
export function Page({ children }: { children: ReactNode }) {
  const reduced = useReducedMotion();
  return (
    <motion.section
      initial={reduced ? false : { opacity: 0, y: 14 }}
      animate={{ opacity: 1, y: 0 }}
      exit={reduced ? undefined : { opacity: 0 }}
      transition={{ duration: 0.38, ease: [0.2, 0.8, 0.2, 1] }}
      className="pb-18 pt-7"
    >
      {children}
    </motion.section>
  );
}

export function Disclaimer({ className = "" }: { className?: string }) {
  return (
    <p className={`text-[.76rem] text-muted ${className}`}>
      Heirloom gives guidance and scenarios, not regulated financial advice. For a personal recommendation, speak to a regulated adviser.
    </p>
  );
}
