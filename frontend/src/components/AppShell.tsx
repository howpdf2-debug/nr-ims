import { Outlet, useNavigate, Link, useLocation } from "react-router-dom";
import { LayoutDashboard, Bell, LogOut, ShieldAlert, GitBranch, Settings, Wrench, ShieldCheck, Radar, Users, Volume2, VolumeX, Monitor } from "lucide-react";
import { useAlarmSound } from "../hooks/useAlarmSound";

export default function AppShell() {
  const navigate = useNavigate();
  const location = useLocation();
  const { isMuted, toggleMute } = useAlarmSound();

  const token = localStorage.getItem("token");
  let userRole = "operator";
  if (token) { try { userRole = JSON.parse(atob(token.split('.')[1])).role || "operator"; } catch (e) {} }

  const handleLogout = () => { localStorage.removeItem("token"); navigate("/"); };
  const canManageStations = userRole.includes("admin");
  const isIrcaAdmin = userRole === "irca_admin";

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '2.5rem', color: 'var(--accent-blue)' }}>
          <ShieldAlert size={28} /><span style={{ fontSize: '1.25rem', fontWeight: 700, color: 'white' }}>NR-IMS NOC</span>
        </div>
        
        <nav>
          <Link to="/dashboard" className={`nav-item ${location.pathname === '/dashboard' ? 'active' : ''}`}><LayoutDashboard size={20} /> Dashboard</Link>
          <Link to="/topology" className={`nav-item ${location.pathname === '/topology' ? 'active' : ''}`}><GitBranch size={20} /> Topology Map</Link>
          {canManageStations && <Link to="/stations" className={`nav-item ${location.pathname === '/stations' ? 'active' : ''}`}><Settings size={20} /> Manage Stations</Link>}
          <Link to="/alarms" className={`nav-item ${location.pathname === '/alarms' ? 'active' : ''}`}><Bell size={20} /> Alarm Center</Link>
          <Link to="/actions" className={`nav-item ${location.pathname === '/actions' ? 'active' : ''}`}><Wrench size={20} /> Action Center</Link>
          
          {isIrcaAdmin && (
            <>
              <Link to="/discovery" className={`nav-item ${location.pathname === '/discovery' ? 'active' : ''}`}><Radar size={20} /> Auto-Discovery</Link>
              <Link to="/users" className={`nav-item ${location.pathname === '/users' ? 'active' : ''}`}><Users size={20} /> User Management</Link>
              <Link to="/audit" className={`nav-item ${location.pathname === '/audit' ? 'active' : ''}`}><ShieldCheck size={20} /> Audit Logs</Link>
            </>
          )}
        </nav>
        
        <div style={{ marginTop: 'auto', fontSize: '0.75rem', color: 'var(--text-muted)' }}>
          Logged in as: <strong style={{ display: 'block', color: 'white', textTransform: 'uppercase' }}>{userRole.replace('_', ' ')}</strong>
        </div>
      </aside>

      <main className="main-content">
        <header className="topbar">
          <h1>Northern Railway (NR)</h1>
          
          <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
            <button onClick={() => window.open('/wallboard', '_blank')} className="nav-item" style={{ margin: 0, padding: '0.5rem 1rem', width: 'auto', cursor: 'pointer', background: 'var(--bg-surface)', border: '1px solid var(--border-color)', display: 'flex', gap: '6px' }} title="Open Wallboard">
              <Monitor size={18} /> Wallboard
            </button>

            {/* Global Mute Button */}
            <button onClick={toggleMute} className="nav-item" style={{ margin: 0, padding: '0.5rem', width: 'auto', cursor: 'pointer', background: 'var(--bg-surface)', border: '1px solid var(--border-color)' }} title={isMuted ? "Unmute Alarms" : "Mute Alarms"}>
              {isMuted ? <VolumeX size={18} color="var(--accent-red)" /> : <Volume2 size={18} color="var(--accent-green)" />}
            </button>

            <button onClick={handleLogout} className="nav-item" style={{ margin: 0, padding: '0.5rem 1rem', width: 'auto', cursor: 'pointer', background: 'transparent' }}><LogOut size={18} /> Logout</button>
          </div>
        </header>
        <div className="page-content"><Outlet /></div>
      </main>
    </div>
  );
}