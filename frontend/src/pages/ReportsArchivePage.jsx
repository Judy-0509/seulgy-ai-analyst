import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import Wordmark from "../components/Wordmark";

const API = "";

const A = {
  bg: "#f7f6f3",
  panel: "rgba(255,255,255,.72)",
  panelStrong: "rgba(255,255,255,.9)",
  border: "rgba(42,40,38,.09)",
  t1: "#2a2826",
  t2: "#4a4744",
  t3: "#716f6c",
  t4: "#9a9896",
  shadow: "0 12px 34px rgba(31,41,55,.08), inset 0 1px 0 rgba(255,255,255,.76)",
};

function domainColors(domain) {
  if (domain === "humanoid") return {
    em:   "#ef4444",
    emD:  "#b91c1c",
    emBg: "rgba(239,68,68,.09)",
    emBr: "rgba(239,68,68,.24)",
  };
  if (domain === "automotive") return {
    em:   "#2563eb",
    emD:  "#1d4ed8",
    emBg: "rgba(37,99,235,.09)",
    emBr: "rgba(37,99,235,.24)",
  };
  return {
    em:   "#10b981",
    emD:  "#047857",
    emBg: "rgba(16,185,129,.09)",
    emBr: "rgba(16,185,129,.24)",
  };
}

function Badge({ children, dc }) {
  return (
    <span style={{
      display: "inline-flex", alignItems: "center", height: 22, padding: "0 8px",
      borderRadius: 7, background: dc.emBg, color: dc.emD,
      border: `1px solid ${dc.emBr}`, fontSize: 11, fontWeight: 700,
    }}>
      {children}
    </span>
  );
}

function ReportCard({ report, onOpen, onDelete, deleting }) {
  const dc = domainColors(report.domain);
  const metricTags = report.metric_tags || [];

  return (
    <div style={{
      position: "relative", borderRadius: 12, background: A.panelStrong,
      border: `1px solid ${A.border}`, boxShadow: "0 1px 4px rgba(0,0,0,.03)",
      overflow: "hidden",
    }}>
      <button
        onClick={onOpen}
        style={{
          display: "block", width: "100%", textAlign: "left", cursor: "pointer",
          padding: "18px 56px 18px 20px", background: "none", border: 0,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 10, flexWrap: "wrap" }}>
          <Badge dc={dc}>{report.domain === "humanoid" ? "Humanoid" : report.domain === "automotive" ? "Automotive" : "Smartphone"}</Badge>
          <Badge dc={dc}>{report.section_count}개 섹션</Badge>
          <Badge dc={dc}>{report.reference_count}개 참고</Badge>
          <span style={{ fontSize: 11.5, color: A.t4 }}>{report.run_ts || report.modified_at}</span>
        </div>
        <h2 style={{ margin: "0 0 8px", fontSize: 17, lineHeight: 1.4, color: A.t1, letterSpacing: 0 }}>
          {report.topic}
        </h2>
        {report.summary && (
          <p style={{
            margin: "0 0 12px", fontSize: 13, color: A.t3, lineHeight: 1.65,
            display: "-webkit-box", WebkitLineClamp: 2, WebkitBoxOrient: "vertical", overflow: "hidden",
          }}>
            {report.summary}
          </p>
        )}
        {metricTags.length > 0 && (
          <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
            {metricTags.slice(0, 6).map((metric) => (
              <span key={metric} style={{
                display: "inline-flex", alignItems: "center", height: 22,
                padding: "0 8px", borderRadius: 99, background: dc.emBg,
                color: dc.emD, border: `1px solid ${dc.emBr}`,
                fontSize: 11, fontWeight: 700,
              }}>
                {metric}
              </span>
            ))}
          </div>
        )}
      </button>

      {deleting ? (
        <div style={{
          display: "flex", alignItems: "center", gap: 10, padding: "10px 20px",
          borderTop: `1px solid ${A.border}`, background: "rgba(239,68,68,.04)",
        }}>
          <span style={{ fontSize: 12.5, color: "#b91c1c", flex: 1 }}>정말 삭제하시겠습니까?</span>
          <button
            onClick={(e) => { e.stopPropagation(); onDelete(true); }}
            style={{
              border: 0, background: "#ef4444", color: "#fff",
              borderRadius: 7, padding: "5px 12px", fontSize: 12, fontWeight: 700, cursor: "pointer",
            }}
          >
            삭제
          </button>
          <button
            onClick={(e) => { e.stopPropagation(); onDelete(false); }}
            style={{
              border: `1px solid ${A.border}`, background: A.panelStrong, color: A.t2,
              borderRadius: 7, padding: "5px 12px", fontSize: 12, fontWeight: 700, cursor: "pointer",
            }}
          >
            취소
          </button>
        </div>
      ) : (
        <button
          onClick={(e) => { e.stopPropagation(); onDelete("confirm"); }}
          style={{
            position: "absolute", top: 16, right: 16,
            border: `1px solid ${A.border}`, background: A.panelStrong,
            color: A.t4, borderRadius: 7, padding: "4px 10px",
            fontSize: 11, fontWeight: 700, cursor: "pointer",
          }}
        >
          삭제
        </button>
      )}
    </div>
  );
}

