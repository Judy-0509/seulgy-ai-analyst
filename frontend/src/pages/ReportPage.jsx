import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

const API = "";

const BASE_R = {
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

function makeR(domain) {
  if (domain === "humanoid") return {
    ...BASE_R,
    em:   "#ef4444",
    emD:  "#b91c1c",
    emBg: "rgba(239,68,68,.09)",
    emBr: "rgba(239,68,68,.24)",
  };
  if (domain === "automotive") return {
    ...BASE_R,
    em:   "#2563eb",
    emD:  "#1d4ed8",
    emBg: "rgba(37,99,235,.09)",
    emBr: "rgba(37,99,235,.24)",
  };
  // smartphone — light bg에서 LandingPage 의 forest 톤과 일관성 있게 어둡고 차분한 forest green
  return {
    ...BASE_R,
    em:   "#047857",                  // 진한 forest (LandingPage emD)
    emD:  "#065f46",                  // 더 진한 톤 (h2, link)
    emBg: "rgba(6,95,70,.06)",        // 매우 옅은 forest 틴트
    emBr: "rgba(6,95,70,.18)",        // 차분한 border
  };
}

const SOURCE_DOMAIN_ACCENTS = {
  smartphone: {
    emD: "#065f46",
    emBg: "rgba(6,95,70,.06)",
    emBr: "rgba(6,95,70,.18)",
  },
  humanoid: {
    emD: "#b91c1c",
    emBg: "rgba(239,68,68,.09)",
    emBr: "rgba(239,68,68,.24)",
  },
  automotive: {
    emD: "#1d4ed8",
    emBg: "rgba(37,99,235,.09)",
    emBr: "rgba(37,99,235,.24)",
  },
};

const SOURCE_DOMAIN_BY_NAME = {
  "DigiTimes Asia": "smartphone",
  "Counterpoint Research": "smartphone",
  "TrendForce": "smartphone",
  "Nikkei Asia": "smartphone",
  "Omdia": "smartphone",
  "IDC": "smartphone",
  "Reuters": "smartphone",
  "CCS Insight": "smartphone",
  "Yole": "smartphone",
  "Bloomberg Technology": "smartphone",
  "Gartner": "smartphone",
  "The Robot Report": "humanoid",
  "IEEE Spectrum": "humanoid",
  "TechCrunch Robotics": "humanoid",
  "MIT Technology Review": "humanoid",
  "Robotics & Automation News": "humanoid",
  "The Verge": "humanoid",
  "arXiv (cs.RO)": "humanoid",
  "NVIDIA": "humanoid",
  "Boston Dynamics": "humanoid",
  "Figure AI": "humanoid",
  "Unitree Robotics": "humanoid",
  "JATO Dynamics": "automotive",
  "Cox Automotive": "automotive",
  "AlixPartners": "automotive",
  "WardsAuto": "automotive",
  "SAE International": "automotive",
  "Automotive Dive": "automotive",
  "Automotive World": "automotive",
  "InsideEVs": "automotive",
  "Electrek": "automotive",
  "Toyota Newsroom": "automotive",
  "VW Group": "automotive",
  "Mercedes-Benz Media": "automotive",
};

function sourceAccent(sourceName, R) {
  const domain = SOURCE_DOMAIN_BY_NAME[sourceName];
  return SOURCE_DOMAIN_ACCENTS[domain] || {
    emD: R.emD,
    emBg: R.emBg,
    emBr: R.emBr,
  };
}

function SourceBadge({ children, R, accent }) {
  const A = accent || R;
  return (
    <span style={{
      display: "inline-flex", alignItems: "center", height: 20,
      padding: "0 7px", borderRadius: 6, background: A.emBg,
      color: A.emD, border: `1px solid ${A.emBr}`,
      fontSize: 10.5, fontWeight: 700, whiteSpace: "nowrap",
    }}>
      {children}
    </span>
  );
}

function MetricPill({ value, R, accent }) {
  const A = accent || R;
  return (
    <span style={{
      display: "inline-flex", alignItems: "center", height: 22,
      padding: "0 8px", borderRadius: 99, background: A.emBg,
      color: A.emD, border: `1px solid ${A.emBr}`,
      fontSize: 11, fontWeight: 700,
    }}>
      {value}
    </span>
  );
}

function ViewToggle({ value, onChange, R }) {
  const items = [
    { id: "report", label: "Report" },
    { id: "custom", label: "Custom" },
  ];
  return (
    <div style={{
      display: "inline-flex", alignItems: "center", gap: 3, padding: 3,
      borderRadius: 999, background: "rgba(42,40,38,.055)",
      border: `1px solid ${R.border}`,
    }}>
      {items.map((item) => {
        const active = value === item.id;
        return (
          <button
            key={item.id}
            type="button"
            onClick={() => onChange(item.id)}
            style={{
              border: 0, borderRadius: 999, padding: "6px 13px",
              background: active ? R.em : "transparent",
              color: active ? "#fff" : R.t3,
              fontSize: 12, fontWeight: 800, cursor: "pointer",
              transition: "background .15s, color .15s",
            }}
          >
            {item.label}
          </button>
        );
      })}
    </div>
  );
}

function ReferenceCard({ refItem, R }) {
  const accent = sourceAccent(refItem.source_name || refItem.source || "", R);
  const sectionIndices = Array.isArray(refItem.section_indices) && refItem.section_indices.length > 0
    ? refItem.section_indices
    : refItem.section_index
      ? [refItem.section_index]
      : [];
  const sectionLabel = sectionIndices.map((index) => `섹션${index}`).join(", ");

  return (
    <a
      href={refItem.url}
      target="_blank"
      rel="noopener noreferrer"
      style={{
        display: "block", padding: "13px 14px", borderRadius: 8,
        background: R.panelStrong, border: `1px solid ${R.border}`,
        boxShadow: "0 1px 3px rgba(0,0,0,.03)", textDecoration: "none",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 7, marginBottom: 8 }}>
        <SourceBadge R={R} accent={accent}>{refItem.source_name || "Source"}</SourceBadge>
        {sectionLabel && (
          <span style={{ fontSize: 10.5, color: accent.emD, fontWeight: 700 }}>
            {sectionLabel}
          </span>
        )}
        {refItem.date && <span style={{ fontSize: 10.5, color: R.t4 }}>{refItem.date}</span>}
      </div>
      <p style={{ margin: "0 0 7px", fontSize: 12.5, fontWeight: 700, color: R.t1, lineHeight: 1.45 }}>
        {refItem.title || refItem.source_name}
      </p>
      <p style={{ margin: 0, fontSize: 11.5, color: R.t3, lineHeight: 1.55 }}>
        {refItem.detail}
      </p>
      {refItem.metrics?.length > 0 && (
        <div style={{ display: "flex", flexWrap: "wrap", gap: 5, marginTop: 10 }}>
          {refItem.metrics.map((metric) => <MetricPill key={metric} value={metric} R={R} accent={accent} />)}
        </div>
      )}
    </a>
  );
}

function firstSentences(text = "", max = 2) {
  const cleaned = text.replace(/\s+/g, " ").trim();
  if (!cleaned) return "";
  const parts = cleaned.match(/[^.!?。！？]+[.!?。！？]?/g) || [cleaned];
  return parts.slice(0, max).join(" ").trim();
}

function buildResearchBackground(report) {
  if (report.research_background) return report.research_background;
  const summary = firstSentences(report.executive_summary, 2);
  if (summary) return summary;
  const sectionTitles = (report.sections || []).map((s) => s.title).filter(Boolean).slice(0, 3);
  if (sectionTitles.length > 0) {
    return `${sectionTitles.join(", ")}를 중심으로 시장 구조와 경쟁 구도 변화가 나타나고 있습니다.`;
  }
  return "시장 구조와 경쟁 구도 변화가 본격화되고 있습니다.";
}

function buildInsightSummary(insights = []) {
  return insights.map((insight) => ({
    title: insight.title,
    summary: firstSentences(insight.body, 2) || insight.title,
  }));
}

function SectionBlock({ section, R }) {
  const [open, setOpen] = useState(false);
  const bullets = section.bullets || [];
  return (
    <section style={{ padding: "28px 0", borderTop: `1px solid ${R.border}` }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 12 }}>
        <span style={{
          display: "inline-flex", alignItems: "center", justifyContent: "center",
          width: 28, height: 28, borderRadius: 8, color: R.emD, background: R.emBg,
          border: `1px solid ${R.emBr}`, fontSize: 12, fontWeight: 800,
        }}>
          {section.index}
        </span>
        <h2 style={{ margin: 0, fontSize: 20, color: R.t1, letterSpacing: 0, lineHeight: 1.35 }}>
          {section.title}
        </h2>
      </div>
      {section.headline && (
        <p style={{ margin: "0 0 14px", fontSize: 15, fontWeight: 500, color: R.emD, lineHeight: 1.55 }}>
          {section.headline}
        </p>
      )}
      {section.narrative && (
        <p style={{ margin: "0 0 16px", fontSize: 14.5, color: R.t2, lineHeight: 1.85, whiteSpace: "pre-wrap" }}>
          {section.narrative}
        </p>
      )}
      {bullets.length > 0 && (
        <>
          <button
            onClick={() => setOpen(o => !o)}
            aria-expanded={open}
            style={{
              display: "flex", alignItems: "center", gap: 8,
              margin: 0, padding: "6px 0", border: 0, background: "none",
              cursor: "pointer", color: R.t1,
            }}
          >
            <span style={{ fontSize: 13, fontWeight: 700, color: R.t1 }}>상세 수치</span>
            <span style={{ fontSize: 11, color: R.t4, fontWeight: 500 }}>{bullets.length}건</span>
            <span style={{
              fontSize: 13, color: R.emD, fontWeight: 700,
              transition: "transform 0.25s ease",
              transform: open ? "rotate(90deg)" : "rotate(0deg)",
              display: "inline-block", lineHeight: 1,
            }}>›</span>
          </button>
          <div style={{
            maxHeight: open ? "3000px" : "0px",
            opacity: open ? 1 : 0,
            overflow: "hidden",
            transition: "max-height 0.35s ease, opacity 0.2s ease",
          }}>
            <ul style={{
              margin: "8px 0 0", padding: "0 0 0 4px", listStyle: "none",
              display: "grid", gap: 8,
            }}>
              {bullets.map((bullet, index) => (
                <li key={index} style={{
                  display: "flex", alignItems: "flex-start", gap: 10,
                  fontSize: 13.5, color: R.t1, lineHeight: 1.7,
                }}>
                  <span style={{
                    color: R.emD, fontSize: 16, lineHeight: 1.4, flexShrink: 0,
                    marginTop: -1,
                  }}>•</span>
                  <span style={{ minWidth: 0 }}>{bullet}</span>
                </li>
              ))}
            </ul>
          </div>
        </>
      )}
    </section>
  );
}

