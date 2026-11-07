/**
 * Apple-style dock (after the shadcn / motion-primitives Dock), adapted for a top bar:
 * items grow downward, labels appear below the icon, and the active page gets a filled icon plus a dot.
 */
import {
  AnimatePresence,
  motion,
  useMotionValue,
  useSpring,
  useTransform,
  type MotionValue,
  type SpringOptions,
} from "framer-motion";
import {
  Children,
  cloneElement,
  createContext,
  isValidElement,
  useContext,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
  type CSSProperties,
  type ReactElement,
  type ReactNode,
} from "react";
import { NavLink } from "react-router-dom";
import { cn } from "@/lib/utils";

const DEFAULT_MAGNIFICATION = 60; // was 80
const DEFAULT_DISTANCE = 130; // was 150
const DEFAULT_PANEL_HEIGHT = 58; // was 64
const BASE_SIZE = 44; // was 40

export function useMediaQuery(query: string) {
  const [matches, setMatches] = useState(() => typeof window !== "undefined" && window.matchMedia(query).matches);
  useEffect(() => {
    const mq = window.matchMedia(query);
    const on = () => setMatches(mq.matches);
    on();
    mq.addEventListener("change", on);
    return () => mq.removeEventListener("change", on);
  }, [query]);
  return matches;
}

type DockContextType = {
  mouseX: MotionValue<number>;
  spring: SpringOptions;
  magnification: number;
  distance: number;
  compact: boolean;
};

const DockContext = createContext<DockContextType | undefined>(undefined);

function useDock() {
  const ctx = useContext(DockContext);
  if (!ctx) throw new Error("useDock must be used within a Dock");
  return ctx;
}

type DockProps = {
  children: ReactNode;
  className?: string;
  distance?: number;
  panelHeight?: number;
  magnification?: number;
  spring?: SpringOptions;
};

export function Dock({
  children,
  className,
  spring = { mass: 0.1, stiffness: 170, damping: 16 },
  magnification = DEFAULT_MAGNIFICATION,
  distance = DEFAULT_DISTANCE,
  panelHeight = DEFAULT_PANEL_HEIGHT,
}: DockProps) {
  const mouseX = useMotionValue(Infinity);
  const reduced = useMediaQuery("(prefers-reduced-motion: reduce)");
  const compact = useMediaQuery("(max-width: 600px)");
  const magnify = reduced || compact ? BASE_SIZE : magnification;

  // Keep the outer width at the resting width so the brand and family switch don't shift.
  const panelRef = useRef<HTMLDivElement>(null);
  const [restWidth, setRestWidth] = useState<number | undefined>(undefined);
  useLayoutEffect(() => {
    const measure = () => {
      if (mouseX.get() !== Infinity || !panelRef.current) return;
      setRestWidth(panelRef.current.offsetWidth);
    };
    measure();
    window.addEventListener("resize", measure);
    return () => window.removeEventListener("resize", measure);
  }, [mouseX, compact]);

  return (
    <motion.div
      className={cn("relative flex max-w-full items-start", compact && "no-scrollbar w-full overflow-x-auto", className)}
      style={{ width: compact ? undefined : restWidth, height: panelHeight }}
    >
      <motion.div
        ref={panelRef}
        onMouseMove={({ clientX }) => mouseX.set(clientX)}
        onMouseLeave={() => mouseX.set(Infinity)}
        className={cn(
          "flex w-fit items-start gap-[10px] rounded-[22px] border border-line bg-surface px-[10px] py-[6px]",
          compact ? "mx-auto" : "absolute left-1/2 top-0 -translate-x-1/2",
        )}
        style={{ height: panelHeight }}
        role="toolbar"
        aria-label="Pages and settings"
      >
        <DockContext.Provider value={{ mouseX, spring, distance, magnification: magnify, compact }}>
          {children}
        </DockContext.Provider>
      </motion.div>
    </motion.div>
  );
}

type DockItemProps = {
  children: ReactNode;
  /** text label, used for the accessible name */
  label: string;
  to?: string;
  onClick?: () => void;
  active?: boolean;
  pressed?: boolean;
  /** page colour: fills the circle and the dot when active */
  color?: string;
  className?: string;
  style?: CSSProperties;
};

export function DockItem({ children, label, to, onClick, active, pressed, color, className, style }: DockItemProps) {
  const ref = useRef<HTMLDivElement>(null);
  const { distance, magnification, mouseX, spring } = useDock();
  const isHovered = useMotionValue(0);

  const mouseDistance = useTransform(mouseX, (val) => {
    const rect = ref.current?.getBoundingClientRect() ?? { x: 0, width: 0 };
    return val - rect.x - rect.width / 2;
  });
  const widthTransform = useTransform(mouseDistance, [-distance, 0, distance], [BASE_SIZE, magnification, BASE_SIZE]);
  const width = useSpring(widthTransform, spring);

  const focusTarget = "absolute inset-0 z-[1] rounded-full focus-visible:outline-offset-2";
  const onFocus = (e: React.FocusEvent<HTMLElement>) => {
    if (e.currentTarget.matches(":focus-visible")) isHovered.set(1);
  };
  const handlers = { onFocus, onBlur: () => isHovered.set(0), "aria-label": label };

  return (
    <motion.div
      ref={ref}
      style={{ width, ...style }}
      onHoverStart={() => isHovered.set(1)}
      onHoverEnd={() => isHovered.set(0)}
      className={cn("relative inline-flex aspect-square shrink-0 items-center justify-center rounded-full", className)}
    >
      {to !== undefined ? (
        <NavLink to={to} end className={focusTarget} aria-current={active ? "page" : undefined} {...handlers} />
      ) : (
        <button type="button" onClick={onClick} className={focusTarget} aria-pressed={pressed} {...handlers} />
      )}
      {Children.map(children, (child) =>
        isValidElement(child) ? cloneElement(child as ReactElement<{ width?: MotionValue<number>; isHovered?: MotionValue<number> }>, { width, isHovered }) : child,
      )}
      {active && (
        <span
          aria-hidden="true"
          className="absolute -bottom-[12px] left-1/2 h-[5px] w-[5px] -translate-x-1/2 rounded-full"
          style={{ background: color }}
        />
      )}
    </motion.div>
  );
}

type InjectedProps = { width?: MotionValue<number>; isHovered?: MotionValue<number> };

export function DockLabel({ children, className, ...rest }: { children: ReactNode; className?: string } & InjectedProps) {
  const { isHovered } = rest;
  const { compact } = useDock();
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    if (!isHovered) return;
    return isHovered.on("change", (v) => setVisible(v === 1));
  }, [isHovered]);

  if (compact) return null;
  return (
    <AnimatePresence>
      {visible && (
        <motion.div
          initial={{ opacity: 0, y: -6 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -6 }}
          transition={{ duration: 0.16 }}
          className={cn(
            "pointer-events-none absolute left-1/2 top-[calc(100%+12px)] z-20 whitespace-pre rounded-lg bg-ink px-2 py-1 text-[.74rem] font-semibold text-surface",
            className,
          )}
          role="tooltip"
          style={{ x: "-50%" }}
        >
          {children}
        </motion.div>
      )}
    </AnimatePresence>
  );
}

export function DockIcon({ children, className, ...rest }: { children: ReactNode; className?: string } & InjectedProps) {
  const fallback = useMotionValue(BASE_SIZE);
  const width = useTransform(rest.width ?? fallback, (v) => v / 2);
  return (
    <motion.div style={{ width, height: width }} className={cn("pointer-events-none flex items-center justify-center", className)}>
      {children}
    </motion.div>
  );
}
