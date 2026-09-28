import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { C } from "../theme";
import { authFetch } from "../lib/authFetch";

const DOMAIN_IDS = ["smartphone", "humanoid", "automotive", "smartglass"];
const STATUS_IDS = ["new", "reviewed", "applied", "dismissed"];
const STATUS_LABELS = { new: "신규", reviewed: "검토됨", applied: "적용됨", dismissed: "반려됨" };
const TARGET_LABELS = { general: "일반", keyword: "키워드", source: "기관·소스", report: "보고서" };
const panelStyle = {
  background: C.card, border: "1px solid " + C.border, borderRadius: 8,
  padding: 18, marginBottom: 22,
};
const buttonStyle = {
  height: 32, padding: "0 12px", borderRadius: 7,
  border: "1px solid " + C.border, background: C.subtle,
  fontSize: 12, fontWeight: 600, color: C.t2, cursor: "pointer",
};
const inputStyle = {
  width: "100%", boxSizing: "border-box", padding: "6px 10px", borderRadius: 7,
  border: "1px solid " + C.border, background: C.card,
  fontSize: 13, color: C.t1, outline: "none",
};
const selectStyle = { ...inputStyle, height: 32 };

export default function FeedbackPage() {
  const nav = useNavigate();
  const [filterDomain, setFilterDomain] = useState("");
  const [filterStatus, setFilterStatus] = useState("");
  const [allItems, setAllItems] = useState([]);
  const [allStatus, setAllStatus] = useState("idle");
  const [requests, setRequests] = useState([]);
  const [requestsStatus, setRequestsStatus] = useState("idle");
  const [team, setTeam] = useState([]);
  const [teamStatus, setTeamStatus] = useState("idle");
  const [newEmail, setNewEmail] = useState("");
  const [newName, setNewName] = useState("");
  const [teamError, setTeamError] = useState("");
  const [users, setUsers] = useState([]);
  const [usersStatus, setUsersStatus] = useState("idle");
  const [usersError, setUsersError] = useState("");

  const loadAll = useCallback(() => {
    setAllStatus("loading");
    const params = new URLSearchParams();
    if (filterDomain) params.set("domain", filterDomain);
    if (filterStatus) params.set("status", filterStatus);
    authFetch("/api/feedback?" + params)
      .then(r => { if (!r.ok) throw new Error(); return r.json(); })
      .then(data => { setAllItems(Array.isArray(data) ? data : []); setAllStatus("ready"); })
      .catch(() => setAllStatus("error"));
  }, [filterDomain, filterStatus]);

  const loadRequests = useCallback(() => {
    setRequestsStatus("loading");
    authFetch("/api/roles/requests")
      .then(r => { if (!r.ok) throw new Error(); return r.json(); })
      .then(data => { setRequests(data.requests || []); setRequestsStatus("ready"); })
      .catch(() => setRequestsStatus("error"));
  }, []);

  const loadTeam = useCallback(() => {
    setTeamStatus("loading");
    authFetch("/api/roles/team")
      .then(r => { if (!r.ok) throw new Error(); return r.json(); })
      .then(data => { setTeam(data.team || []); setTeamStatus("ready"); })
      .catch(() => setTeamStatus("error"));
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
    void Promise.resolve().then(loadAll);
    void Promise.resolve().then(loadRequests);
    void Promise.resolve().then(loadTeam);
    void Promise.resolve().then(loadUsers);
  }, [loadAll, loadRequests, loadTeam, loadUsers]);

  const postJson = (url, body) => authFetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const handleStatusChange = (id, status) => authFetch("/api/feedback/" + id, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status }),
  }).then(r => { if (!r.ok) throw new Error(); return loadAll(); }).catch(() => {});
  const handleApprove = email => postJson("/api/roles/approve", { email })
    .then(r => { if (!r.ok) throw new Error(); return Promise.all([loadRequests(), loadTeam(), loadUsers()]); }).catch(() => {});
  const handleReject = email => postJson("/api/roles/reject", { email })
    .then(r => { if (!r.ok) throw new Error(); return loadRequests(); }).catch(() => {});
  const handleAddTeam = () => {
    if (!newEmail.trim()) return;
    setTeamError("");
    postJson("/api/roles/team", { email: newEmail.trim(), name: newName.trim() })
      .then(r => { if (!r.ok) throw new Error(); return r.json(); })
      .then(data => { setTeam(data.team || []); setNewEmail(""); setNewName(""); })
      .catch(() => setTeamError("추가하지 못했습니다."));
  };
  const handleRemoveTeam = email => postJson("/api/roles/team/remove", { email })
    .then(r => { if (!r.ok) throw new Error(); return r.json(); })
    .then(data => setTeam(data.team || []))
    .catch(() => {});
  const handleDesignate = email => postJson("/api/roles/team", { email })
    .then(r => { if (!r.ok) throw new Error(); return Promise.all([loadUsers(), loadTeam(), loadRequests()]); }).catch(() => {});
  const handleRemoveUser = email => postJson("/api/roles/team/remove", { email })
    .then(r => { if (!r.ok) throw new Error(); return Promise.all([loadUsers(), loadTeam(), loadRequests()]); }).catch(() => {});

  return (
    <div style={{ minHeight: "100vh", background: C.bg }}>
      <div style={{
        background: C.card, borderBottom: "1px solid " + C.border,
        padding: "0 32px", display: "flex", alignItems: "center", gap: 20, height: 56,
      }}>
        <button onClick={() => nav("/")} style={buttonStyle}>뒤로</button>
        <h1 style={{ fontSize: 16, fontWeight: 700, color: C.t1, margin: 0 }}>피드백</h1>
        <span style={{ fontSize: 12, color: C.t4 }}>관리자 검토 및 역할 승인</span>
      </div>

      <div style={{ maxWidth: 820, margin: "0 auto", padding: "28px 32px" }}>
        <section style={panelStyle}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12, marginBottom: 12, flexWrap: "wrap" }}>
            <h2 style={{ fontSize: 14, fontWeight: 700, color: C.t1, margin: 0 }}>전체 피드백</h2>
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
          {allStatus === "ready" && allItems.length === 0 && <p style={{ fontSize: 13, color: C.t4, margin: 0 }}>아직 제출된 피드백이 없습니다.</p>}
          {allItems.length > 0 && (
            <div style={{ display: "grid", gap: 8 }}>
              {allItems.map(item => (
                <div key={item.id} style={{ padding: "10px 12px", border: "1px solid " + C.border, borderRadius: 8, background: C.subtle }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 8, marginBottom: 6 }}>
                    <div>
                      <div style={{ fontSize: 13, fontWeight: 700, color: C.t1 }}>
                        {item.name || item.email}
                        {item.name && <span style={{ fontSize: 11, color: C.t4, marginLeft: 6 }}>{item.email}</span>}
                      </div>
                      <div style={{ fontSize: 11, color: C.t4, marginTop: 2 }}>
                        {[item.domain || "공통", (TARGET_LABELS[item.target_type] || item.target_type) + (item.target_ref ? " · " + item.target_ref : ""), (item.created_at || "").slice(0, 10)].join(" · ")}
                      </div>
                    </div>
                    <select value={item.status} onChange={e => handleStatusChange(item.id, e.target.value)} style={{ ...selectStyle, width: 110, flexShrink: 0 }}>
                      {STATUS_IDS.map(s => <option key={s} value={s}>{STATUS_LABELS[s] || s}</option>)}
                    </select>
                  </div>
                  <p style={{ fontSize: 13, color: C.t1, margin: 0, whiteSpace: "pre-wrap" }}>{item.message}</p>
                </div>
              ))}
            </div>
          )}
        </section>

        <section style={panelStyle}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12, marginBottom: 12 }}>
            <h2 style={{ fontSize: 14, fontWeight: 700, color: C.t1, margin: 0 }}>애널리스트 역할 신청</h2>
            <button onClick={loadRequests} style={buttonStyle}>새로고침</button>
          </div>
          {requestsStatus === "loading" && <p style={{ fontSize: 13, color: C.t4, margin: 0 }}>불러오는 중...</p>}
          {requestsStatus === "error" && <p style={{ fontSize: 13, color: "#ef4444", margin: 0 }}>불러오지 못했습니다.</p>}
          {requestsStatus === "ready" && requests.length === 0 && <p style={{ fontSize: 13, color: C.t4, margin: 0 }}>대기 중인 신청이 없습니다.</p>}
          {requests.length > 0 && <div style={{ display: "grid", gap: 8 }}>
            {requests.map(req => (
              <div key={req.email} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12, padding: "10px 12px", border: "1px solid " + C.border, borderRadius: 8, background: C.subtle }}>
                <div style={{ minWidth: 0 }}>
                  <div style={{ fontSize: 13, fontWeight: 700, color: C.t1 }}>{req.email}</div>
                  <div style={{ fontSize: 12, color: C.t4 }}>{[req.name, (req.ts || "").slice(0, 10)].filter(Boolean).join(" · ")}</div>
                </div>
                <div style={{ display: "flex", gap: 8, flexShrink: 0 }}>
                  <button onClick={() => handleApprove(req.email)} style={{ ...buttonStyle, background: "#2563eb", border: "1px solid #2563eb", color: "#fff" }}>승인</button>
                  <button onClick={() => handleReject(req.email)} style={buttonStyle}>거절</button>
                </div>
              </div>
            ))}
          </div>}
        </section>

        <section style={panelStyle}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12, marginBottom: 12 }}>
            <h2 style={{ fontSize: 14, fontWeight: 700, color: C.t1, margin: 0 }}>팀원 관리</h2>
            <button onClick={loadTeam} style={buttonStyle}>새로고침</button>
          </div>
          <div style={{ display: "flex", gap: 8, marginBottom: 14, flexWrap: "wrap" }}>
            <input value={newEmail} onChange={e => setNewEmail(e.target.value)} placeholder="이메일" style={{ ...inputStyle, width: 220 }} />
            <input value={newName} onChange={e => setNewName(e.target.value)} placeholder="이름 (선택)" style={{ ...inputStyle, width: 140 }} />
            <button onClick={handleAddTeam} disabled={!newEmail.trim()} style={{ ...buttonStyle, opacity: newEmail.trim() ? 1 : 0.5 }}>추가</button>
          </div>
          {teamError && <p style={{ fontSize: 12, color: "#ef4444", margin: "0 0 10px" }}>{teamError}</p>}
          {teamStatus === "loading" && <p style={{ fontSize: 13, color: C.t4, margin: 0 }}>불러오는 중...</p>}
          {teamStatus === "error" && <p style={{ fontSize: 13, color: "#ef4444", margin: 0 }}>불러오지 못했습니다.</p>}
          {teamStatus === "ready" && team.length === 0 && <p style={{ fontSize: 13, color: C.t4, margin: 0 }}>등록된 팀원이 없습니다.</p>}
          {team.length > 0 && <div style={{ display: "grid", gap: 8 }}>
            {team.map(member => (
              <div key={member.email} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12, padding: "10px 12px", border: "1px solid " + C.border, borderRadius: 8, background: C.subtle }}>
                <div style={{ minWidth: 0 }}>
                  <div style={{ fontSize: 13, fontWeight: 700, color: C.t1 }}>{member.email}</div>
                  <div style={{ fontSize: 12, color: C.t4 }}>{[member.name, (member.added_at || "").slice(0, 10)].filter(Boolean).join(" · ")}</div>
                </div>
                <button onClick={() => handleRemoveTeam(member.email)} style={buttonStyle}>제거</button>
              </div>
            ))}
          </div>}

          <div style={{ marginTop: 22, paddingTop: 18, borderTop: "1px solid " + C.border }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12, marginBottom: 12 }}>
              <h3 style={{ fontSize: 13, fontWeight: 700, color: C.t1, margin: 0 }}>로그인 사용자</h3>
              <button onClick={loadUsers} style={buttonStyle}>새로고침</button>
            </div>
            {usersStatus === "loading" && <p style={{ fontSize: 13, color: C.t4, margin: 0 }}>불러오는 중...</p>}
            {usersStatus === "error" && <p style={{ fontSize: 13, color: "#ef4444", margin: 0 }}>{usersError || "불러오지 못했습니다."}</p>}
            {usersStatus === "ready" && users.length === 0 && <p style={{ fontSize: 13, color: C.t4, margin: 0 }}>로그인한 사용자가 없습니다.</p>}
            {users.length > 0 && <div style={{ display: "grid", gap: 8 }}>
              {users.map(user => (
                <div key={user.email} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12, padding: "10px 12px", border: "1px solid " + C.border, borderRadius: 8, background: C.subtle }}>
                  <div style={{ minWidth: 0 }}>
                    <div style={{ fontSize: 13, fontWeight: 700, color: C.t1 }}>{user.email}</div>
                    <div style={{ fontSize: 12, color: C.t4 }}>최근 로그인 {(user.last_sign_in_at || "").slice(0, 10) || "—"}</div>
                  </div>
                  <div style={{ display: "flex", alignItems: "center", gap: 8, flexShrink: 0 }}>
                    {user.role === "admin" && <span style={{ fontSize: 11, fontWeight: 700, color: C.t3 }}>관리자</span>}
                    {user.role === "team" && <button onClick={() => handleRemoveUser(user.email)} style={buttonStyle}>해제</button>}
                    {user.role === "other" && <button onClick={() => handleDesignate(user.email)} style={{ ...buttonStyle, background: "#2563eb", border: "1px solid #2563eb", color: "#fff" }}>애널리스트 지정</button>}
                  </div>
                </div>
              ))}
            </div>}
          </div>
        </section>
      </div>
    </div>
  );
}
