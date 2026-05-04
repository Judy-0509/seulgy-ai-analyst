import { useState } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { C } from "../theme";
import SparkLogo from "../components/SparkLogo";
import { useAuth } from "../contexts/AuthContext";

export default function LoginPage() {
  const nav = useNavigate();
  const location = useLocation();
  const { login, isAuthenticated } = useAuth();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const from = location.state?.from?.pathname || "/app";

  if (isAuthenticated) {
    nav(from, { replace: true });
    return null;
  }

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!username.trim() || !password.trim()) {
      setError("아이디와 비밀번호를 입력해주세요.");
      return;
    }
    setLoading(true);
    setError("");
    await new Promise(r => setTimeout(r, 600));
    login(username.trim());
    nav(from, { replace: true });
  };

  return (
    <div style={{ height: "100%", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", background: C.bg, padding: 24 }}>
      {/* Card */}
      <div style={{ width: "100%", maxWidth: 380, background: C.card, border: `1px solid ${C.border}`, borderRadius: 16, padding: "36px 32px", boxShadow: "0 8px 32px rgba(0,0,0,0.06)", animation: "fadeUp 0.3s ease" }}>
        {/* Logo */}
        <div style={{ display: "flex", justifyContent: "center", marginBottom: 28 }}>
          <SparkLogo size={32} />
        </div>

        <h1 style={{ fontSize: 18, fontWeight: 700, color: C.t1, textAlign: "center", margin: "0 0 4px", letterSpacing: "-0.02em" }}>로그인</h1>
        <p style={{ fontSize: 12, color: C.t4, textAlign: "center", margin: "0 0 28px" }}>Spark 리서치 도구에 접속합니다</p>

        <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
            <label style={{ fontSize: 11, fontWeight: 600, color: C.t3, letterSpacing: "0.03em" }}>아이디</label>
            <input
              type="text"
              value={username}
              onChange={e => setUsername(e.target.value)}
              placeholder="사용자 아이디"
              autoFocus
              style={{ border: `1.5px solid ${C.border}`, borderRadius: 9, padding: "10px 12px", fontSize: 13, color: C.t1, background: C.card, outline: "none", transition: "border-color 0.15s" }}
              onFocus={e => e.target.style.borderColor = C.ind}
              onBlur={e => e.target.style.borderColor = C.border}
            />
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
            <label style={{ fontSize: 11, fontWeight: 600, color: C.t3, letterSpacing: "0.03em" }}>비밀번호</label>
            <input
              type="password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              placeholder="비밀번호"
              style={{ border: `1.5px solid ${C.border}`, borderRadius: 9, padding: "10px 12px", fontSize: 13, color: C.t1, background: C.card, outline: "none", transition: "border-color 0.15s" }}
              onFocus={e => e.target.style.borderColor = C.ind}
              onBlur={e => e.target.style.borderColor = C.border}
            />
          </div>

          {error && (
            <div style={{ fontSize: 11, color: "#dc2626", background: "#fef2f2", border: "1px solid #fecaca", borderRadius: 7, padding: "8px 12px" }}>
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={loading}
            style={{ marginTop: 4, padding: "11px", border: "none", borderRadius: 9, background: loading ? C.indBg : "linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%)", color: loading ? C.ind : "#fff", fontSize: 13, fontWeight: 700, cursor: loading ? "default" : "pointer", transition: "opacity 0.15s" }}
          >
            {loading ? "로그인 중..." : "로그인"}
          </button>
        </form>

        <div style={{ marginTop: 20, paddingTop: 20, borderTop: `1px solid ${C.border}`, display: "flex", justifyContent: "center", gap: 16 }}>
          <button onClick={() => nav("/")} style={{ fontSize: 11, color: C.t4, background: "none", border: "none", cursor: "pointer" }}>← 홈으로</button>
          <button onClick={() => nav("/app")} style={{ fontSize: 11, color: C.ind, background: "none", border: "none", cursor: "pointer" }}>로그인 없이 시작</button>
        </div>
      </div>

      <p style={{ marginTop: 20, fontSize: 11, color: C.t4, textAlign: "center" }}>
        현재 모의 인증 모드 — 아무 값이나 입력하면 로그인됩니다
      </p>
    </div>
  );
}
