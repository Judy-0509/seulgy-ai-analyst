import { C } from "../theme";
import SparkLogo from "./SparkLogo";

export default function ReportModal({ data, onClose }) {
  return (
    <div
      style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.45)", zIndex: 200, display: "flex", alignItems: "center", justifyContent: "center", padding: 32, backdropFilter: "blur(4px)" }}
      onClick={e => e.target === e.currentTarget && onClose()}
    >
      <div style={{ background: C.card, borderRadius: 16, width: "min(860px, 100%)", maxHeight: "88vh", overflow: "hidden", display: "flex", flexDirection: "column", boxShadow: "0 24px 80px rgba(0,0,0,0.18)", animation: "scaleIn 0.25s ease" }}>
        {/* Header */}
        <div style={{ padding: "24px 28px 20px", borderBottom: `1px solid ${C.border}`, background: "linear-gradient(135deg, #fafaf8 0%, #f4f4f1 100%)", flexShrink: 0 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
            <div>
              <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
                <SparkLogo size={22} />
                <span style={{ fontSize: 11, color: C.t4, fontFamily: C.mono }}>Research Report</span>
                <span style={{ fontSize: 10, color: C.ind, background: C.indBg, border: `1px solid ${C.indBr}`, borderRadius: 99, padding: "1px 7px", fontWeight: 600 }}>완료</span>
              </div>
              <h2 style={{ fontSize: 17, fontWeight: 700, color: C.t1, margin: 0, lineHeight: 1.35, letterSpacing: "-0.02em" }}>{data.topic}</h2>
              <p style={{ fontSize: 11, color: C.t4, margin: "5px 0 0", fontFamily: C.mono }}>생성 시각: {data.run_ts} · 출처: Omdia · Counterpoint · IDC</p>
            </div>
            <div style={{ display: "flex", gap: 7, flexShrink: 0 }}>
              <button style={{ fontSize: 11, color: C.t3, background: C.subtle, border: `1px solid ${C.border}`, borderRadius: 7, padding: "6px 13px", cursor: "pointer" }}>PDF 저장</button>
              <button onClick={onClose} style={{ background: "none", border: "none", fontSize: 18, color: C.t4, cursor: "pointer", padding: 4 }}>✕</button>
            </div>
          </div>
        </div>

        {/* Body */}
        <div style={{ overflow: "auto", flex: 1, padding: "24px 28px" }}>
          {/* Executive Summary */}
          <section style={{ marginBottom: 28 }}>
            <h3 style={{ fontSize: 13, fontWeight: 700, color: C.ind, letterSpacing: "0.06em", textTransform: "uppercase", marginBottom: 12, display: "flex", alignItems: "center", gap: 6 }}>
              <span style={{ width: 3, height: 14, background: C.ind, borderRadius: 2, display: "inline-block" }} />
              Executive Summary
            </h3>
            <p style={{ fontSize: 13, color: C.t2, lineHeight: 1.8, background: C.subtle, borderRadius: 10, padding: "16px 18px", border: `1px solid ${C.border}`, margin: 0 }}>
              {data.executiveSummary}
            </p>
          </section>

          {/* Sections */}
          {(data.sections || []).map((sec, i) => (
            <section key={i} style={{ marginBottom: 24 }}>
              <h3 style={{ fontSize: 13, fontWeight: 700, color: C.t1, marginBottom: 8, display: "flex", alignItems: "center", gap: 8 }}>
                <span style={{ width: 22, height: 22, borderRadius: 6, background: C.indBg, border: `1px solid ${C.indBr}`, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 10, fontWeight: 700, color: C.ind, flexShrink: 0 }}>{i + 1}</span>
                {sec.title}
              </h3>
              <p style={{ fontSize: 12, color: C.t3, marginBottom: 12, padding: "8px 12px", background: C.subtle, borderRadius: 7, borderLeft: `3px solid ${C.indBr}`, lineHeight: 1.6 }}>
                {sec.angle}
              </p>
              <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                {(sec.keyResults || []).slice(0, 4).map((r, ri) => (
                  <div key={ri} style={{ display: "flex", gap: 8, padding: "8px 12px", background: C.card, border: `1px solid ${C.border}`, borderRadius: 7 }}>
                    <span style={{ fontSize: 9, fontWeight: 600, color: C.ind, background: C.indBg, borderRadius: 4, padding: "2px 6px", whiteSpace: "nowrap", alignSelf: "flex-start", marginTop: 1 }}>{r.org}</span>
                    <span style={{ fontSize: 11, color: C.t2, lineHeight: 1.5 }}>{r.title}</span>
                  </div>
                ))}
              </div>
            </section>
          ))}

          {/* Insights */}
          <section>
            <h3 style={{ fontSize: 13, fontWeight: 700, color: C.amb, letterSpacing: "0.06em", textTransform: "uppercase", marginBottom: 12, display: "flex", alignItems: "center", gap: 6 }}>
              <span style={{ width: 3, height: 14, background: C.amb, borderRadius: 2, display: "inline-block" }} />
              핵심 시사점
            </h3>
            <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
              {(data.insights || []).map((ins, i) => (
                <div key={i} style={{ padding: "16px 18px", background: C.card, border: `1px solid ${C.border}`, borderRadius: 10, borderLeft: `3px solid ${C.amb}` }}>
                  <div style={{ fontSize: 13, fontWeight: 700, color: C.t1, marginBottom: 6 }}>{i + 1}. {ins.title}</div>
                  <p style={{ fontSize: 12, color: C.t2, margin: 0, lineHeight: 1.75 }}>{ins.body}</p>
                </div>
              ))}
            </div>
          </section>
        </div>

        {/* Footer */}
        <div style={{ padding: "14px 28px", borderTop: `1px solid ${C.border}`, display: "flex", justifyContent: "flex-end", gap: 8, flexShrink: 0, background: C.subtle }}>
          <button onClick={onClose} style={{ padding: "8px 18px", border: `1px solid ${C.border}`, borderRadius: 8, background: C.card, fontSize: 12, color: C.t3, cursor: "pointer" }}>닫기</button>
          <button style={{ padding: "8px 20px", border: "none", borderRadius: 8, background: "linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%)", fontSize: 12, fontWeight: 700, color: "#fff", cursor: "pointer" }}>새 탭에서 열기 ↗</button>
        </div>
      </div>
    </div>
  );
}
