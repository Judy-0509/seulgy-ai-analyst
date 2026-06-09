import { BrowserRouter, Routes, Route, Navigate, useLocation } from "react-router-dom";
import { AuthProvider, useAuth } from "./contexts/AuthContext";
import { DomainProvider } from "./contexts/DomainContext";
import Sidebar from "./components/Sidebar";
import LandingPage from "./pages/LandingPage";
import LoginPage from "./pages/LoginPage";
import AppPage from "./pages/AppPage";
import DbPage from "./pages/DbPage";
import NewsPage from "./pages/NewsPage";
import ReportPage from "./pages/ReportPage";
import ReportsArchivePage from "./pages/ReportsArchivePage";
import KeywordsPage from "./pages/KeywordsPage";
import UsagePage from "./pages/UsagePage";
import AccessRequestsPage from "./pages/AccessRequestsPage";
import FeedbackPage from "./pages/FeedbackPage";

/** 로그인 필요 (멤버 이상) — 미인증 시 /login 으로 리디렉트 */
function MemberRoute({ children }) {
  const { isAuthenticated, loading } = useAuth();
  const location = useLocation();
  if (loading) return null;
  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }
  return children;
}

/** 관리자 전용 — 미인증 시 /login, 비관리자 시 / 으로 리디렉트 */
function AdminRoute({ children }) {
  const { isAuthenticated, isAdmin, loading } = useAuth();
  const location = useLocation();
  if (loading) return null;
  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }
  if (!isAdmin) {
    return <Navigate to="/" replace />;
  }
  return children;
}

/** 페이지별 접근 제어 — isAdmin 또는 hasPageAccess(page) 인 경우 허용, 아니면 / 로 리디렉트 */
function PageRoute({ page, children }) {
  const { isAuthenticated, hasPageAccess, loading } = useAuth();
  const location = useLocation();
  if (loading) return null;
  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }
  if (!hasPageAccess(page)) {
    return <Navigate to="/" replace />;
  }
  return children;
}

function LegacyReportRedirect() {
  const { slug } = useLocation().pathname.match(/^\/report\/(?<slug>.+)$/)?.groups || {};
  return <Navigate to={slug ? `/archive/${slug}` : "/archive"} replace />;
}

function RouterContent() {
  const location = useLocation();
  const isHome = location.pathname === "/";
  return (
    <div style={{ height: "100vh", overflow: "hidden" }}>
      {isHome && <Sidebar />}
      <div style={{ width: "100%", height: "100%", overflow: "hidden", minWidth: 0 }}>
        <Routes>
          {/* PUBLIC */}
          <Route path="/"       element={<LandingPage />} />
          <Route path="/login"  element={<LoginPage />} />
          <Route path="/news"   element={<NewsPage />} />
          <Route path="/archive" element={<ReportsArchivePage />} />

          {/* MEMBER */}
          <Route path="/archive/:slug" element={<MemberRoute><ReportPage /></MemberRoute>} />
          <Route path="/feedback" element={<MemberRoute><FeedbackPage /></MemberRoute>} />

          {/* ADMIN */}
          <Route path="/app"      element={<AdminRoute><AppPage /></AdminRoute>} />
          <Route path="/usage"    element={<AdminRoute><UsagePage /></AdminRoute>} />
          <Route path="/access"   element={<AdminRoute><AccessRequestsPage /></AdminRoute>} />

          {/* PAGE-GATED (isAdmin 또는 granted) */}
          <Route path="/db"       element={<PageRoute page="db"><DbPage /></PageRoute>} />
          <Route path="/keywords" element={<PageRoute page="keywords"><KeywordsPage /></PageRoute>} />

          {/* Redirects */}
          <Route path="/reports"      element={<Navigate to="/archive" replace />} />
          <Route path="/report/:slug" element={<LegacyReportRedirect />} />
          <Route path="*"             element={<Navigate to="/" replace />} />
        </Routes>
      </div>
    </div>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <DomainProvider>
        <BrowserRouter>
          <RouterContent />
        </BrowserRouter>
      </DomainProvider>
    </AuthProvider>
  );
}
