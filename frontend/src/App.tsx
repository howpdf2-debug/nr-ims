import { BrowserRouter, Routes, Route } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import Login from "./pages/Login";
import Dashboard from "./pages/Dashboard";
import DivisionDetail from "./pages/DivisionDetail";
import StationDetail from "./pages/StationDetail";
import DeviceDetail from "./pages/DeviceDetail";
import Topology from "./pages/Topology";
import Alarms from "./pages/Alarms";
import AppShell from "./components/AppShell";
import ProtectedRoute from "./components/ProtectedRoute";

const queryClient = new QueryClient();

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Login />} />
          <Route element={<ProtectedRoute />}>
            <Route element={<AppShell />}>
              <Route path="/dashboard" element={<Dashboard />} />
              <Route path="/division/:divCode" element={<DivisionDetail />} />
              <Route path="/station/:code" element={<StationDetail />} />
              <Route path="/device/:deviceId" element={<DeviceDetail />} />
              <Route path="/topology" element={<Topology />} />
              <Route path="/alarms" element={<Alarms />} />
            </Route>
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
export default App;
