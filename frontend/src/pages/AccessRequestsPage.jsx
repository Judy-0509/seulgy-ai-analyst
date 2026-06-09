import { useState, useEffect } from "react";
import { authFetch } from "../lib/authFetch";

const PAGE_LABELS = { db: "DB", keywords: "Keywords" };

export default function AccessRequestsPage() {
  const [requests, setRequests] = useState([]);
  const [status, setStatus]     = useState("loading"); // loading | ready | empty | error
  const [approving, setApproving] = useState(null); // "email|page" being approved
  const [tick, setTick]           = useState(0); // increment to re-fetch

  useEffect(() => {
    let cancelled = false;
    Promise.resolve()
      .then(() => { if (!cancelled) setStatus("loading"); })
      .then(() => authFetch("/api/access/requests"))
      .then(res => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then(data => {
        if (cancelled) return;
        const reqs = data.requests || [];
        setRequests(reqs);
        setStatus(reqs.length === 0 ? "empty" : "ready");
      })
      .catch(() => { if (!cancelled) setStatus("error"); });
    return () => { cancelled = true; };
  }, [tick]);

  function reload() { setTick(t => t + 1); }

  async function handleApprove(email, page) {
    const key = `${email}|${page}`;
    setApproving(key);
    try {
      const res = await authFetch("/api/access/approve", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, page }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      reload();
    } catch {
      // 실패 시 목록 새로고침해 현재 상태 반영
      reload();
    } finally {
      setApproving(null);
    }
  }

  const S = {
    page: {
      minHeight: "100vh",
      background: "#07110b",
      color: "#fff",
      fontFamily: '"Cabinet Grotesk", "Pretendard Variable", Pretendard, sans-serif',
      padding: "40px clamp(16px, 4vw, 48px)",
    },
    heading: {
      fontSize: 28,
      fontWeight: 800,
      letterSpacing: "-0.03em",
      marginBottom: 8,
      color: "#fff",
    },
    sub: {
      fontSize: 13,
      color: "rgba(255,255,255,.55)",
      marginBottom: 32,
    },
    table: {
      width: "100%",
      borderCollapse: "collapse",
      background: "rgba(6,20,11,.68)",
      borderRadius: 16,
      overflow: "hidden",
      border: "1px solid rgba(255,255,255,.14)",
    },
    th: {
      textAlign: "left",
      padding: "12px 16px",
      fontSize: 11,
      fontWeight: 700,
      letterSpacing: "0.06em",
      color: "rgba(255,255,255,.45)",
      borderBottom: "1px solid rgba(255,255,255,.10)",
      textTransform: "uppercase",
    },
    td: {
      padding: "14px 16px",
      fontSize: 13,
      color: "rgba(255,255,255,.85)",
      borderBottom: "1px solid rgba(255,255,255,.07)",
    },
    approveBtn: (loading) => ({
      height: 30,
      padding: "0 14px",
      borderRadius: 99,
      border: "1px solid rgba(16,185,129,.4)",
      background: loading ? "rgba(16,185,129,.08)" : "rgba(16,185,129,.14)",
      color: "#6ee7b7",
      fontSize: 12,
      fontWeight: 700,
      cursor: loading ? "default" : "pointer",
      opacity: loading ? 0.6 : 1,
      transition: "background .15s",
    }),
    msg: {
      textAlign: "center",
      padding: "60px 0",
      color: "rgba(255,255,255,.45)",
      fontSize: 14,
    },
    reloadBtn: {
      marginTop: 12,
      height: 34,
      padding: "0 18px",
      borderRadius: 99,
      border: "1px solid rgba(255,255,255,.18)",
      background: "rgba(255,255,255,.06)",
      color: "rgba(255,255,255,.72)",
      fontSize: 12,
      fontWeight: 700,
      cursor: "pointer",
    },
  };

  return (
    <div style={S.page}>
      <h1 style={S.heading}>권한 요청 관리</h1>
      <p style={S.sub}>대기 중인 페이지 접근 권한 신청 목록입니다. 승인하면 즉시 적용됩니다.</p>

      {status === "loading" && <p style={S.msg}>불러오는 중…</p>}

      {status === "error" && (
        <div style={S.msg}>
          <p>불러오기 실패</p>
          <button style={S.reloadBtn} onClick={reload}>다시 시도</button>
        </div>
      )}

      {status === "empty" && (
        <div style={S.msg}>
          <p>대기 중인 권한 신청이 없습니다.</p>
          <button style={S.reloadBtn} onClick={reload}>새로고침</button>
        </div>
      )}

      {status === "ready" && (
        <>
          <table style={S.table}>
            <thead>
              <tr>
                <th style={S.th}>이메일</th>
                <th style={S.th}>페이지</th>
                <th style={S.th}>신청일시</th>
                <th style={S.th}></th>
              </tr>
            </thead>
            <tbody>
              {requests.map((r) => {
                const key = `${r.email}|${r.page}`;
                const isApproving = approving === key;
                return (
                  <tr key={key}>
                    <td style={S.td}>{r.email}</td>
                    <td style={S.td}>{PAGE_LABELS[r.page] ?? r.page}</td>
                    <td style={S.td}>{r.ts ? r.ts.slice(0, 19).replace("T", " ") : "-"}</td>
                    <td style={S.td}>
                      <button
                        style={S.approveBtn(isApproving)}
                        disabled={isApproving}
                        onClick={() => handleApprove(r.email, r.page)}
                      >
                        {isApproving ? "승인 중…" : "승인"}
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          <div style={{ textAlign: "right", marginTop: 12 }}>
            <button style={S.reloadBtn} onClick={reload}>새로고침</button>
          </div>
        </>
      )}
    </div>
  );
}
