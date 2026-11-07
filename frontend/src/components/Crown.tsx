import { useId } from "react";

export function Crown({ size = 32 }: { size?: number }) {
  const gid = `crown-gold-${useId().replace(/:/g, "")}`;
  return (
    <svg width={size} height={(size * 28) / 30} viewBox="-1 0 30 28" aria-hidden="true" className="shrink-0 overflow-visible">
      <defs>
        <linearGradient id={gid} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#FFE9A8" />
          <stop offset=".55" stopColor="#E8B23E" />
          <stop offset="1" stopColor="#A9781A" />
        </linearGradient>
      </defs>
      <g fill={`url(#${gid})`}>
        <path d="M3.2 21.5 1.6 8.6c-.1-1 .9-1.5 1.6-1l5.6 4.3 4-8.4c.5-1.1 1.9-1.1 2.4 0l4 8.4 5.6-4.3c.7-.5 1.7 0 1.6 1l-1.6 12.9Z" />
        <rect x="3" y="22.4" width="22" height="4.6" rx="1.6" />
      </g>
      <rect x="3" y="22.4" width="22" height="4.6" rx="1.6" fill="#000" fillOpacity=".16" />
      <path d="M5.2 19.5 4.3 11.4 8.6 14.6" fill="none" stroke="#fff" strokeOpacity=".55" strokeWidth="1.1" strokeLinecap="round" />
      {[[2.4, 7.4, 1.8], [14, 2.4, 2.2], [25.6, 7.4, 1.8]].map(([cx, cy, r]) => (
        <circle key={cx} cx={cx} cy={cy} r={r} fill="#FFF6DC" stroke="#B98722" strokeWidth=".5" />
      ))}
      <circle cx="8.5" cy="24.7" r="1.25" fill="var(--gen1)" />
      <circle cx="14" cy="24.7" r="1.55" fill="var(--gen2)" />
      <circle cx="19.5" cy="24.7" r="1.25" fill="var(--gen3)" />
    </svg>
  );
}
