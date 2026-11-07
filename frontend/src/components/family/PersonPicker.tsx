import { GEN_VAR, type Member } from "@/lib/families";
import { cn } from "@/lib/utils";
import { Avatar } from "./PersonCard";

export function PersonPicker({ members, value, onChange }: { members: Member[]; value: string; onChange: (id: string) => void }) {
  return (
    <div role="radiogroup" aria-label="Family member" className="flex flex-wrap gap-2">
      {members.map((m) => {
        const on = m.id === value;
        return (
          <button
            key={m.id}
            role="radio"
            aria-checked={on}
            onClick={() => onChange(m.id)}
            className={cn(
              "inline-flex items-center gap-2 rounded-full py-1 pl-1 pr-3.5 text-[.9rem] font-medium transition-colors",
              on ? "bg-surface" : "bg-surface/65 hover:bg-surface",
            )}
            style={on ? { boxShadow: `0 0 0 2px ${GEN_VAR[m.gen]}` } : undefined}
          >
            <Avatar member={m} size={28} />
            {m.name}
          </button>
        );
      })}
    </div>
  );
}
