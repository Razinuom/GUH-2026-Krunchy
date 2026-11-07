import { FAMILIES, type FamilyId } from "@/lib/families";
import { cn } from "@/lib/utils";

export function FamilySwitch({ value, onChange }: { value: FamilyId; onChange: (f: FamilyId) => void }) {
  return (
    <div role="radiogroup" aria-label="Family" className="inline-flex shrink-0 whitespace-nowrap rounded-full border border-line bg-sunk p-[3px]">
      {(Object.keys(FAMILIES) as FamilyId[]).map((id) => {
        const on = id === value;
        return (
          <button
            key={id}
            role="radio"
            aria-checked={on}
            onClick={() => onChange(id)}
            className={cn(
              "rounded-full px-3.5 py-1.5 text-[.84rem] transition-colors sm600:px-3",
              on ? "bg-ink font-semibold text-surface" : "text-muted hover:text-ink",
            )}
          >
            {FAMILIES[id].name.replace(" Family", "")}
            <span className="sm600:hidden"> Family</span>
          </button>
        );
      })}
    </div>
  );
}
