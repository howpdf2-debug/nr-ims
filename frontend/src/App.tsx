import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import Login from "./pages/Login";
import Dashboard from "./pages/Dashboard";
import DivisionDetail from "./pages/DivisionDetail";
import StationDetail from "./pages/StationDetail";
import DeviceDetail from "./pages/DeviceDetail";
import StationManagement from "./pages/StationManagement";
import Topology from "./pages/Topology";
import Alarms from "./pages/Alarms";
import ActionCenter from "./pages/ActionCenter";
import AuditLog from "./pages/AuditLog";
import DiscoveryCenter from "./pages/DiscoveryCenter";
import UserManagement from "./pages/UserManagement";
import Wallboard from "./pages/Wallboard";
import Reports from "./pages/Reports"; // <-- नया Reports पेज इम्पोर्ट किया

import AppShell from "./components/AppShell";
import ProtectedRoute from "./components/ProtectedRoute";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { refetchOnWindowFocus: false, retry: 1, staleTime: 30000 },
  },
});

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Login />} />
          
          <Route element={<ProtectedRoute />}>
            {/* WALLBOARD (AppShell के बाहर, ताकि फुल-स्क्रीन में साइडबार न दिखे) */}
            <Route path="/wallboard" element={<Wallboard />} />

            {/* REST OF THE APP (AppShell के अंदर) */}
            <Route element={<AppShell />}>
              <Route path="/dashboard" element={<Dashboard />} />
              <Route path="/division/:divCode" element={<DivisionDetail />} />
              <Route path="/station/:code" element={<StationDetail />} />
              <Route path="/device/:deviceId" element={<DeviceDetail />} />
              <Route path="/stations" element={<StationManagement />} />
              <Route path="/topology" element={<Topology />} />
              <Route path="/alarms" element={<Alarms />} />
              <Route path="/actions" element={<ActionCenter />} />
              <Route path="/reports" element={<Reports />} /> {/* <-- नया Reports राउट */}
              <Route path="/audit" element={<AuditLog />} />
              <Route path="/discovery" element={<DiscoveryCenter />} />
              <Route path="/users" element={<UserManagement />} />
              
              {/* किसी भी गलत URL पर Dashboard पर भेजें */}
              <Route path="*" element={<Navigate to="/dashboard" replace />} />
            </Route>
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}

export default App;