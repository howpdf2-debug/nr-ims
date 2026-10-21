import { lazy, Suspense } from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import AppShell from "./components/AppShell";
import ProtectedRoute from "./components/ProtectedRoute";
import RouteErrorBoundary from "./components/ErrorBoundary";

// ── Lazy Loading All Pages (Splitting into separate chunks) ──
const Login = lazy(() => import("./pages/Login"));
const Dashboard = lazy(() => import("./pages/Dashboard"));
const DivisionDetail = lazy(() => import("./pages/DivisionDetail"));
const StationDetail = lazy(() => import("./pages/StationDetail"));
const DeviceDetail = lazy(() => import("./pages/DeviceDetail"));
const StationManagement = lazy(() => import("./pages/StationManagement"));
const Topology = lazy(() => import("./pages/Topology"));
const Alarms = lazy(() => import("./pages/Alarms"));
const ActionCenter = lazy(() => import("./pages/ActionCenter"));
const AuditLog = lazy(() => import("./pages/AuditLog"));
const DiscoveryCenter = lazy(() => import("./pages/DiscoveryCenter"));
const UserManagement = lazy(() => import("./pages/UserManagement"));
const Wallboard = lazy(() => import("./pages/Wallboard"));
const Reports = lazy(() => import("./pages/Reports"));

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { refetchOnWindowFocus: false, retry: 1, staleTime: 30000 },
  },
});

// ── Loading Screen (जब कोई नया पेज लोड हो रहा हो) ──
const PageLoader = () => (
  <div style={{ display: "flex", height: "100vh", alignItems: "center", justifyContent: "center", background: "var(--bg-base)", color: "var(--text-main)" }}>
    <div style={{ textAlign: "center" }}>
      <div className="pulse" style={{ width: "50px", height: "50px", border: "4px solid var(--accent-blue)", borderRadius: "50%", borderTopColor: "transparent", animation: "spin 1s linear infinite", margin: "0 auto 1rem auto" }} />
      <h2>Loading Module...</h2>
    </div>
  </div>
);

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <RouteErrorBoundary>
        <Suspense fallback={<PageLoader />}>
          <Routes>
            <Route path="/" element={<Login />} />
            
            <Route element={<ProtectedRoute />}>
              {/* WALLBOARD (Full Screen) */}
              <Route path="/wallboard" element={<Wallboard />} />

              {/* REST OF THE APP (Inside AppShell) */}
              <Route element={<AppShell />}>
                <Route path="/dashboard" element={<Dashboard />} />
                <Route path="/division/:divCode" element={<DivisionDetail />} />
                <Route path="/station/:code" element={<StationDetail />} />
                <Route path="/device/:deviceId" element={<DeviceDetail />} />
                <Route path="/stations" element={<StationManagement />} />
                <Route path="/topology" element={<Topology />} />
                <Route path="/alarms" element={<Alarms />} />
                <Route path="/actions" element={<ActionCenter />} />
                <Route path="/reports" element={<Reports />} />
                <Route path="/audit" element={<AuditLog />} />
                <Route path="/discovery" element={<DiscoveryCenter />} />
                <Route path="/users" element={<UserManagement />} />
                
                <Route path="*" element={<Navigate to="/dashboard" replace />} />
              </Route>
            </Route>
          </Routes>
        </Suspense>
        </RouteErrorBoundary>
      </BrowserRouter>
    </QueryClientProvider>
  );
}

export default App;