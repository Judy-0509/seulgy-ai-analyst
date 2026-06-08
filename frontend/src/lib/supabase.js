import { createClient } from "@supabase/supabase-js";

const url = import.meta.env.VITE_SUPABASE_URL;
const anonKey = import.meta.env.VITE_SUPABASE_ANON_KEY;

// .env에 키가 채워졌는지 — UI 안내 등에 활용 가능.
export const supabaseConfigured = Boolean(url && anonKey);

if (!supabaseConfigured) {
  // 키가 없어도 앱이 크래시하지 않도록 placeholder로 생성하고 콘솔로 안내한다.
  console.warn(
    "[Seulgy] Supabase 환경변수가 비어 있습니다. 루트 .env에 " +
      "VITE_SUPABASE_URL / VITE_SUPABASE_ANON_KEY 를 설정하세요. (supabase/README.md 참고)"
  );
}

export const supabase = createClient(
  url || "https://placeholder.supabase.co",
  anonKey || "placeholder-anon-key",
  {
    auth: {
      persistSession: true,
      autoRefreshToken: true,
      // OAuth(구글) 리디렉트 복귀 시 URL의 code를 자동 처리하기 위해 필요.
      detectSessionInUrl: true,
      flowType: "pkce",
    },
  }
);
