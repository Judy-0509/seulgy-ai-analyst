import { C } from "../../theme";

export default function Badge({ status }) {
  const m = {
    done:    { l: "완료",    c: C.ind,  bg: C.indBg,  br: C.indBr },
    running: { l: "진행 중", c: C.ind,  bg: C.indBg,  br: C.indBr },
    waiting: { l: "대기",    c: C.t4,   bg: C.subtle, br: C.border },
    gate:    { l: "GATE",   c: C.ambD, bg: C.ambBg,  br: C.ambBr },
  };
  const s = m[status] || m.waiting;
  return (
    <span style={{
      display: "inline-flex", alignItems: "center", gap: 4, fontSize: 10, fontWeight: 600,
      letterSpacing: "0.04em", color: s.c, background: s.bg, border: `1px solid ${s.br}`,
      borderRadius: 99, padding: "2px 9px", whiteSpace: "nowrap"
    }}>
      {status === "running" && (
        <span style={{
          width: 5, height: 5, borderRadius: "50%", background: s.c,
          animation: "pulse 1.2s ease-in-out infinite"
        }} />
      )}
      {s.l}
    </span>
  );
}
