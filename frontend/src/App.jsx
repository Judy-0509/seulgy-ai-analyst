import { BrowserRouter, Routes, Route, Navigate, useLocation } from "react-router-dom";
import { AuthProvider, useAuth } from "./contexts/AuthContext";
import LandingPage from "./pages/LandingPage";
import LoginPage from "./pages/LoginPage";
import AppPage from "./pages/AppPage";
import DbPage from "./pages/DbPage";
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
  return (
    <Routes>
      <Route path="/" element={<LandingPage />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/app" element={<AppPage />} />
      <Route path="/archive" element={<ReportsArchivePage />} />
      <Route path="/archive/:slug" element={<ReportPage />} />
      <Route path="/reports" element={<Navigate to="/archive" replace />} />
      <Route path="/report/:slug" element={<LegacyReportRedirect />} />
      <Route path="/db" element={
        <ProtectedRoute>
          <DbPage />
        </ProtectedRoute>
      } />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <RouterContent />
      </BrowserRouter>
    </AuthProvider>
  );
}
