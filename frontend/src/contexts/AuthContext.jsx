/* eslint-disable react-refresh/only-export-components */
import { createContext, useContext, useEffect, useState, useCallback } from "react";
import { supabase } from "../lib/supabase";

const AuthCtx = createContext(null);

async function _loadMe(token) {
  try {
    const res = await fetch("/api/me", {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (res.ok) {
      const data = await res.json();
      return { isAdmin: Boolean(data.is_admin), pages: Array.isArray(data.pages) ? data.pages : [] };
    }
  } catch {
    // network error → defaults
  }
  return { isAdmin: false, pages: [] };
}

export function AuthProvider({ children }) {
  const [user, setUser]               = useState(null);
  const [isAdmin, setIsAdmin]         = useState(false);
  const [pages, setPages]             = useState([]);
  const [accessToken, setAccessToken] = useState(null);
  const [loading, setLoading]         = useState(true);

  const _applyMe = useCallback((token) => {
    _loadMe(token).then(({ isAdmin: a, pages: p }) => {
      setIsAdmin(a);
      setPages(p);
    });
  }, []);

  useEffect(() => {
    // 현재 세션 로드
    supabase.auth.getSession().then(({ data: { session } }) => {
      if (session) {
        setUser(session.user);
        setAccessToken(session.access_token);
        _applyMe(session.access_token);
      } else {
        setUser(null);
        setAccessToken(null);
        setIsAdmin(false);
        setPages([]);
      }
      setLoading(false);
    });

    // 로그인/로그아웃/토큰 갱신 이벤트 구독
    const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, session) => {
      if (session) {
        setUser(session.user);
        setAccessToken(session.access_token);
        _applyMe(session.access_token);
      } else {
        setUser(null);
        setAccessToken(null);
        setIsAdmin(false);
        setPages([]);
      }
    });

    return () => subscription.unsubscribe();
  }, [_applyMe]);

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
   * Google OAuth 로그인 — 리디렉트 후 supabase.js 의 detectSessionInUrl 이 세션을 처리한다.
   */
  async function signInWithGoogle() {
    const { error } = await supabase.auth.signInWithOAuth({
      provider: "google",
      options: { redirectTo: `${window.location.origin}/archive` },
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
    setPages([]);
    setAccessToken(null);
  }

  // DbPage 하위 호환: logout 별칭
  const logout = signOut;

  /** 승인 후 /api/me 를 다시 호출해 pages 를 갱신한다. */
  async function refreshMe() {
    const { data } = await supabase.auth.getSession();
    const token = data?.session?.access_token;
    if (token) _applyMe(token);
  }

  /** isAdmin 이거나 해당 page 가 부여된 경우 true. */
  function hasPageAccess(page) {
    return isAdmin || pages.includes(page);
  }

  return (
    <AuthCtx.Provider value={{
      user,
      isAuthenticated: !!user,
      isAdmin,
      pages,
      hasPageAccess,
      refreshMe,
      accessToken,
      loading,
      signIn,
      signInWithGoogle,
      verifyOtp,
      signOut,
      logout,
    }}>
      {children}
    </AuthCtx.Provider>
  );
}

export const useAuth = () => useContext(AuthCtx);
