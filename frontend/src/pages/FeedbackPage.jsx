import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { C } from "../theme";
import { authFetch } from "../lib/authFetch";
import { useAuth } from "../contexts/AuthContext";

const DOMAIN_IDS = ["smartphone", "humanoid", "automotive", "smartglass"];
const TARGET_TYPE_IDS = ["general", "keyword", "source", "report"];
const STATUS_IDS = ["new", "reviewed", "applied", "dismissed"];

const STATUS_LABELS = { new: "신규", reviewed: "검토됨", applied: "적용됨", dismissed: "반려됨" };
const TARGET_LABELS = { general: "일반", keyword: "키워드", source: "기관·소스", report: "보고서" };

const panelStyle = {
  background: C.card,
  border: `1px solid ${C.border}`,
  borderRadius: 8,
  padding: 18,
  marginBottom: 22,
};

const buttonStyle = {
  height: 32,
  padding: "0 12px",
  borderRadius: 7,
  border: `1px solid ${C.border}`,
  background: C.subtle,
  fontSize: 12,
  fontWeight: 600,
  color: C.t2,
  cursor: "pointer",
};

const STATUS_COLORS = {
  new:       { bg: "rgba(37,99,235,.1)",  color: "#2563eb" },
  reviewed:  { bg: "rgba(234,179,8,.12)", color: "#b45309" },
  applied:   { bg: "rgba(16,185,129,.1)", color: "#059669" },
  dismissed: { bg: "rgba(107,114,128,.1)", color: "#6b7280" },
};

function StatusBadge({ status }) {
  const s = STATUS_COLORS[status] || STATUS_COLORS.new;
  return (
    <span style={{
      display: "inline-block", padding: "2px 9px", borderRadius: 99,
      fontSize: 11, fontWeight: 700,
      background: s.bg, color: s.color,
    }}>
      {STATUS_LABELS[status] || status}
    </span>
  );
}

function TargetRefPlaceholder(type) {
  if (type === "keyword") return "예: OLED, 화웨이";
  if (type === "source")  return "예: Counterpoint Research";
  if (type === "report")  return "예: 보고서 슬러그 또는 제목";
  return "";
}

