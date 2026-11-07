import { NavLink, useLocation } from "react-router-dom";
import { Activity, Home, Hourglass, Info, LifeBuoy, Mic, Moon, ShieldCheck, Sun, Type, Users } from "lucide-react";
import { Dock, DockIcon, DockItem, DockLabel } from "@/components/ui/dock";
import { Crown } from "@/components/Crown";
import { FamilySwitch } from "@/components/family/FamilySwitch";
import { useHeirloom } from "@/state/HeirloomContext";

export const PAGES = [
  { to: "/", title: "Home", icon: Home, color: "var(--gold)" },
  { to: "/family", title: "The Family", icon: Users, color: "#C77F00" },
  { to: "/forecast", title: "Next 90 Days", icon: Activity, color: "var(--gen2)" },
  { to: "/time-machine", title: "Time Machine", icon: Hourglass, color: "var(--gen3)" },
  { to: "/coach", title: "Voice Coach", icon: Mic, color: "#D9532F" },
  { to: "/claims", title: "Claim Check", icon: ShieldCheck, color: "var(--accent)" },
  { to: "/about", title: "How It Works", icon: Info, color: "var(--muted)" },
];

export function TopBar() {
  const { pathname } = useLocation();
  const { night, toggleNight, large, toggleLarge, openHelp, family, setFamily } = useHeirloom();

  return (
    <div className="sticky top-0 z-30 border-b border-line bg-surface/90 backdrop-blur-[14px] [padding-top:env(safe-area-inset-top,0px)]">
      <div
        className="mx-auto grid h-[76px] max-w-[1180px] grid-cols-[1fr_auto_1fr] items-center gap-4
                   [padding-inline:max(20px,env(safe-area-inset-left))]
                   lg960:h-auto lg960:grid-cols-[1fr_auto] lg960:gap-y-3 lg960:py-3"
      >
        <NavLink to="/" className="flex min-w-0 items-center gap-2.5 text-ink no-underline">
          <Crown size={32} />
          <span className="min-w-0">
            <strong className="block font-display text-xl font-extrabold leading-tight tracking-tight">Heirloom</strong>
            <small className="block truncate text-xs text-muted">Family Money Coach</small>
          </span>
        </NavLink>

        <div className="flex min-w-0 justify-center lg960:order-3 lg960:col-span-2">
          <Dock>
            {PAGES.map(({ to, title, icon: Icon, color }) => {
              const active = pathname === to;
              return (
                <DockItem
                  key={to}
                  to={to}
                  label={title}
                  active={active}
                  color={color}
                  style={{ background: active ? color : "var(--sunk)", color: active ? "#fff" : "var(--ink)" }}
                >
                  <DockLabel>{title}</DockLabel>
                  <DockIcon>
                    <Icon className="h-full w-full" strokeWidth={active ? 2.2 : 1.9} />
                  </DockIcon>
                </DockItem>
              );
            })}
            <span className="mx-0.5 h-[30px] w-px shrink-0 self-center bg-line" aria-hidden="true" />
            <DockItem label="Larger Text" onClick={toggleLarge} pressed={large} className={large ? "bg-ink text-surface" : "bg-sunk text-ink"}>
              <DockLabel>{large ? "Normal Text" : "Larger Text"}</DockLabel>
              <DockIcon>
                <Type className="h-full w-full" />
              </DockIcon>
            </DockItem>
            <DockItem label={night ? "Day Mode" : "Night Mode"} onClick={toggleNight} pressed={night} className="bg-sunk text-ink">
              <DockLabel>{night ? "Day Mode" : "Night Mode"}</DockLabel>
              <DockIcon>{night ? <Sun className="h-full w-full" /> : <Moon className="h-full w-full" />}</DockIcon>
            </DockItem>
            <DockItem label="Talk to a Person" onClick={openHelp} className="bg-ink text-surface">
              <DockLabel>Talk to a Person</DockLabel>
              <DockIcon>
                <LifeBuoy className="h-full w-full" />
              </DockIcon>
            </DockItem>
          </Dock>
        </div>

        <div className="flex justify-end">
          <FamilySwitch value={family} onChange={setFamily} />
        </div>
      </div>
    </div>
  );
}