function CustomSlideView({ report, R }) {
  const background = buildResearchBackground(report);
  const insightLines = buildInsightSummary(report.insights || []);
  const sections = report.sections || [];
  return (
    <article style={{
      minWidth: 0, padding: "0", background: "transparent",
      border: 0, boxShadow: "none",
    }}>
      <div style={{
        display: "grid", gridTemplateRows: "auto auto auto 1fr",
        minHeight: "calc(100vh - 168px)", gap: 12,
      }}>
        <section style={{
          padding: "18px 22px", borderRadius: 12, background: R.panelStrong,
          border: `1px solid ${R.border}`,
        }}>
          <SourceBadge R={R}>Custom Brief</SourceBadge>
          <h1 style={{ margin: "12px 0 0", fontSize: 26, lineHeight: 1.28, letterSpacing: 0, color: R.t1 }}>
            {report.topic}
          </h1>
        </section>

        <section style={{
          padding: "18px 22px", borderRadius: 12, background: R.emBg,
          border: `1px solid ${R.emBr}`,
        }}>
          <h2 style={{ margin: "0 0 8px", fontSize: 15, color: R.emD }}>조사 배경</h2>
          <p style={{ margin: 0, fontSize: 14, color: R.t2, lineHeight: 1.7 }}>{background}</p>
        </section>

        <section style={{ padding: "4px 0 0" }}>
          <h2 style={{ margin: "0 0 8px", fontSize: 14, color: R.emD }}>시사점</h2>
          <div style={{ display: "grid", gap: 10 }}>
            {(insightLines.length
              ? insightLines
              : [{ title: "시장 분석", summary: "분석 결과를 바탕으로 시장 변화와 기업 대응 방향을 요약합니다." }]
            ).map((item, index) => (
              <div key={index} style={{
                padding: "12px 14px", borderRadius: 8,
                background: R.emBg, border: `1px solid ${R.emBr}`,
              }}>
                <p style={{ margin: "0 0 5px", fontSize: 12.5, fontWeight: 800, color: R.emD, letterSpacing: "-.01em" }}>
                  {index + 1}. {item.title}
                </p>
                <p style={{ margin: 0, fontSize: 13, color: R.t2, lineHeight: 1.6 }}>
                  {item.summary}
                </p>
              </div>
            ))}
          </div>
        </section>

        <section style={{
          padding: "18px 22px", borderRadius: 12, background: R.panelStrong,
          border: `1px solid ${R.border}`, minHeight: 0,
        }}>
          <h2 style={{ margin: "0 0 14px", fontSize: 15, color: R.emD }}>핵심 분석</h2>
          <div style={{ display: "grid", gap: 10 }}>
            {sections.map((section) => (
              <div key={section.index} style={{
                padding: "15px 16px", borderRadius: 10, background: R.emBg,
                border: `1px solid ${R.emBr}`, minWidth: 0,
              }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 10 }}>
                  <span style={{
                    display: "inline-flex", alignItems: "center", justifyContent: "center",
                    width: 24, height: 24, borderRadius: 7, background: R.emBg,
                    border: `1px solid ${R.emBr}`, color: R.emD, fontSize: 11, fontWeight: 800,
                    flexShrink: 0,
                  }}>
                    {section.index}
                  </span>
                  <h3 style={{ margin: 0, fontSize: 14.5, lineHeight: 1.35, color: R.t1 }}>
                    {section.title}
                  </h3>
                </div>
                {section.headline && (
                  <p style={{ margin: "0 0 9px", fontSize: 13, fontWeight: 500, color: R.emD, lineHeight: 1.5 }}>
                    {section.headline}
                  </p>
                )}
                {section.narrative && (
                  <p style={{ margin: "0 0 10px", fontSize: 12.6, color: R.t2, lineHeight: 1.65 }}>
                    {section.narrative}
                  </p>
                )}
              </div>
            ))}
          </div>
        </section>
      </div>
    </article>
  );
}

