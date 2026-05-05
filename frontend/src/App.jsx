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

function ProtectedRoute({ children }) {
  const { isAuthenticated } = useAuth();
  const location = useLocation();
  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
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
          <Route path="/"       element={<LandingPage />} />
          <Route path="/login"  element={<LoginPage />} />
          <Route path="/news"   element={<NewsPage />} />

          <Route path="/app"    element={<ProtectedRoute><AppPage /></ProtectedRoute>} />
          <Route path="/db"     element={<ProtectedRoute><DbPage /></ProtectedRoute>} />
          <Route path="/archive"       element={<ProtectedRoute><ReportsArchivePage /></ProtectedRoute>} />
          <Route path="/archive/:slug" element={<ProtectedRoute><ReportPage /></ProtectedRoute>} />

          <Route path="/reports"       element={<Navigate to="/archive" replace />} />
          <Route path="/report/:slug"  element={<LegacyReportRedirect />} />
          <Route path="*"              element={<Navigate to="/" replace />} />
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