export default function ReportsArchivePage() {
  const nav = useNavigate();
  const [reports, setReports] = useState([]);
  const [query, setQuery] = useState("");
  const [error, setError] = useState("");
  const [confirmSlug, setConfirmSlug] = useState(null);

  const headerDc = domainColors("smartphone");

  useEffect(() => {
    let cancelled = false;
    fetch(`${API}/api/reports`)
      .then((res) => {
        if (!res.ok) throw new Error("failed");
        return res.json();
      })
      .then((data) => {
        if (!cancelled) setReports(data.reports || []);
      })
      .catch(() => {
        if (!cancelled) setError("리포트 아카이브를 불러오지 못했습니다.");
      });
    return () => { cancelled = true; };
  }, []);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return reports;
    return reports.filter((r) =>
      `${r.topic} ${r.summary}`.toLowerCase().includes(q)
    );
  }, [reports, query]);

  function handleDelete(slug, action) {
    if (action === "confirm") {
      setConfirmSlug(slug);
      return;
    }
    if (action === false) {
      setConfirmSlug(null);
      return;
    }
    fetch(`${API}/api/reports/${encodeURIComponent(slug)}`, { method: "DELETE" })
      .then((res) => { if (!res.ok) throw new Error(); })
      .then(() => {
        setReports((prev) => prev.filter((r) => r.slug !== slug));
        setConfirmSlug(null);
      })
      .catch(() => alert("삭제에 실패했습니다."));
  }

  return (
    <main style={{
      height: "100vh", overflow: "auto", background: A.bg, color: A.t1,
      fontFamily: '"Pretendard Variable", Pretendard, Inter, -apple-system, BlinkMacSystemFont, "Helvetica Neue", sans-serif',
    }}>
      <div style={{
        position: "sticky", top: 0, zIndex: 5, height: 58, display: "flex",
        alignItems: "center", justifyContent: "space-between", padding: "0 28px",
        background: "rgba(247,246,243,.86)", backdropFilter: "blur(28px) saturate(180%)",
        WebkitBackdropFilter: "blur(28px) saturate(180%)", borderBottom: `1px solid ${A.border}`,
      }}>
        <button onClick={() => nav("/")} style={{
          border: 0, background: "none", color: A.t3, fontSize: 13,
          fontWeight: 700, cursor: "pointer", padding: 0,
        }}>
          홈
        </button>
        <button onClick={() => nav("/")} style={{ border: 0, background: "none", padding: 0, cursor: "pointer", display: "inline-flex", alignItems: "center" }} aria-label="Seulgy 홈">
          <Wordmark size={22} />
        </button>
      </div>

      <div style={{ maxWidth: 1080, margin: "0 auto", padding: "38px 20px 60px" }}>
        <section style={{
          padding: "28px 30px", borderRadius: 16, background: A.panel,
          border: `1px solid ${A.border}`, boxShadow: A.shadow, marginBottom: 18,
        }}>
          <Badge dc={headerDc}>Report Archive</Badge>
          <h1 style={{ margin: "14px 0 8px", fontSize: 30, lineHeight: 1.25, letterSpacing: 0 }}>
            과거 Executive Report
          </h1>
          <p style={{ margin: "0 0 20px", fontSize: 13.5, color: A.t3, lineHeight: 1.7 }}>
            생성된 리포트를 한 곳에서 검색하고 다시 열람합니다.
          </p>
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="주제 또는 요약 검색"
            style={{
              width: "100%", height: 42, boxSizing: "border-box", borderRadius: 10,
              border: `1px solid ${A.border}`, background: "rgba(255,255,255,.72)",
              padding: "0 14px", outline: "none", color: A.t1, fontSize: 13.5,
            }}
          />
        </section>

        {error && <p style={{ color: A.t3 }}>{error}</p>}

        <div style={{ display: "grid", gap: 12 }}>
          {filtered.map((report) => (
            <ReportCard
              key={report.slug}
              report={report}
              deleting={confirmSlug === report.slug}
              onOpen={() => nav(`/archive/${report.slug}`)}
              onDelete={(action) => handleDelete(report.slug, action)}
            />
          ))}
        </div>

        {!error && filtered.length === 0 && (
          <p style={{ margin: "28px 0 0", textAlign: "center", color: A.t4, fontSize: 13 }}>
            표시할 리포트가 없습니다.
          </p>
        )}
      </div>
    </main>
  );
}
