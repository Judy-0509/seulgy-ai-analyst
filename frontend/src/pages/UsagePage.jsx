import { useEffect, useState } from "react";
import { C } from "../theme";

const fmt = n => (n ?? 0).toLocaleString();
const fmtCny = n => `¥${(n ?? 0).toFixed(4)}`;

const card = {
  background: C.card,
  border: `1px solid ${C.border}`,
  borderRadius: 12,
  padding: "18px 22px",
};

const labelStyle = {
  fontSize: 11,
  fontWeight: 700,
  letterSpacing: ".06em",
  color: C.t4,
  textTransform: "uppercase",
  marginBottom: 6,
};

function StatBox({ label, value, sub }) {
  return (
    <div style={{ ...card, flex: 1, minWidth: 140 }}>
      <div style={labelStyle}>{label}</div>
      <div style={{ fontSize: 24, fontWeight: 700, color: C.t1, lineHeight: 1.2 }}>{value}</div>
      {sub && <div style={{ fontSize: 12, color: C.t3, marginTop: 4 }}>{sub}</div>}
    </div>
  );
}

export default function UsagePage() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetch("/api/usage")
      .then(r => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then(d => {
        setData(d);
        setLoading(false);
      })
      .catch(e => {
        setError(e.message);
        setLoading(false);
      });
  }, []);

  if (loading) return (
    <div style={{ height: "100vh", display: "flex", alignItems: "center", justifyContent: "center", background: C.bg }}>
      <span style={{ color: C.t3, fontSize: 14 }}>불러오는 중...</span>
    </div>
  );

  if (error) return (
    <div style={{ height: "100vh", display: "flex", alignItems: "center", justifyContent: "center", background: C.bg }}>
      <span style={{ color: "#ef4444", fontSize: 14 }}>오류: {error}</span>
    </div>
  );

  const s = data?.summary ?? {};
  const byModel = data?.by_model ?? [];
  const byDay = data?.by_day ?? [];
  const recent = data?.recent ?? [];

  return (
    <div style={{ background: C.bg, minHeight: "100vh", padding: "32px 24px" }}>
      <div style={{ maxWidth: 900, margin: "0 auto" }}>
        <div style={{ marginBottom: 28 }}>
          <h1 style={{ fontSize: 22, fontWeight: 700, color: C.t1, margin: 0 }}>API 사용량</h1>
          <p style={{ fontSize: 13, color: C.t3, margin: "6px 0 0" }}>GLM 호출 토큰 수 및 예상 비용</p>
        </div>

        <div style={{ display: "flex", gap: 12, flexWrap: "wrap", marginBottom: 24 }}>
          <StatBox label="총 호출 수" value={fmt(s.call_count)} />
          <StatBox label="총 토큰" value={fmt(s.total_tokens)} sub={`입력 ${fmt(s.total_prompt_tokens)} / 출력 ${fmt(s.total_completion_tokens)}`} />
          <StatBox label="예상 비용" value={fmtCny(s.total_cost_cny)} sub="Zhipu AI 공식 단가 기준" />
        </div>

        {byModel.length > 0 && (
          <div style={{ ...card, marginBottom: 20 }}>
            <div style={{ fontSize: 14, fontWeight: 700, color: C.t1, marginBottom: 14 }}>모델별</div>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
              <thead>
                <tr style={{ color: C.t4 }}>
                  {["모델", "호출", "입력 토큰", "출력 토큰", "비용"].map(h => (
                    <th key={h} style={{ textAlign: "left", padding: "0 8px 8px 0", fontWeight: 600, borderBottom: `1px solid ${C.border}` }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {byModel.map(m => (
                  <tr key={m.model} style={{ borderBottom: `1px solid ${C.subtle}` }}>
                    <td style={{ padding: "8px 8px 8px 0", color: C.t2, fontFamily: C.mono, fontSize: 12 }}>{m.model}</td>
                    <td style={{ padding: "8px 8px 8px 0", color: C.t2 }}>{fmt(m.calls)}</td>
                    <td style={{ padding: "8px 8px 8px 0", color: C.t2 }}>{fmt(m.prompt_tokens)}</td>
                    <td style={{ padding: "8px 8px 8px 0", color: C.t2 }}>{fmt(m.completion_tokens)}</td>
                    <td style={{ padding: "8px 8px 8px 0", color: C.ind, fontWeight: 600 }}>{fmtCny(m.cost_cny)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {byDay.length > 0 && (
          <div style={{ ...card, marginBottom: 20 }}>
            <div style={{ fontSize: 14, fontWeight: 700, color: C.t1, marginBottom: 14 }}>일별</div>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
              <thead>
                <tr style={{ color: C.t4 }}>
                  {["날짜", "호출", "토큰", "비용"].map(h => (
                    <th key={h} style={{ textAlign: "left", padding: "0 8px 8px 0", fontWeight: 600, borderBottom: `1px solid ${C.border}` }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {byDay.map(d => (
                  <tr key={d.day} style={{ borderBottom: `1px solid ${C.subtle}` }}>
                    <td style={{ padding: "8px 8px 8px 0", color: C.t2 }}>{d.day}</td>
                    <td style={{ padding: "8px 8px 8px 0", color: C.t2 }}>{fmt(d.calls)}</td>
                    <td style={{ padding: "8px 8px 8px 0", color: C.t2 }}>{fmt(d.prompt_tokens + d.completion_tokens)}</td>
                    <td style={{ padding: "8px 8px 8px 0", color: C.ind, fontWeight: 600 }}>{fmtCny(d.cost_cny)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {recent.length > 0 && (
          <div style={{ ...card }}>
            <div style={{ fontSize: 14, fontWeight: 700, color: C.t1, marginBottom: 14 }}>최근 호출 (최대 50건)</div>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
              <thead>
                <tr style={{ color: C.t4 }}>
                  {["시각", "모델", "입력", "출력", "비용", "호출처"].map(h => (
                    <th key={h} style={{ textAlign: "left", padding: "0 8px 8px 0", fontWeight: 600, borderBottom: `1px solid ${C.border}` }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {recent.map((e, i) => (
                  <tr key={`${e.ts}-${i}`} style={{ borderBottom: `1px solid ${C.subtle}` }}>
                    <td style={{ padding: "6px 8px 6px 0", color: C.t3 }}>{e.ts?.slice(0, 19).replace("T", " ")}</td>
                    <td style={{ padding: "6px 8px 6px 0", color: C.t2, fontFamily: C.mono }}>{e.model}</td>
                    <td style={{ padding: "6px 8px 6px 0", color: C.t2 }}>{fmt(e.prompt_tokens)}</td>
                    <td style={{ padding: "6px 8px 6px 0", color: C.t2 }}>{fmt(e.completion_tokens)}</td>
                    <td style={{ padding: "6px 8px 6px 0", color: C.ind }}>{fmtCny(e.cost_cny)}</td>
                    <td style={{ padding: "6px 8px 6px 0", color: C.t4, fontFamily: C.mono }}>{e.caller}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {recent.length === 0 && (
          <div style={{ ...card, textAlign: "center", color: C.t3, padding: 48 }}>
            아직 기록된 API 호출이 없습니다.
          </div>
        )}
      </div>
    </div>
  );
}
