import { useState } from "react";
import { C } from "../../theme";

export default function Gate1Panel({ sections, onConfirm, onClose }) {
  const [localSections, setLocalSections] = useState(
    sections.map(s => ({ ...s, queries: (s.queries || []).map(q => ({ ...q })) }))
  );
  const [newQuery, setNewQuery] = useState({});

  const toggleQuery = (si, qi) => {
    setLocalSections(prev => prev.map((s, i) => i !== si ? s : {
      ...s, queries: s.queries.map((q, j) => j !== qi ? q : { ...q, included: !q.included })
    }));
  };

  const addQuery = (si) => {
    const val = (newQuery[si] || "").trim();
    if (!val) return;
    setLocalSections(prev => prev.map((s, i) => i !== si ? s : {
      ...s, queries: [...s.queries, { text: val, included: true }]
    }));
    setNewQuery(prev => ({ ...prev, [si]: "" }));
  };

  return (
    <div style={{ position: "absolute", top: 0, right: 0, bottom: 0, width: 420, background: C.card, borderLeft: `1px solid ${C.border}`, display: "flex", flexDirection: "column", animation: "slideInR 0.25s ease", zIndex: 100, boxShadow: "-8px 0 32px rgba(0,0,0,0.07)" }}>
      {/* Header */}
      <div style={{ padding: "18px 20px 16px", borderBottom: `1px solid ${C.border}`, display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexShrink: 0 }}>
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 7, marginBottom: 4 }}>
            <span style={{ fontSize: 16, color: C.amb }}>✦</span>
            <span style={{ fontSize: 13, fontWeight: 700, color: C.t1 }}>GATE 1 — 목차 & 검색어 검토</span>
          </div>
          <p style={{ fontSize: 11, color: C.t3, margin: 0 }}>검색어 포함/제외를 선택하거나 새 검색어를 추가한 뒤 확정하세요</p>
        </div>
        <button onClick={onClose} style={{ background: "none", border: "none", fontSize: 16, color: C.t4, cursor: "pointer", padding: 4 }}>✕</button>
      </div>

      {/* Sections */}
      <div style={{ flex: 1, overflow: "auto", padding: "16px 20px" }}>
        {localSections.map((section, si) => (
          <div key={si} style={{ marginBottom: 20 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 10 }}>
              <div style={{ width: 20, height: 20, borderRadius: 5, background: C.indBg, border: `1px solid ${C.indBr}`, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 10, fontWeight: 700, color: C.ind }}>{si + 1}</div>
              <span style={{ fontSize: 12, fontWeight: 600, color: C.t1 }}>{section.title}</span>
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
              {section.queries.map((q, qi) => (
                <div key={qi} onClick={() => toggleQuery(si, qi)}
                  style={{ display: "flex", alignItems: "center", gap: 8, padding: "7px 10px", borderRadius: 7, border: `1px solid ${q.included ? C.indBr : C.border}`, background: q.included ? C.indBg : C.subtle, cursor: "pointer", transition: "all 0.15s" }}>
                  <div style={{ width: 16, height: 16, borderRadius: 4, border: `1.5px solid ${q.included ? C.ind : C.borderM}`, background: q.included ? C.ind : "transparent", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0, transition: "all 0.15s" }}>
                    {q.included && <span style={{ color: "#fff", fontSize: 9, lineHeight: 1 }}>✓</span>}
                  </div>
                  <span style={{ fontSize: 11, color: q.included ? C.t2 : C.t4, fontFamily: C.mono, lineHeight: 1.4 }}>{q.text}</span>
                </div>
              ))}
              <div style={{ display: "flex", gap: 5, marginTop: 4 }}>
                <input
                  value={newQuery[si] || ""}
                  onChange={e => setNewQuery(prev => ({ ...prev, [si]: e.target.value }))}
                  onKeyDown={e => e.key === "Enter" && addQuery(si)}
                  placeholder="검색어 추가..."
                  style={{ flex: 1, border: `1px solid ${C.border}`, borderRadius: 7, padding: "6px 9px", fontSize: 11, color: C.t2, outline: "none", fontFamily: C.mono, background: C.card }}
                />
                <button onClick={() => addQuery(si)} style={{ background: C.indBg, border: `1px solid ${C.indBr}`, color: C.ind, borderRadius: 7, padding: "6px 10px", fontSize: 11, cursor: "pointer", fontWeight: 600 }}>+</button>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Footer */}
      <div style={{ padding: "14px 20px", borderTop: `1px solid ${C.border}`, display: "flex", gap: 8, flexShrink: 0 }}>
        <button onClick={onClose} style={{ flex: 1, padding: "9px", border: `1px solid ${C.border}`, borderRadius: 8, background: C.card, fontSize: 12, color: C.t3, cursor: "pointer" }}>취소</button>
        <button onClick={() => onConfirm(localSections)} style={{ flex: 2, padding: "9px", border: "none", borderRadius: 8, background: "linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%)", fontSize: 12, fontWeight: 700, color: "#fff", cursor: "pointer" }}>확정 — 검색 시작 →</button>
      </div>
    </div>
  );
}
