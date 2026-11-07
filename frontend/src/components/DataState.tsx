import { CloudOff } from "lucide-react";
import { snapshot } from "@/lib/api";
import type { DataSource } from "@/lib/types";
import { cn } from "@/lib/utils";

/** Says where the numbers on screen came from. */
export function SourceNote({ source, live, className }: { source: DataSource; live: string; className?: string }) {
  if (source === "live") return <p className={cn("text-[.76rem] text-muted", className)}>{live}</p>;
  return (
    <p className={cn("inline-flex items-center gap-1.5 text-[.76rem] font-medium", className)} style={{ color: "var(--warn)" }}>
      <CloudOff className="h-3.5 w-3.5" aria-hidden="true" />
      Offline snapshot: the backend is not reachable, so these are saved backend results from {snapshot.as_of}.
    </p>
  );
}

export function Loading({ label, className }: { label: string; className?: string }) {
  return (
    <p role="status" className={cn("py-10 text-center text-muted", className)}>
      {label}
    </p>
  );
}

export function ErrorNote({ message, className }: { message: string; className?: string }) {
  return (
    <div role="alert" className={cn("rounded-2xl p-5", className)} style={{ background: "var(--critical-soft)" }}>
      <p className="font-semibold" style={{ color: "var(--critical)" }}>
        Couldn&rsquo;t load this
      </p>
      <p className="mt-1 text-[.9rem]">{message}</p>
    </div>
  );
}
