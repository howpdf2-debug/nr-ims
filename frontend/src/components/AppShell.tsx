import { Outlet, useNavigate, Link, useLocation } from "react-router-dom";
import { LayoutDashboard, Bell, LogOut, ShieldAlert, GitBranch, Settings } from "lucide-react";

export default function AppShell() {
  const navigate = useNavigate();
  const location = useLocation();

  const handleLogout = () => {
    localStorage.removeItem("token");
    navigate("/");
  };

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '2.5rem', color: 'var(--accent-blue)' }}>
          <ShieldAlert size={28} />
          <span style={{ fontSize: '1.25rem', fontWeight: 700, color: 'white' }}>NR-IMS NOC</span>
        </div>
        
        <nav>
          <Link to="/dashboard" className={`nav-item ${location.pathname === '/dashboard' ? 'active' : ''}`}>
            <LayoutDashboard size={20} /> Global Dashboard
          </Link>
          <Link to="/topology" className={`nav-item ${location.pathname === '/topology' ? 'active' : ''}`}>
            <GitBranch size={20} /> Topology Map
          </Link>
          <Link to="/stations" className={`nav-item ${location.pathname === '/stations' ? 'active' : ''}`}>
            <Settings size={20} /> Manage Stations
          </Link>
          <Link to="/alarms" className={`nav-item ${location.pathname === '/alarms' ? 'active' : ''}`}>
            <Bell size={20} /> Alarm Center
          </Link>
        </nav>
      </aside>

      <main className="main-content">
        <header className="topbar">
          <h1>Northern Railway (NR)</h1>
          <button onClick={handleLogout} className="nav-item" style={{ margin: 0, padding: '0.5rem 1rem', width: 'auto', cursor: 'pointer', background: 'transparent' }}>
            <LogOut size={18} /> Logout
          </button>
        </header>
        <div className="page-content">
          <Outlet />
        </div>
      </main>
    </div>
  );
}