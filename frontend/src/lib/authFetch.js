/**
 * authFetch — Authorization: Bearer <token> 헤더를 자동으로 첨부하는 fetch 래퍼.
 * Supabase 세션 토큰을 직접 가져오므로 컴포넌트에 accessToken을 prop으로 전달할 필요가 없다.
 */
import { supabase } from "./supabase";

export async function authFetch(url, options = {}) {
  const { data } = await supabase.auth.getSession();
  const token = data?.session?.access_token;

  const headers = { ...(options.headers || {}) };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  return fetch(url, { ...options, headers });
}

/**
 * 현재 세션 토큰을 반환. EventSource / sendBeacon 등 헤더를 직접 붙일 수 없는
 * API 호출에서 ?access_token=<token> 쿼리 파라미터로 전달할 때 사용한다.
 */
export async function getAccessToken() {
  const { data } = await supabase.auth.getSession();
  return data?.session?.access_token ?? null;
}
