import type { ReactNode } from "react";

type Props = {
  page: "family" | "forecast" | "tm" | "coach" | "claims" | "about";
  label: string;
  title: string;
  lead?: string;
  aside?: ReactNode;
};

export function PageHeader({ page, label, title, lead, aside }: Props) {
  return (
    <header
      className="mb-9 flex flex-wrap items-end justify-between gap-x-7 gap-y-5 rounded-[28px] p-[clamp(26px,4vw,44px)]"
      style={{ background: `var(--p-${page})` }}
    >
      <div className="min-w-0 max-w-[62ch]">
        <p className="mb-2 text-[.95rem] font-semibold" style={{ color: `var(--k-${page})` }}>
          {label}
        </p>
        <h1 className="font-display text-[clamp(2.1rem,4.6vw,3.3rem)] font-extrabold leading-[1.02] tracking-[-0.04em]">{title}</h1>
        {lead && <p className="mt-3 text-[1.05rem] opacity-80">{lead}</p>}
      </div>
      {aside}
    </header>
  );
}