export default function ReportPage() {
  const { slug = "" } = useParams();
  const nav = useNavigate();
  const [report, setReport] = useState(null);
  const [error, setError] = useState("");
  const [viewMode, setViewMode] = useState("report");
  const [refsOpen, setRefsOpen] = useState(true);

  useEffect(() => {
    let cancelled = false;
    fetch(`${API}/api/reports/${encodeURIComponent(slug)}`)
      .then((res) => {
        if (!res.ok) throw new Error("report not found");
        return res.json();
      })
      .then((data) => {
        if (!cancelled) setReport(data);
      })
      .catch(() => {
        if (!cancelled) setError("리포트를 불러오지 못했습니다.");
      });
    return () => { cancelled = true; };
  }, [slug]);

  const R = useMemo(() => makeR(report?.domain), [report?.domain]);
  const references = useMemo(() => report?.references || [], [report]);

  if (error) {
    return (
      <main style={{ minHeight: "100vh", background: BASE_R.bg, display: "grid", placeItems: "center", color: BASE_R.t2 }}>
        {error}
      </main>
    );
  }

  if (!report) {
    return (
      <main style={{ minHeight: "100vh", background: BASE_R.bg, display: "grid", placeItems: "center", color: BASE_R.t3 }}>
        리포트 로딩 중...
      </main>
    );
  }

  return (
    <main style={{
      height: "100vh", overflow: "auto", background: R.bg, color: R.t1,
      fontFamily: '"Apple SD Gothic Neo", -apple-system, BlinkMacSystemFont, "SF Pro Display", "SF Pro Text", "Helvetica Neue", sans-serif',
    }}>
      <div style={{
        position: "sticky", top: 0, zIndex: 5, height: 58, display: "flex",
        alignItems: "center", justifyContent: "space-between", padding: "0 28px",
        background: "rgba(247,246,243,.86)", backdropFilter: "blur(28px) saturate(180%)",
        WebkitBackdropFilter: "blur(28px) saturate(180%)", borderBottom: `1px solid ${R.border}`,
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 18 }}>
          <button onClick={() => nav("/")} style={{
            border: 0, background: "none", color: R.t3, fontSize: 13,
            fontWeight: 700, cursor: "pointer", padding: 0,
          }}>
            홈
          </button>
          <button onClick={() => nav("/archive")} style={{
            border: 0, background: "none", color: R.emD, fontSize: 13,
            fontWeight: 700, cursor: "pointer", padding: 0,
          }}>
            리포트 아카이브
          </button>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
          <ViewToggle value={viewMode} onChange={setViewMode} R={R} />
          <img src="/logo-mark.png" alt="Canopy" style={{ width: 50, height: 36, objectFit: "contain" }} />
        </div>
      </div>

      <div style={{
        maxWidth: 1440, margin: "0 auto", padding: "34px 18px 54px",
        display: "grid", gridTemplateColumns: "minmax(0, 1fr) 380px", gap: 22,
      }}>
        {viewMode === "custom" ? (
          <CustomSlideView report={report} R={R} />
        ) : (
          <article style={{
            minWidth: 0, padding: "36px 44px", borderRadius: 16, background: R.panel,
            border: `1px solid ${R.border}`, boxShadow: R.shadow,
          }}>
            <div style={{ marginBottom: 28 }}>
              <SourceBadge R={R}>Executive Report</SourceBadge>
              <h1 style={{ margin: "14px 0 10px", fontSize: 30, lineHeight: 1.28, letterSpacing: 0, color: R.t1 }}>
                {report.topic}
              </h1>
              {report.run_ts && <p style={{ margin: 0, fontSize: 12, color: R.t4 }}>{report.run_ts}</p>}
            </div>

            {report.executive_summary && (
              <section style={{
                padding: "20px 22px", borderRadius: 12, background: R.emBg,
                border: `1px solid ${R.emBr}`, marginBottom: 10,
              }}>
                <h2 style={{ margin: "0 0 10px", fontSize: 16, color: R.emD }}>Executive Summary</h2>
                <p style={{ margin: 0, fontSize: 14.5, color: R.t2, lineHeight: 1.85 }}>
                  {report.executive_summary}
                </p>
              </section>
            )}

            {report.sections.map((section) => (
              <SectionBlock key={section.index} section={section} R={R} />
            ))}

            {report.insights?.length > 0 && (
              <section style={{ paddingTop: 30, borderTop: `1px solid ${R.border}` }}>
                <h2 style={{ margin: "0 0 16px", fontSize: 20, color: R.t1 }}>Market Insights</h2>
                <div style={{ display: "grid", gap: 14 }}>
                  {report.insights.map((insight, index) => (
                    <div key={index} style={{
                      padding: "17px 18px", borderRadius: 10,
                      background: R.panelStrong, border: `1px solid ${R.border}`,
                    }}>
                      <h3 style={{ margin: "0 0 8px", fontSize: 15, color: R.emD }}>
                        {index + 1}. {insight.title}
                      </h3>
                      <p style={{ margin: 0, fontSize: 13.5, color: R.t2, lineHeight: 1.75 }}>
                        {insight.body}
                      </p>
                    </div>
                  ))}
                </div>
              </section>
            )}
          </article>
        )}

        <aside style={{ position: "sticky", top: 78, alignSelf: "start", maxHeight: "calc(100vh - 98px)", overflow: "auto" }}>
          <div style={{
            padding: "18px", borderRadius: 14, background: R.panel,
            border: `1px solid ${R.border}`, boxShadow: R.shadow,
          }}>
            <button
              onClick={() => setRefsOpen(o => !o)}
              aria-expanded={refsOpen}
              style={{
                display: "flex", alignItems: "center", justifyContent: "space-between",
                width: "100%", margin: 0, padding: 0, border: 0, background: "none",
                textAlign: "left", cursor: "pointer", color: R.t1,
              }}
            >
              <span style={{
                display: "flex", alignItems: "baseline", gap: 8, minWidth: 0,
              }}>
                <span style={{ fontSize: 15, fontWeight: 700, color: R.t1 }}>참고 수치</span>
                <span style={{ fontSize: 11, color: R.t4, fontWeight: 500 }}>
                  {references.length}건
                </span>
              </span>
              <span style={{
                fontSize: 13, color: R.emD, fontWeight: 700,
                transition: "transform 0.25s ease",
                transform: refsOpen ? "rotate(90deg)" : "rotate(0deg)",
                display: "inline-block", lineHeight: 1, marginLeft: 8,
              }}>
                ›
              </span>
            </button>
            {/* 펼침 영역 — max-height 슬라이딩 */}
            <div style={{
              maxHeight: refsOpen ? "5000px" : "0px",
              opacity: refsOpen ? 1 : 0,
              overflow: "hidden",
              transition: "max-height 0.35s ease, opacity 0.2s ease",
            }}>
              <p style={{ margin: "8px 0 14px", fontSize: 11.5, color: R.t4 }}>
                본문에 사용된 링크와 해당 근거
              </p>
              <div style={{ display: "grid", gap: 10 }}>
                {references.map((refItem, index) => (
                  <ReferenceCard key={`${refItem.url}-${index}`} refItem={refItem} R={R} />
                ))}
              </div>
            </div>
          </div>
        </aside>
      </div>
    </main>
  );
}