export default function FeedbackPage() {
  const nav = useNavigate();
  const { isAdmin, canFeedback, roleRequested, requestAnalyst } = useAuth();

  // ── form state ──
  const [domain, setDomain]         = useState("");
  const [targetType, setTargetType] = useState("general");
  const [targetRef, setTargetRef]   = useState("");
  const [message, setMessage]       = useState("");
  const [submitStatus, setSubmitStatus] = useState("idle"); // idle | loading | ok | error
  const [submitError, setSubmitError]   = useState("");

  // ── my feedback ──
  const [mine, setMine]           = useState([]);
  const [mineStatus, setMineStatus] = useState("idle"); // idle | loading | ready | error

  // ── admin: all feedback ──
  const [filterDomain, setFilterDomain] = useState("");
  const [filterStatus, setFilterStatus] = useState("");
  const [allItems, setAllItems]   = useState([]);
  const [allStatus, setAllStatus] = useState("idle");

  // ── admin: team management ──
  const [team, setTeam]           = useState([]);
  const [teamStatus, setTeamStatus] = useState("idle");
  const [newEmail, setNewEmail]   = useState("");
  const [newName, setNewName]     = useState("");
  const [teamError, setTeamError] = useState("");

  // ── analyst access request (non-analyst) ──
  const [reqSubmitting, setReqSubmitting] = useState(false);
  const [reqDone, setReqDone]             = useState(false);

  // ── admin: pending analyst requests ──
  const [requests, setRequests]       = useState([]);
  const [requestsStatus, setRequestsStatus] = useState("idle");

  // ── admin: logged-in supabase users ──
  const [users, setUsers]         = useState([]);
  const [usersStatus, setUsersStatus] = useState("idle");
  const [usersError, setUsersError]   = useState("");

  const canAccess = canFeedback;

  const loadMine = useCallback(() => {
    setMineStatus("loading");
    authFetch("/api/feedback/mine")
      .then(r => { if (!r.ok) throw new Error(); return r.json(); })
      .then(data => { setMine(Array.isArray(data) ? data : []); setMineStatus("ready"); })
      .catch(() => setMineStatus("error"));
  }, []);

  const loadAll = useCallback(() => {
    setAllStatus("loading");
    const params = new URLSearchParams();
    if (filterDomain) params.set("domain", filterDomain);
    if (filterStatus) params.set("status", filterStatus);
    authFetch(`/api/feedback?${params}`)
      .then(r => { if (!r.ok) throw new Error(); return r.json(); })
      .then(data => { setAllItems(Array.isArray(data) ? data : []); setAllStatus("ready"); })
      .catch(() => setAllStatus("error"));
  }, [filterDomain, filterStatus]);

  const loadTeam = useCallback(() => {
    setTeamStatus("loading");
    authFetch("/api/roles/team")
      .then(r => { if (!r.ok) throw new Error(); return r.json(); })
      .then(data => { setTeam(data.team || []); setTeamStatus("ready"); })
      .catch(() => setTeamStatus("error"));
  }, []);

  const loadRequests = useCallback(() => {
    setRequestsStatus("loading");
    authFetch("/api/roles/requests")
      .then(r => { if (!r.ok) throw new Error(); return r.json(); })
      .then(data => { setRequests(data.requests || []); setRequestsStatus("ready"); })
      .catch(() => setRequestsStatus("error"));
  }, []);

  const loadUsers = useCallback(() => {
    setUsersStatus("loading");
    setUsersError("");
    authFetch("/api/auth/users")
      .then(async r => {
        if (r.status === 503) { setUsersError("service_role 키 설정이 필요합니다."); throw new Error("503"); }
        if (!r.ok) { setUsersError("불러오지 못했습니다."); throw new Error(String(r.status)); }
        return r.json();
      })
      .then(data => { setUsers(data.users || []); setUsersStatus("ready"); })
      .catch(() => setUsersStatus("error"));
  }, []);

  useEffect(() => {
    if (canAccess) void Promise.resolve().then(loadMine);
  }, [canAccess, loadMine]);

  useEffect(() => {
    if (isAdmin) {
      void Promise.resolve().then(loadAll);
      void Promise.resolve().then(loadTeam);
      void Promise.resolve().then(loadRequests);
      void Promise.resolve().then(loadUsers);
    }
  }, [isAdmin, loadAll, loadTeam, loadRequests, loadUsers]);

  const handleSubmit = () => {
    if (!message.trim()) return;
    setSubmitStatus("loading");
    setSubmitError("");
    authFetch("/api/feedback", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ domain, target_type: targetType, target_ref: targetRef, message: message.trim() }),
    })
      .then(r => { if (!r.ok) throw new Error(); return r.json(); })
      .then(() => {
        setSubmitStatus("ok");
        setMessage("");
        loadMine();
      })
      .catch(() => { setSubmitStatus("error"); setSubmitError("제출하지 못했습니다. 잠시 후 다시 시도해주세요."); });
  };

  const handleStatusChange = (fid, newStatus) => {
    authFetch(`/api/feedback/${fid}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status: newStatus }),
    })
      .then(r => { if (!r.ok) throw new Error(); return r.json(); })
      .then(loadAll)
      .catch(() => {});
  };

  const handleAddTeam = () => {
    if (!newEmail.trim()) return;
    setTeamError("");
    authFetch("/api/roles/team", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: newEmail.trim(), name: newName.trim() }),
    })
      .then(r => { if (!r.ok) throw new Error(); return r.json(); })
      .then(data => { setTeam(data.team || []); setNewEmail(""); setNewName(""); })
      .catch(() => setTeamError("추가하지 못했습니다."));
  };

  const handleRemoveTeam = (email) => {
    authFetch("/api/roles/team/remove", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email }),
    })
      .then(r => { if (!r.ok) throw new Error(); return r.json(); })
      .then(data => setTeam(data.team || []))
      .catch(() => {});
  };

  const handleRequestAnalyst = async () => {
    setReqSubmitting(true);
    try {
      const { ok } = await requestAnalyst();
      if (ok) setReqDone(true);
    } finally {
      setReqSubmitting(false);
    }
  };

  const handleApprove = (email) => {
    authFetch("/api/roles/approve", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email }),
    })
      .then(r => { if (!r.ok) throw new Error(); return r.json(); })
      .then(() => { loadRequests(); loadTeam(); loadUsers(); })
      .catch(() => {});
  };

  const handleReject = (email) => {
    authFetch("/api/roles/reject", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email }),
    })
      .then(r => { if (!r.ok) throw new Error(); return r.json(); })
      .then(() => loadRequests())
      .catch(() => {});
  };

  const handleDesignate = (email) => {
    authFetch("/api/roles/team", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email }),
    })
      .then(r => { if (!r.ok) throw new Error(); return r.json(); })
      .then(() => { loadUsers(); loadTeam(); loadRequests(); })
      .catch(() => {});
  };

  const handleRemoveUser = (email) => {
    authFetch("/api/roles/team/remove", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email }),
    })
      .then(r => { if (!r.ok) throw new Error(); return r.json(); })
      .then(() => { loadUsers(); loadTeam(); loadRequests(); })
      .catch(() => {});
  };

  const inputStyle = {
    width: "100%", boxSizing: "border-box",
    padding: "6px 10px", borderRadius: 7,
    border: `1px solid ${C.border}`, background: C.card,
    fontSize: 13, color: C.t1, outline: "none",
  };

  const selectStyle = { ...inputStyle, height: 32 };

  return (
    <div style={{ minHeight: "100vh", background: C.bg }}>
      {/* Header bar */}
      <div style={{
        background: C.card, borderBottom: `1px solid ${C.border}`,
        padding: "0 32px", display: "flex", alignItems: "center", gap: 20, height: 56,
      }}>
        <button onClick={() => nav("/")} style={buttonStyle}>
          뒤로
        </button>
        <h1 style={{ fontSize: 16, fontWeight: 700, color: C.t1, margin: 0 }}>
          피드백
        </h1>
        <span style={{ fontSize: 12, color: C.t4 }}>
          서비스 개선을 위한 의견을 남겨주세요
        </span>
      </div>

      <div style={{ maxWidth: 820, margin: "0 auto", padding: "28px 32px" }}>
        {/* No-access panel */}
        {!canAccess && (
          <section style={panelStyle}>
            <h2 style={{ fontSize: 15, fontWeight: 700, color: C.t1, margin: "0 0 8px" }}>
              애널리스트 권한이 필요합니다
            </h2>
            <p style={{ fontSize: 14, color: C.t2, margin: "0 0 14px", lineHeight: 1.6 }}>
              피드백 작성·DB·Keywords 열람은 관리자가 지정한 애널리스트만 가능합니다. 아래 버튼으로 권한을 신청하면 관리자 승인 후 이용할 수 있습니다.
            </p>
            {(roleRequested || reqDone) ? (
              <span style={{
                display: "inline-block", height: 36, lineHeight: "36px", padding: "0 16px",
                borderRadius: 8, background: C.subtle, border: `1px solid ${C.border}`,
                color: C.t3, fontSize: 13, fontWeight: 700,
              }}>
                신청 완료 — 관리자 승인 대기 중
              </span>
            ) : (
              <button
                onClick={handleRequestAnalyst}
                disabled={reqSubmitting}
                style={{
                  height: 36, padding: "0 16px", borderRadius: 8,
                  background: "#2563eb", border: "1px solid #2563eb", color: "#fff",
                  fontSize: 13, fontWeight: 700, cursor: "pointer",
                  opacity: reqSubmitting ? 0.6 : 1,
                }}
              >
                {reqSubmitting ? "신청 중..." : "애널리스트 권한 신청"}
              </button>
            )}
          </section>
        )}

        {/* Feedback form (team + admin) */}
        {canAccess && (
          <section style={panelStyle}>
            <h2 style={{ fontSize: 14, fontWeight: 700, color: C.t1, margin: "0 0 14px" }}>
              피드백
            </h2>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginBottom: 12 }}>
              <div>
                <label style={{ fontSize: 12, color: C.t3, display: "block", marginBottom: 4 }}>
                  도메인
                </label>
                <select value={domain} onChange={e => setDomain(e.target.value)} style={selectStyle}>
                  <option value="">공통</option>
                  {DOMAIN_IDS.map(d => (
                    <option key={d} value={d}>{d}</option>
                  ))}
                </select>
              </div>
              <div>
                <label style={{ fontSize: 12, color: C.t3, display: "block", marginBottom: 4 }}>
                  대상 유형
                </label>
                <select value={targetType} onChange={e => { setTargetType(e.target.value); setTargetRef(""); }} style={selectStyle}>
                  {TARGET_TYPE_IDS.map(tt => (
                    <option key={tt} value={tt}>{TARGET_LABELS[tt] || tt}</option>
                  ))}
                </select>
              </div>
            </div>

            {targetType !== "general" && (
              <div style={{ marginBottom: 12 }}>
                <label style={{ fontSize: 12, color: C.t3, display: "block", marginBottom: 4 }}>
                  대상 입력 (선택)
                </label>
                <input
                  value={targetRef}
                  onChange={e => setTargetRef(e.target.value)}
                  placeholder={TargetRefPlaceholder(targetType)}
                  style={inputStyle}
                />
              </div>
            )}

            <div style={{ marginBottom: 12 }}>
              <label style={{ fontSize: 12, color: C.t3, display: "block", marginBottom: 4 }}>
                의견
              </label>
              <textarea
                value={message}
                onChange={e => setMessage(e.target.value)}
                placeholder="개선 사항, 요청, 오류 등을 자유롭게 작성해주세요"
                rows={4}
                style={{ ...inputStyle, resize: "vertical", lineHeight: 1.6 }}
              />
            </div>

            <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
              <button
                onClick={handleSubmit}
                disabled={submitStatus === "loading" || !message.trim()}
                style={{
                  ...buttonStyle,
                  background: "#2563eb", color: "#fff",
                  border: "1px solid #2563eb",
                  opacity: (!message.trim() || submitStatus === "loading") ? 0.6 : 1,
                }}
              >
                {submitStatus === "loading" ? "..." : "제출"}
              </button>
              {submitStatus === "ok" && (
                <span style={{ fontSize: 12, color: "#059669" }}>피드백이 제출되었습니다.</span>
              )}
              {submitStatus === "error" && (
                <span style={{ fontSize: 12, color: "#ef4444" }}>{submitError}</span>
              )}
            </div>
          </section>
        )}

        {/* My feedback list */}
        {canAccess && (
          <section style={panelStyle}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
              <h2 style={{ fontSize: 14, fontWeight: 700, color: C.t1, margin: 0 }}>
                내 피드백
              </h2>
              <button onClick={loadMine} style={buttonStyle}>새로고침</button>
            </div>
            {mineStatus === "loading" && <p style={{ fontSize: 13, color: C.t4, margin: 0 }}>불러오는 중...</p>}
            {mineStatus === "error" && <p style={{ fontSize: 13, color: "#ef4444", margin: 0 }}>불러오지 못했습니다.</p>}
            {mineStatus === "ready" && mine.length === 0 && (
              <p style={{ fontSize: 13, color: C.t4, margin: 0 }}>아직 제출된 피드백이 없습니다.</p>
            )}
            {mineStatus === "ready" && mine.length > 0 && (
              <div style={{ display: "grid", gap: 8 }}>
                {mine.map(item => (
                  <div key={item.id} style={{
                    padding: "10px 12px", border: `1px solid ${C.border}`, borderRadius: 8, background: C.subtle,
                  }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 8, marginBottom: 4 }}>
                      <div style={{ fontSize: 11, color: C.t4 }}>
                        {[item.domain || "공통", (TARGET_LABELS[item.target_type] || item.target_type) + (item.target_ref ? ` · ${item.target_ref}` : "")].join(" / ")}
                      </div>
                      <StatusBadge status={item.status} />
                    </div>
                    <p style={{ fontSize: 13, color: C.t1, margin: "0 0 4px", whiteSpace: "pre-wrap" }}>{item.message}</p>
                    <div style={{ fontSize: 11, color: C.t4 }}>{(item.created_at || "").slice(0, 10)}</div>
                  </div>
                ))}
              </div>
            )}
          </section>
        )}

        {/* Admin: all feedback */}
        {isAdmin && (
          <section style={panelStyle}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12, marginBottom: 12, flexWrap: "wrap" }}>
              <h2 style={{ fontSize: 14, fontWeight: 700, color: C.t1, margin: 0 }}>
                전체 피드백
              </h2>
              <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
                <select value={filterDomain} onChange={e => setFilterDomain(e.target.value)} style={{ ...selectStyle, width: 140 }}>
                  <option value="">전체 도메인</option>
                  {DOMAIN_IDS.map(d => <option key={d} value={d}>{d}</option>)}
                </select>
                <select value={filterStatus} onChange={e => setFilterStatus(e.target.value)} style={{ ...selectStyle, width: 120 }}>
                  <option value="">전체 상태</option>
                  {STATUS_IDS.map(s => <option key={s} value={s}>{STATUS_LABELS[s] || s}</option>)}
                </select>
                <button onClick={loadAll} style={buttonStyle}>적용</button>
              </div>
            </div>
            {allStatus === "loading" && <p style={{ fontSize: 13, color: C.t4, margin: 0 }}>불러오는 중...</p>}
            {allStatus === "error" && <p style={{ fontSize: 13, color: "#ef4444", margin: 0 }}>불러오지 못했습니다.</p>}
            {allStatus === "ready" && allItems.length === 0 && (
              <p style={{ fontSize: 13, color: C.t4, margin: 0 }}>아직 제출된 피드백이 없습니다.</p>
            )}
            {allStatus === "ready" && allItems.length > 0 && (
              <div style={{ display: "grid", gap: 8 }}>
                {allItems.map(item => (
                  <div key={item.id} style={{
                    padding: "10px 12px", border: `1px solid ${C.border}`, borderRadius: 8, background: C.subtle,
                  }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 8, marginBottom: 6 }}>
                      <div>
                        <div style={{ fontSize: 13, fontWeight: 700, color: C.t1 }}>
                          {item.name || item.email}
                          {item.name && <span style={{ fontSize: 11, color: C.t4, marginLeft: 6 }}>{item.email}</span>}
                        </div>
                        <div style={{ fontSize: 11, color: C.t4, marginTop: 2 }}>
                          {[item.domain || "공통", (TARGET_LABELS[item.target_type] || item.target_type) + (item.target_ref ? ` · ${item.target_ref}` : ""), (item.created_at || "").slice(0, 10)].join(" · ")}
                        </div>
                      </div>
                      <select
                        value={item.status}
                        onChange={e => handleStatusChange(item.id, e.target.value)}
                        style={{ ...selectStyle, width: 110, flexShrink: 0 }}
                      >
                        {STATUS_IDS.map(s => <option key={s} value={s}>{STATUS_LABELS[s] || s}</option>)}
                      </select>
                    </div>
                    <p style={{ fontSize: 13, color: C.t1, margin: 0, whiteSpace: "pre-wrap" }}>{item.message}</p>
                  </div>
                ))}
              </div>
            )}
          </section>
        )}

        {/* Admin: pending analyst requests */}
        {isAdmin && (
          <section style={panelStyle}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12, marginBottom: 12 }}>
              <h2 style={{ fontSize: 14, fontWeight: 700, color: C.t1, margin: 0 }}>
                권한 신청 대기
              </h2>
              <button onClick={loadRequests} style={buttonStyle}>새로고침</button>
            </div>
            {requestsStatus === "loading" && <p style={{ fontSize: 13, color: C.t4, margin: 0 }}>불러오는 중...</p>}
            {requestsStatus === "error" && <p style={{ fontSize: 13, color: "#ef4444", margin: 0 }}>불러오지 못했습니다.</p>}
            {requestsStatus === "ready" && requests.length === 0 && (
              <p style={{ fontSize: 13, color: C.t4, margin: 0 }}>대기 중인 신청이 없습니다.</p>
            )}
            {requests.length > 0 && (
              <div style={{ display: "grid", gap: 8 }}>
                {requests.map(req => (
                  <div key={req.email} style={{
                    display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12,
                    padding: "10px 12px", border: `1px solid ${C.border}`, borderRadius: 8, background: C.subtle,
                  }}>
                    <div style={{ minWidth: 0 }}>
                      <div style={{ fontSize: 13, fontWeight: 700, color: C.t1 }}>{req.email}</div>
                      <div style={{ fontSize: 12, color: C.t4 }}>
                        {[req.name, (req.ts || "").slice(0, 10)].filter(Boolean).join(" · ")}
                      </div>
                    </div>
                    <div style={{ display: "flex", gap: 8, flexShrink: 0 }}>
                      <button
                        onClick={() => handleApprove(req.email)}
                        style={{ ...buttonStyle, background: "#2563eb", border: "1px solid #2563eb", color: "#fff" }}
                      >
                        승인
                      </button>
                      <button onClick={() => handleReject(req.email)} style={buttonStyle}>거절</button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </section>
        )}

        {/* Admin: team management */}
        {isAdmin && (
          <section style={panelStyle}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12, marginBottom: 12 }}>
              <h2 style={{ fontSize: 14, fontWeight: 700, color: C.t1, margin: 0 }}>
                팀원 관리
              </h2>
              <button onClick={loadTeam} style={buttonStyle}>새로고침</button>
            </div>

            {/* Add member form */}
            <div style={{ display: "flex", gap: 8, marginBottom: 14, flexWrap: "wrap" }}>
              <input
                value={newEmail}
                onChange={e => setNewEmail(e.target.value)}
                placeholder="이메일"
                style={{ ...inputStyle, width: 220 }}
              />
              <input
                value={newName}
                onChange={e => setNewName(e.target.value)}
                placeholder="이름 (선택)"
                style={{ ...inputStyle, width: 140 }}
              />
              <button
                onClick={handleAddTeam}
                disabled={!newEmail.trim()}
                style={{ ...buttonStyle, opacity: newEmail.trim() ? 1 : 0.5 }}
              >
                추가
              </button>
            </div>
            {teamError && <p style={{ fontSize: 12, color: "#ef4444", margin: "0 0 10px" }}>{teamError}</p>}

            {teamStatus === "loading" && <p style={{ fontSize: 13, color: C.t4, margin: 0 }}>불러오는 중...</p>}
            {teamStatus === "error" && <p style={{ fontSize: 13, color: "#ef4444", margin: 0 }}>불러오지 못했습니다.</p>}
            {teamStatus === "ready" && team.length === 0 && (
              <p style={{ fontSize: 13, color: C.t4, margin: 0 }}>등록된 팀원이 없습니다.</p>
            )}
            {team.length > 0 && (
              <div style={{ display: "grid", gap: 8 }}>
                {team.map(member => (
                  <div key={member.email} style={{
                    display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12,
                    padding: "10px 12px", border: `1px solid ${C.border}`, borderRadius: 8, background: C.subtle,
                  }}>
                    <div style={{ minWidth: 0 }}>
                      <div style={{ fontSize: 13, fontWeight: 700, color: C.t1 }}>{member.email}</div>
                      <div style={{ fontSize: 12, color: C.t4 }}>
                        {[member.name, (member.added_at || "").slice(0, 10)].filter(Boolean).join(" · ")}
                      </div>
                    </div>
                    <button onClick={() => handleRemoveTeam(member.email)} style={buttonStyle}>
                      제거
                    </button>
                  </div>
                ))}
              </div>
            )}

            {/* Logged-in supabase users picker */}
            <div style={{ marginTop: 22, paddingTop: 18, borderTop: `1px solid ${C.border}` }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12, marginBottom: 12 }}>
                <h3 style={{ fontSize: 13, fontWeight: 700, color: C.t1, margin: 0 }}>
                  로그인 사용자
                </h3>
                <button onClick={loadUsers} style={buttonStyle}>새로고침</button>
              </div>
              {usersStatus === "loading" && <p style={{ fontSize: 13, color: C.t4, margin: 0 }}>불러오는 중...</p>}
              {usersStatus === "error" && (
                <p style={{ fontSize: 13, color: "#ef4444", margin: 0 }}>{usersError || "불러오지 못했습니다."}</p>
              )}
              {usersStatus === "ready" && users.length === 0 && (
                <p style={{ fontSize: 13, color: C.t4, margin: 0 }}>로그인한 사용자가 없습니다.</p>
              )}
              {users.length > 0 && (
                <div style={{ display: "grid", gap: 8 }}>
                  {users.map(u => (
                    <div key={u.email} style={{
                      display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12,
                      padding: "10px 12px", border: `1px solid ${C.border}`, borderRadius: 8, background: C.subtle,
                    }}>
                      <div style={{ minWidth: 0 }}>
                        <div style={{ fontSize: 13, fontWeight: 700, color: C.t1 }}>{u.email}</div>
                        <div style={{ fontSize: 12, color: C.t4 }}>
                          최근 로그인 {(u.last_sign_in_at || "").slice(0, 10) || "—"}
                        </div>
                      </div>
                      <div style={{ display: "flex", alignItems: "center", gap: 8, flexShrink: 0 }}>
                        {u.role === "admin" && (
                          <span style={{ fontSize: 11, fontWeight: 700, color: C.t3 }}>관리자</span>
                        )}
                        {u.role === "team" && (
                          <button onClick={() => handleRemoveUser(u.email)} style={buttonStyle}>해제</button>
                        )}
                        {u.role === "other" && (
                          <button
                            onClick={() => handleDesignate(u.email)}
                            style={{ ...buttonStyle, background: "#2563eb", border: "1px solid #2563eb", color: "#fff" }}
                          >
                            애널리스트 지정
                          </button>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </section>
        )}
      </div>
    </div>
  );
}
