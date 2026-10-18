import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

// Pages
import Login from "./pages/Login";
import Dashboard from "./pages/Dashboard";
import DivisionDetail from "./pages/DivisionDetail";
import StationDetail from "./pages/StationDetail";
import DeviceDetail from "./pages/DeviceDetail";
import StationManagement from "./pages/StationManagement";
import Topology from "./pages/Topology";
import Alarms from "./pages/Alarms";
import ActionCenter from "./pages/ActionCenter"; // <-- नया पेज

// Components
import AppShell from "./components/AppShell";
import ProtectedRoute from "./components/ProtectedRoute";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
      staleTime: 30000,
    },
  },
});

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          {/* Public Route */}
          <Route path="/" element={<Login />} />

          {/* Protected Routes */}
          <Route element={<ProtectedRoute />}>
            <Route element={<AppShell />}>
              <Route path="/dashboard" element={<Dashboard />} />
              <Route path="/division/:divCode" element={<DivisionDetail />} />
              <Route path="/station/:code" element={<StationDetail />} />
              <Route path="/device/:deviceId" element={<DeviceDetail />} />
              <Route path="/stations" element={<StationManagement />} />
              <Route path="/topology" element={<Topology />} />
              <Route path="/alarms" element={<Alarms />} />
              <Route path="/actions" element={<ActionCenter />} /> {/* <-- नया राउट */}
              
              {/* डिफ़ॉल्ट रास्ता */}
              <Route path="*" element={<Navigate to="/dashboard" replace />} />
            </Route>
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}

export default App;