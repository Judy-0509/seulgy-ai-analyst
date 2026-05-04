import { C, SRC_COLORS } from "../../theme";

export default function SourceBar({ sources, h = 5, showLabels = true }) {
  const entries = Object.entries(sources);
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
      <div style={{ height: h, borderRadius: 99, overflow: "hidden", display: "flex", gap: 1 }}>
        {entries.map(([k, v], i) => (
          <div key={k} style={{ flex: v, background: SRC_COLORS[i % SRC_COLORS.length] }} />
        ))}
      </div>
      {showLabels && (
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          {entries.map(([k, v], i) => (
            <span key={k} style={{
              display: "flex", alignItems: "center", gap: 3,
              fontSize: 10, color: C.t3
            }}>
              <span style={{
                width: 6, height: 6, borderRadius: 2,
                background: SRC_COLORS[i % SRC_COLORS.length]
              }} />
              {k} {v}건
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
