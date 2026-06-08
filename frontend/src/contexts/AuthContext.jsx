/* eslint-disable react-refresh/only-export-components */
import { createContext, useContext, useEffect, useState } from "react";
import { supabase } from "../lib/supabase";

const AuthCtx = createContext(null);

async function _fetchIsAdmin(token) {
  try {
    const res = await fetch("/api/me", {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (res.ok) {
      const data = await res.json();
      return Boolean(data.is_admin);
    }
  } catch {
    // network error → not admin
  }
  return false;
}

export function AuthProvider({ children }) {
  const [user, setUser]               = useState(null);
  const [isAdmin, setIsAdmin]         = useState(false);
  const [accessToken, setAccessToken] = useState(null);
  const [loading, setLoading]         = useState(true);

  useEffect(() => {
    // 현재 세션 로드
    supabase.auth.getSession().then(({ data: { session } }) => {
      if (session) {
        setUser(session.user);
        setAccessToken(session.access_token);
        _fetchIsAdmin(session.access_token).then(setIsAdmin);
      } else {
        setUser(null);
        setAccessToken(null);
        setIsAdmin(false);
      }
      setLoading(false);
    });

    // 로그인/로그아웃/토큰 갱신 이벤트 구독
    const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, session) => {
      if (session) {
        setUser(session.user);
        setAccessToken(session.access_token);
        _fetchIsAdmin(session.access_token).then(setIsAdmin);
      } else {
        setUser(null);
        setAccessToken(null);
        setIsAdmin(false);
      }
    });

    return () => subscription.unsubscribe();
  }, []);

  /**
   * 이메일 OTP 발송 — signIn step 1.
   * 성공 시 { ok: true }, 실패 시 { ok: false, error: string }
   */
  async function signIn(email) {
    const { error } = await supabase.auth.signInWithOtp({
      email,
      options: { shouldCreateUser: true },
    });
    if (error) return { ok: false, error: error.message };
    return { ok: true };
  }

  /**
   * 이메일 OTP 코드 검증 — signIn step 2.
   * 성공 시 { ok: true }, 실패 시 { ok: false, error: string }
   */
  async function verifyOtp(email, token) {
    const { error } = await supabase.auth.verifyOtp({
      email,
      token,
      type: "email",
    });
    if (error) return { ok: false, error: error.message };
    return { ok: true };
  }

  async function signOut() {
    await supabase.auth.signOut();
    setUser(null);
    setIsAdmin(false);
    setAccessToken(null);
  }

  // DbPage 하위 호환: logout 별칭
  const logout = signOut;

  return (
    <AuthCtx.Provider value={{
      user,
      isAuthenticated: !!user,
      isAdmin,
      accessToken,
      loading,
      signIn,
      verifyOtp,
      signOut,
      logout,
    }}>
      {children}
    </AuthCtx.Provider>
  );
}

export const useAuth = () => useContext(AuthCtx);
