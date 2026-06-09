import { useEffect, useState } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { C } from "../theme";
import { useAuth } from "../contexts/AuthContext";
import { supabaseConfigured } from "../lib/supabase";
import Wordmark from "../components/Wordmark";

export default function LoginPage() {
  const nav = useNavigate();
  const location = useLocation();
  const { signInWithGoogle, isAuthenticated } = useAuth();

  const [error, setError]   = useState("");
  const [loading, setLoading] = useState(false);
  const [shake, setShake]   = useState(false);

  const from = location.state?.from?.pathname || "/archive";

  useEffect(() => {
    if (isAuthenticated) nav(from, { replace: true });
  }, [isAuthenticated, nav, from]);

  function _triggerShake(msg) {
    setError(msg);
    setShake(true);
    setTimeout(() => setShake(false), 500);
  }

  async function handleGoogle() {
    setLoading(true);
    setError("");
    const result = await signInWithGoogle();
    if (!result.ok) {
      setLoading(false);
      _triggerShake(result.error || "Google 로그인에 실패했습니다.");
    }
    // 성공 시 Google로 리디렉트되므로 여기서 상태를 더 바꾸지 않는다.
  }

  // Supabase 미설정 안내
  if (!supabaseConfigured) {
    return (
      <div style={{
        height: "100%", display: "flex", alignItems: "center", justifyContent: "center",
        background: C.bg,
        fontFamily: '"Pretendard Variable", Pretendard, Inter, -apple-system, BlinkMacSystemFont, "Helvetica Neue", sans-serif',
      }}>
        <div style={{ width: "100%", maxWidth: 400 }}>
          <div style={{ display: "flex", justifyContent: "center", marginBottom: 36 }}>
            <Wordmark size={42} />
          </div>
          <div style={{
            background: C.card, border: `1px solid ${C.border}`,
            borderRadius: 16, padding: "36px 32px 32px",
            boxShadow: "0 2px 16px rgba(0,0,0,0.06)",
          }}>
            <p style={{ margin: "0 0 8px", fontSize: 13, fontWeight: 700, color: C.t1, textAlign: "center" }}>
              Supabase 설정 필요
            </p>
            <p style={{ margin: "0 0 20px", fontSize: 13, color: C.t3, textAlign: "center", lineHeight: 1.6 }}>
              로그인을 사용하려면 Supabase 프로젝트를 연결해야 합니다.
              <br />
              <code style={{ fontSize: 11, background: C.subtle2, borderRadius: 4, padding: "2px 6px" }}>supabase/README.md</code>
              &nbsp;를 참고하세요.
            </p>
            <button
              onClick={() => nav("/")}
              style={{
                width: "100%", height: 46, border: "none", borderRadius: 10,
                background: C.t1, color: "#fff",
                fontSize: 13, fontWeight: 700, cursor: "pointer",
              }}
            >
              홈으로
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <>
      <style>{`
        @keyframes fadeUp {
          from { opacity: 0; transform: translateY(14px); }
          to   { opacity: 1; transform: translateY(0); }
        }
        @keyframes shake {
          0%,100% { transform: translateX(0); }
          20%      { transform: translateX(-7px); }
          40%      { transform: translateX(7px); }
          60%      { transform: translateX(-5px); }
          80%      { transform: translateX(5px); }
        }
        .otp-input::placeholder { color: #c8c6c2; letter-spacing: 0; }
        .otp-input:focus { border-color: ${C.t2} !important; }
        .submit-btn:hover:not(:disabled) { opacity: 0.82; }
      `}</style>

      <div style={{
        height: "100%", display: "flex", alignItems: "center", justifyContent: "center",
        background: C.bg,
        fontFamily: '"Pretendard Variable", Pretendard, Inter, -apple-system, BlinkMacSystemFont, "Helvetica Neue", sans-serif',
      }}>
        <div style={{ width: "100%", maxWidth: 360, animation: "fadeUp 0.35s ease" }}>
          {/* Logo */}
          <div style={{ display: "flex", justifyContent: "center", marginBottom: 36 }}>
            <Wordmark size={42} />
          </div>

          {/* Card */}
          <div style={{
            background: C.card,
            border: `1px solid ${C.border}`,
            borderRadius: 16,
            padding: "36px 32px 32px",
            boxShadow: "0 2px 16px rgba(0,0,0,0.06)",
            animation: shake ? "shake 0.45s ease" : "none",
          }}>
            <p style={{
              margin: "0 0 20px", fontSize: 11, fontWeight: 600,
              color: C.t4, letterSpacing: "0.08em", textTransform: "uppercase", textAlign: "center",
            }}>
              로그인
            </p>
            <button
              type="button"
              onClick={handleGoogle}
              disabled={loading}
              style={{
                width: "100%", boxSizing: "border-box", height: 46,
                display: "flex", alignItems: "center", justifyContent: "center", gap: 10,
                border: `1.5px solid ${C.border}`, borderRadius: 10,
                background: C.card, color: C.t1,
                fontSize: 13, fontWeight: 600,
                cursor: loading ? "default" : "pointer",
              }}
            >
              <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true">
                <path fill="#4285F4" d="M17.64 9.2c0-.64-.06-1.25-.16-1.84H9v3.48h4.84a4.14 4.14 0 0 1-1.8 2.72v2.26h2.92c1.7-1.57 2.68-3.88 2.68-6.62z"/>
                <path fill="#34A853" d="M9 18c2.43 0 4.47-.8 5.96-2.18l-2.92-2.26c-.8.54-1.84.86-3.04.86-2.34 0-4.32-1.58-5.03-3.7H.96v2.33A9 9 0 0 0 9 18z"/>
                <path fill="#FBBC05" d="M3.97 10.72a5.4 5.4 0 0 1 0-3.44V4.95H.96a9 9 0 0 0 0 8.1l3.01-2.33z"/>
                <path fill="#EA4335" d="M9 3.58c1.32 0 2.5.46 3.44 1.35l2.58-2.58C13.47.9 11.43 0 9 0A9 9 0 0 0 .96 4.95l3.01 2.33C4.68 5.16 6.66 3.58 9 3.58z"/>
              </svg>
              {loading ? "이동 중…" : "Google로 계속하기"}
            </button>
            {error && (
              <p style={{ margin: "16px 0 0", fontSize: 12, color: "#b91c1c", textAlign: "center", lineHeight: 1.4 }}>
                {error}
              </p>
            )}
          </div>

          <button
            onClick={() => nav("/")}
            style={{
              display: "block", margin: "20px auto 0",
              background: "none", border: "none",
              fontSize: 12, color: C.t4, cursor: "pointer",
            }}
          >
            ← 홈으로
          </button>
        </div>
      </div>
    </>
  );
}
