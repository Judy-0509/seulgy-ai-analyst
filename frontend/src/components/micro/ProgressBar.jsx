import { C } from "../../theme";

export default function ProgressBar({ pct, color = C.ind, h = 4, animated = false }) {
  return (
    <div style={{ height: h, background: C.subtle2, borderRadius: 99, overflow: "hidden" }}>
      <div style={{
        height: "100%", width: `${pct}%`, background: color, borderRadius: 99,
        transition: "width .9s cubic-bezier(.4,0,.2,1)", position: "relative", overflow: "hidden"
      }}>
        {animated && (
          <div style={{
            position: "absolute", inset: 0,
            background: "linear-gradient(90deg,transparent,rgba(255,255,255,.4),transparent)",
            animation: "shimmer 1.8s infinite", backgroundSize: "200% 100%"
          }} />
        )}
      </div>
    </div>
  );
}
