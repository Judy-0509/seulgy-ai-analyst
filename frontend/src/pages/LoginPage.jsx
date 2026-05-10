import { useEffect, useRef, useState } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { C } from "../theme";
import { useAuth } from "../contexts/AuthContext";

export default function LoginPage() {
  const nav = useNavigate();
  const location = useLocation();
  const { login, isAuthenticated } = useAuth();
  const [pin, setPin] = useState("");
  const [error, setError] = useState("");
  const [shake, setShake] = useState(false);
  const inputRef = useRef(null);

  const from = location.state?.from?.pathname || "/app";

  useEffect(() => {
    if (isAuthenticated) nav(from, { replace: true });
  }, [isAuthenticated, nav, from]);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!pin.trim()) return;
    const result = login(pin.trim());
    if (result.ok) {
      nav(from, { replace: true });
    } else {
      setError(result.error);
      setPin("");
      setShake(true);
      setTimeout(() => setShake(false), 500);
      inputRef.current?.focus();
    }
  };

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
        .pin-input::placeholder { color: #c8c6c2; letter-spacing: 0; }
        .pin-input:focus { border-color: ${C.t2} !important; }
        .submit-btn:hover:not(:disabled) { opacity: 0.82; }
      `}</style>

      <div style={{
        height: "100%", display: "flex", alignItems: "center", justifyContent: "center",
        background: C.bg,
        fontFamily: '"Pretendard Variable", Pretendard, Inter, -apple-system, BlinkMacSystemFont, "Helvetica Neue", sans-serif',
      }}>
        <div style={{
          width: "100%", maxWidth: 360,
          animation: "fadeUp 0.35s ease",
        }}>
          {/* Logo */}
          <div style={{ display: "flex", justifyContent: "center", marginBottom: 36 }}>
            <img
              src="/logo-mark.png"
              alt="Canopy"
              style={{ width: 88, height: 64, objectFit: "contain", opacity: 0.92 }}
            />
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
              margin: "0 0 6px",
              fontSize: 11,
              fontWeight: 600,
              color: C.t4,
              letterSpacing: "0.08em",
              textTransform: "uppercase",
              textAlign: "center",
            }}>
              Enter your pin key
            </p>
            <p style={{
              margin: "0 0 26px",
              fontSize: 13,
              color: C.t3,
              textAlign: "center",
              lineHeight: 1.5,
            }}>
              리서치 도구에 접근하려면 PIN이 필요합니다
            </p>

            <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 14 }}>
              <input
                ref={inputRef}
                className="pin-input"
                type="password"
                value={pin}
                onChange={(e) => { setPin(e.target.value); setError(""); }}
                placeholder="• • • • • •"
                autoComplete="off"
                style={{
                  width: "100%",
                  boxSizing: "border-box",
                  height: 52,
                  border: `1.5px solid ${error ? "#fca5a5" : C.border}`,
                  borderRadius: 10,
                  padding: "0 16px",
                  fontSize: 22,
                  letterSpacing: "0.25em",
                  color: C.t1,
                  background: error ? "#fff8f8" : C.card,
                  outline: "none",
                  textAlign: "center",
                  transition: "border-color 0.15s, background 0.15s",
                }}
              />

              {error && (
                <p style={{
                  margin: 0,
                  fontSize: 12,
                  color: "#b91c1c",
                  textAlign: "center",
                  lineHeight: 1.4,
                }}>
                  {error}
                </p>
              )}

              <button
                type="submit"
                disabled={!pin.trim()}
                className="submit-btn"
                style={{
                  height: 46,
                  border: "none",
                  borderRadius: 10,
                  background: pin.trim() ? C.t1 : C.subtle2,
                  color: pin.trim() ? "#fff" : C.t4,
                  fontSize: 13,
                  fontWeight: 700,
                  cursor: pin.trim() ? "pointer" : "default",
                  transition: "background 0.15s, color 0.15s, opacity 0.15s",
                  letterSpacing: "0.01em",
                }}
              >
                확인
              </button>
            </form>
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
