import { C } from "../theme";

export function SparkIcon({ size = 28 }) {
  const r = Math.round(size * 0.26);
  return (
    <svg width={size} height={size} viewBox="0 0 28 28" fill="none" style={{ flexShrink: 0 }}>
      <rect width="28" height="28" rx={r} fill="#ffffff" stroke="rgba(45,106,45,.22)" strokeWidth="1" />
      <path d="M16.5 4L9 15.5H14.5L11.5 24L20 12H14.5L16.5 4Z" fill="url(#sg)" />
      <defs>
        <linearGradient id="sg" x1="9" y1="4" x2="20" y2="24" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stopColor="#86efac" />
          <stop offset="50%" stopColor="#2d6a2d" />
          <stop offset="100%" stopColor="#4a9e4a" />
        </linearGradient>
      </defs>
    </svg>
  );
}

export default function SparkLogo({ size = 28, textColor }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
      <SparkIcon size={size} />
      <span style={{ fontSize: size * 0.6, fontWeight: 700, color: textColor ?? C.t1, letterSpacing: "-0.035em" }}>
        Spark
      </span>
    </div>
  );
}
