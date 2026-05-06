import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { C } from "../theme";

const DOMAINS = [
  { id: "smartphone", label: "Smartphone", accent: "#10b981", accentBg: "rgba(16,185,129,.08)", accentBr: "rgba(16,185,129,.28)" },
  { id: "humanoid",   label: "Humanoid",   accent: "#b73745", accentBg: "rgba(183,55,69,.08)",  accentBr: "rgba(183,55,69,.28)"  },
  { id: "automotive", label: "Automotive", accent: "#2563eb", accentBg: "rgba(37,99,235,.08)",  accentBr: "rgba(37,99,235,.28)"  },
];

export default function KeywordsPage() {
  const nav = useNavigate();
  const [activeDomain, setActiveDomain] = useState("smartphone");
  const [allKeywords, setAllKeywords] = useState({});
  const [status, setStatus] = useState({});
  const [query, setQuery] = useState("");

  useEffect(() => {
    DOMAINS.forEach(({ id }) => {
      setStatus(prev => ({ ...prev, [id]: "loading" }));
      fetch(`/api/keywords?domain=${id}`)
        .then(r => { if (!r.ok) throw new Error(); return r.json(); })
        .then(data => {
          setAllKeywords(prev => ({ ...prev, [id]: data.keywords || [] }));
          setStatus(prev => ({ ...prev, [id]: "ready" }));
        })
        .catch(() => setStatus(prev => ({ ...prev, [id]: "error" })));
    });
  }, []);

  const domain = DOMAINS.find(d => d.id === activeDomain);
  const keywords = allKeywords[activeDomain] || [];
  const domainStatus = status[activeDomain] || "loading";

  const filtered = query
    ? keywords.filter(kw => kw.toLowerCase().includes(query.toLowerCase()))
    : keywords;

  return (
    <div style={{ minHeight: "100vh", background: C.bg }}>
      {/* Header */}
      <div style={{
        background: C.card, borderBottom: `1px solid ${C.border}`,
        padding: "0 32px", display: "flex", alignItems: "center", gap: 20, height: 56,
      }}>
        <button
          onClick={() => nav("/")}
          style={{
            height: 30, padding: "0 12px", borderRadius: 7,
            border: `1px solid ${C.border}`, background: C.subtle,
            fontSize: 12, fontWeight: 600, color: C.t2, cursor: "pointer",
          }}
        >
          ← 홈
        </button>
        <h1 style={{ fontSize: 16, fontWeight: 700, color: C.t1, margin: 0 }}>
          필터링 키워드
        </h1>
        <span style={{ fontSize: 12, color: C.t4 }}>
          아카이브 기사 필터링에 사용되는 키워드 목록
        </span>
      </div>

      {/* Domain tabs */}
      <div style={{
        background: C.card, borderBottom: `1px solid ${C.border}`,
        padding: "0 32px", display: "flex",
      }}>
        {DOMAINS.map(d => {
          const active = activeDomain === d.id;
          const count = allKeywords[d.id]?.length;
          return (
            <button
              key={d.id}
              onClick={() => { setActiveDomain(d.id); setQuery(""); }}
              style={{
                padding: "14px 22px", border: "none", background: "transparent",
                cursor: "pointer", fontSize: 13,
                fontWeight: active ? 700 : 500,
                color: active ? d.accent : C.t3,
                borderBottom: active ? `2px solid ${d.accent}` : "2px solid transparent",
                transition: "color .15s, border-color .15s",
              }}
            >
              {d.label}
              {count !== undefined && (
                <span style={{ marginLeft: 6, fontSize: 11, color: active ? d.accent : C.t4 }}>
                  {count}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {/* Content */}
      <div style={{ maxWidth: 1024, margin: "0 auto", padding: "28px 32px" }}>

        {/* Search + meta row */}
        <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 20 }}>
          <input
            value={query}
            onChange={e => setQuery(e.target.value)}
            placeholder="키워드 검색…"
            style={{
              width: 240, height: 36, padding: "0 12px", borderRadius: 8,
              border: `1px solid ${C.border}`, background: C.card,
              fontSize: 13, color: C.t1, outline: "none",
            }}
          />
          <span style={{ fontSize: 12, color: C.t4 }}>
            {domainStatus === "ready" && (
              query
                ? `${filtered.length} / ${keywords.length}개`
                : `총 ${keywords.length}개`
            )}
          </span>
        </div>

        {/* Keyword chips */}
        {domainStatus === "loading" && (
          <p style={{ fontSize: 13, color: C.t4 }}>불러오는 중…</p>
        )}
        {domainStatus === "error" && (
          <p style={{ fontSize: 13, color: "#ef4444" }}>키워드를 불러오지 못했습니다.</p>
        )}
        {domainStatus === "ready" && filtered.length === 0 && (
          <p style={{ fontSize: 13, color: C.t4 }}>
            {query ? "일치하는 키워드가 없습니다." : "키워드가 없습니다."}
          </p>
        )}
        {domainStatus === "ready" && filtered.length > 0 && (
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
            {filtered.map(kw => (
              <span
                key={kw}
                style={{
                  display: "inline-block",
                  padding: "5px 14px",
                  borderRadius: 99,
                  background: domain.accentBg,
                  border: `1px solid ${domain.accentBr}`,
                  color: C.t1,
                  fontSize: 13,
                  fontWeight: 500,
                }}
              >
                {kw}
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
