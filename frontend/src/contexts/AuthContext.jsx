/* eslint-disable react-refresh/only-export-components */
import { createContext, useContext, useState } from "react";

const PIN = import.meta.env.VITE_PIN_KEY || "";
const AUTH_KEY = "canopy_auth";
const AUTH_TTL_MS = 24 * 60 * 60 * 1000;

const AuthCtx = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => {
    try {
      const saved = localStorage.getItem(AUTH_KEY);
      if (!saved) return null;
      const u = JSON.parse(saved);
      if (!u?.loginAt || Date.now() - u.loginAt > AUTH_TTL_MS) {
        localStorage.removeItem(AUTH_KEY);
        return null;
      }
      return u;
    } catch {
      return null;
    }
  });

  const login = (pin) => {
    if (!PIN) return { ok: false, error: "PIN이 설정되지 않았습니다. .env에 VITE_PIN_KEY를 추가하세요." };
    if (pin !== PIN) return { ok: false, error: "PIN이 올바르지 않습니다." };
    const u = { loginAt: Date.now() };
    localStorage.setItem(AUTH_KEY, JSON.stringify(u));
    setUser(u);
    return { ok: true };
  };

  const logout = () => {
    localStorage.removeItem(AUTH_KEY);
    setUser(null);
  };

  return (
    <AuthCtx.Provider value={{ user, login, logout, isAuthenticated: !!user }}>
      {children}
    </AuthCtx.Provider>
  );
}

export const useAuth = () => useContext(AuthCtx);
