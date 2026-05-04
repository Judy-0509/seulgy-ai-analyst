import { useState } from "react";
import { C, SRC_COLORS } from "../../theme";

export default function Gate2Panel({ sections, onConfirm, onClose }) {
  const [extraQuery, setExtraQuery] = useState({});

  const totalResults = sections.reduce((a, s) => a + (s.resultCount || 0), 0);
  const totalSources = new Set(sections.flatMap(s => Object.keys(s.sources || {}))).size;

  return (
    <div style={{ position: "absolute", top: 0, right: 0, bottom: 0, width: 440, background: C.card, borderLeft: `1px solid ${C.border}`, display: "flex", flexDirection: "column", animation: "slideInR 0.25s ease", zIndex: 100, boxShadow: "-8px 0 32px rgba(0,0,0,0.07)" }}>
      {/* Header */}
      <div style={{ padding: "18px 20px 16px", borderBottom: `1px solid ${C.border}`, flexShrink: 0 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: 7, marginBottom: 4 }}>
              <span style={{ fontSize: 16, color: C.amb }}>✦</span>
              <span style={{ fontSize: 13, fontWeight: 700, color: C.t1 }}>GATE 2 — 검색 결과 검토</span>
            </div>
            <p style={{ fontSize: 11, color: C.t3, margin: 0 }}>결과가 충분하면 분석 시작, 부족하면 추가 검색어 입력</p>
          </div>
          <button onClick={onClose} style={{ background: "none", border: "none", fontSize: 16, color: C.t4, cursor: "pointer", padding: 4 }}>✕</button>
        </div>
      </div>

      <div style={{ flex: 1, overflow: "auto", padding: "16px 20px" }}>
        {/* Stats */}
        <div style={{ display: "flex", gap: 10, marginBottom: 18, padding: "12px 14px", background: C.subtle, borderRadius: 9, border: `1px solid ${C.border}` }}>
          <div style={{ textAlign: "center", flex: 1 }}>
            <div style={{ fontSize: 20, fontWeight: 700, color: C.ind }}>{totalResults}</div>
            <div style={{ fontSize: 10, color: C.t4 }}>총 수집 건</div>
          </div>
          <div style={{ width: 1, background: C.border }} />
          <div style={{ textAlign: "center", flex: 1 }}>
            <div style={{ fontSize: 20, fontWeight: 700, color: C.ind }}>{sections.length}</div>
            <div style={{ fontSize: 10, color: C.t4 }}>목차 수</div>
          </div>
          <div style={{ width: 1, background: C.border }} />
          <div style={{ textAlign: "center", flex: 1 }}>
            <div style={{ fontSize: 20, fontWeight: 700, color: C.amb }}>{totalSources}</div>
            <div style={{ fontSize: 10, color: C.t4 }}>출처 기관</div>
          </div>
        </div>

        {sections.map((section, si) => {
          const srcEntries = Object.entries(section.sources || {});
          return (
            <div key={si} style={{ marginBottom: 18, padding: "12px 14px", background: C.card, border: `1px solid ${C.border}`, borderRadius: 9 }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10 }}>
                <span style={{ fontSize: 12, fontWeight: 600, color: C.t1 }}>{section.title}</span>
                <span style={{ fontSize: 11, fontWeight: 600, color: C.ind, background: C.indBg, borderRadius: 6, padding: "2px 8px" }}>{section.resultCount}건</span>
              </div>
              {/* Source bar */}
              <div style={{ height: 5, borderRadius: 99, overflow: "hidden", display: "flex", gap: 1, marginBottom: 6 }}>
                {srcEntries.map(([k, v], i) => <div key={k} style={{ flex: v, background: SRC_COLORS[i % SRC_COLORS.length] }} />)}
              </div>
              <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 10 }}>
                {srcEntries.map(([k, v], i) => (
                  <span key={k} style={{ display: "flex", alignItems: "center", gap: 4, fontSize: 10, color: C.t3 }}>
                    <span style={{ width: 7, height: 7, borderRadius: 2, background: SRC_COLORS[i % SRC_COLORS.length], display: "inline-block" }} />
                    {k} <strong style={{ color: C.t2 }}>{v}</strong>건
                  </span>
                ))}
              </div>
              {/* Key results */}
              <div style={{ display: "flex", flexDirection: "column", gap: 4, marginBottom: 10 }}>
                {(section.keyResults || []).slice(0, 3).map((r, ri) => (
                  <div key={ri} style={{ display: "flex", gap: 6, padding: "5px 8px", background: C.subtle, borderRadius: 5 }}>
                    <span style={{ fontSize: 9, fontWeight: 600, color: C.ind, background: C.indBg, borderRadius: 4, padding: "1px 5px", whiteSpace: "nowrap", alignSelf: "flex-start", marginTop: 1 }}>{r.org}</span>
                    <span style={{ fontSize: 10, color: C.t2, lineHeight: 1.4 }}>{r.title}</span>
                  </div>
                ))}
              </div>
              {/* Extra query */}
              <div style={{ display: "flex", gap: 5 }}>
                <input
                  value={extraQuery[si] || ""}
                  onChange={e => setExtraQuery(prev => ({ ...prev, [si]: e.target.value }))}
                  placeholder="추가 검색어 입력..."
                  style={{ flex: 1, border: `1px solid ${C.border}`, borderRadius: 6, padding: "5px 8px", fontSize: 10, color: C.t2, outline: "none", fontFamily: C.mono }}
                />
                <button style={{ background: C.ambBg, border: `1px solid ${C.ambBr}`, color: C.amb, borderRadius: 6, padding: "5px 9px", fontSize: 10, cursor: "pointer", fontWeight: 600 }}>재검색</button>
              </div>
            </div>
          );
        })}
      </div>

      {/* Footer */}
      <div style={{ padding: "14px 20px", borderTop: `1px solid ${C.border}`, display: "flex", gap: 8, flexShrink: 0 }}>
        <button onClick={onClose} style={{ flex: 1, padding: "9px", border: `1px solid ${C.border}`, borderRadius: 8, background: C.card, fontSize: 12, color: C.t3, cursor: "pointer" }}>취소</button>
        <button onClick={onConfirm} style={{ flex: 2, padding: "9px", border: "none", borderRadius: 8, background: "linear-gradient(135deg, #4f46e5 0%, #3730a3 100%)", fontSize: 12, fontWeight: 700, color: "#fff", cursor: "pointer" }}>분석 시작 →</button>
      </div>
    </div>
  );
}
