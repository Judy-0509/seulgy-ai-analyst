import { TAG_COLORS } from "../../theme";

export default function Tag({ label }) {
  const t = TAG_COLORS[label] || { bg: "#f1f5f9", c: "#475569" };
  return (
    <span style={{
      fontSize: 10, fontWeight: 600, color: t.c, background: t.bg,
      borderRadius: 6, padding: "2px 7px", whiteSpace: "nowrap"
    }}>
      {label}
    </span>
  );
}
