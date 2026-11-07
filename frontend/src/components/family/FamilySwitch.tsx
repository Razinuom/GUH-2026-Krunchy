import type { FamilyId } from "@/lib/families";
import { cn } from "@/lib/utils";
import { useHeirloom } from "@/state/HeirloomContext";

export function FamilySwitch({ value, onChange }: { value: FamilyId; onChange: (f: FamilyId) => void }) {
  const { families } = useHeirloom();
  return (
    <div role="radiogroup" aria-label="Family" className="inline-flex shrink-0 whitespace-nowrap rounded-full border border-line bg-sunk p-[3px]">
      {families.map((f) => {
        const on = f.id === value;
        return (
          <button
            key={f.id}
            role="radio"
            aria-checked={on}
            onClick={() => onChange(f.id)}
            className={cn(
              "rounded-full px-3.5 py-1.5 text-[.84rem] transition-colors sm600:px-3",
              on ? "bg-ink font-semibold text-surface" : "text-muted hover:text-ink",
            )}
          >
            {f.name.replace(" Family", "")}
            <span className="sm600:hidden"> Family</span>
          </button>
        );
      })}
    </div>
  );
}
