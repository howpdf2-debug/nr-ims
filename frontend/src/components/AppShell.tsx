import { Outlet, useNavigate, Link, useLocation } from "react-router-dom";
import { 
  LayoutDashboard, Bell, LogOut, ShieldAlert, GitBranch, Settings, 
  Wrench, ShieldCheck, Radar, Users, Volume2, VolumeX, Monitor, BarChart3 
} from "lucide-react";
import { useAlarmSound } from "../hooks/useAlarmSound";

export default function AppShell() {
  const navigate = useNavigate();
  const location = useLocation();
  const { isMuted, toggleMute } = useAlarmSound();

  const token = localStorage.getItem("token");
  let userRole = "operator";
  if (token) {
    try {
      userRole = JSON.parse(atob(token.split('.')[1])).role || "operator";
    } catch (e) {}
  }

  const handleLogout = () => {
    localStorage.removeItem("token");
    navigate("/");
  };

  const canManageStations = userRole.includes("admin");
  const isIrcaAdmin = userRole === "irca_admin";

  return (
    <div className="app-shell" style={{ display: "flex", height: "100vh", overflow: "hidden" }}>
      
      {/* ── SIDEBAR (Fixed Width, Scrollable) ── */}
      <aside 
        className="sidebar" 
        style={{ 
          width: "240px", 
          minWidth: "240px", // साइडबार कभी सिकुड़ेगा नहीं
          flexShrink: 0, 
          display: "flex", 
          flexDirection: "column", 
          padding: "1.5rem 1rem", 
          background: "var(--bg-surface)", 
          borderRight: "1px solid var(--border-color)",
          overflowY: "auto"
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '2.5rem', color: 'var(--accent-blue)', paddingLeft: "0.5rem" }}>
          <ShieldAlert size={28} />
          <span style={{ fontSize: '1.25rem', fontWeight: 700, color: 'white', whiteSpace: "nowrap" }}>NR-IMS NOC</span>
        </div>
        
        <nav style={{ display: "flex", flexDirection: "column", gap: "0.25rem" }}>
          <Link to="/dashboard" className={`nav-item ${location.pathname === '/dashboard' ? 'active' : ''}`} style={{ display: "flex", alignItems: "center", gap: "0.75rem", padding: "0.75rem 1rem", borderRadius: "8px", color: location.pathname === '/dashboard' ? "white" : "var(--text-muted)", textDecoration: "none", background: location.pathname === '/dashboard' ? "var(--bg-base)" : "transparent" }}>
            <LayoutDashboard size={20} /> Dashboard
          </Link>
          <Link to="/topology" className={`nav-item ${location.pathname === '/topology' ? 'active' : ''}`} style={{ display: "flex", alignItems: "center", gap: "0.75rem", padding: "0.75rem 1rem", borderRadius: "8px", color: location.pathname === '/topology' ? "white" : "var(--text-muted)", textDecoration: "none", background: location.pathname === '/topology' ? "var(--bg-base)" : "transparent" }}>
            <GitBranch size={20} /> Topology Map
          </Link>
          {canManageStations && (
            <Link to="/stations" className={`nav-item ${location.pathname === '/stations' ? 'active' : ''}`} style={{ display: "flex", alignItems: "center", gap: "0.75rem", padding: "0.75rem 1rem", borderRadius: "8px", color: location.pathname === '/stations' ? "white" : "var(--text-muted)", textDecoration: "none", background: location.pathname === '/stations' ? "var(--bg-base)" : "transparent" }}>
              <Settings size={20} /> Manage Stations
            </Link>
          )}
          <Link to="/alarms" className={`nav-item ${location.pathname === '/alarms' ? 'active' : ''}`} style={{ display: "flex", alignItems: "center", gap: "0.75rem", padding: "0.75rem 1rem", borderRadius: "8px", color: location.pathname === '/alarms' ? "white" : "var(--text-muted)", textDecoration: "none", background: location.pathname === '/alarms' ? "var(--bg-base)" : "transparent" }}>
            <Bell size={20} /> Alarm Center
          </Link>
          <Link to="/actions" className={`nav-item ${location.pathname === '/actions' ? 'active' : ''}`} style={{ display: "flex", alignItems: "center", gap: "0.75rem", padding: "0.75rem 1rem", borderRadius: "8px", color: location.pathname === '/actions' ? "white" : "var(--text-muted)", textDecoration: "none", background: location.pathname === '/actions' ? "var(--bg-base)" : "transparent" }}>
            <Wrench size={20} /> Action Center
          </Link>
          <Link to="/reports" className={`nav-item ${location.pathname === '/reports' ? 'active' : ''}`} style={{ display: "flex", alignItems: "center", gap: "0.75rem", padding: "0.75rem 1rem", borderRadius: "8px", color: location.pathname === '/reports' ? "white" : "var(--text-muted)", textDecoration: "none", background: location.pathname === '/reports' ? "var(--bg-base)" : "transparent" }}>
            <BarChart3 size={20} /> Reports & SLA
          </Link>
          
          {isIrcaAdmin && (
            <>
              <Link to="/discovery" className={`nav-item ${location.pathname === '/discovery' ? 'active' : ''}`} style={{ display: "flex", alignItems: "center", gap: "0.75rem", padding: "0.75rem 1rem", borderRadius: "8px", color: location.pathname === '/discovery' ? "white" : "var(--text-muted)", textDecoration: "none", background: location.pathname === '/discovery' ? "var(--bg-base)" : "transparent" }}>
                <Radar size={20} /> Auto-Discovery
              </Link>
              <Link to="/users" className={`nav-item ${location.pathname === '/users' ? 'active' : ''}`} style={{ display: "flex", alignItems: "center", gap: "0.75rem", padding: "0.75rem 1rem", borderRadius: "8px", color: location.pathname === '/users' ? "white" : "var(--text-muted)", textDecoration: "none", background: location.pathname === '/users' ? "var(--bg-base)" : "transparent" }}>
                <Users size={20} /> User Management
              </Link>
              <Link to="/audit" className={`nav-item ${location.pathname === '/audit' ? 'active' : ''}`} style={{ display: "flex", alignItems: "center", gap: "0.75rem", padding: "0.75rem 1rem", borderRadius: "8px", color: location.pathname === '/audit' ? "white" : "var(--text-muted)", textDecoration: "none", background: location.pathname === '/audit' ? "var(--bg-base)" : "transparent" }}>
                <ShieldCheck size={20} /> Audit Logs
              </Link>
            </>
          )}
        </nav>
        
        <div style={{ marginTop: 'auto', fontSize: '0.75rem', color: 'var(--text-muted)', padding: "1rem 0.5rem 0 0.5rem" }}>
          Logged in as: <strong style={{ display: 'block', color: 'white', textTransform: 'uppercase', marginTop: "0.25rem" }}>{userRole.replace('_', ' ')}</strong>
        </div>
      </aside>

      {/* ── MAIN CONTENT AREA ── */}
      <main className="main-content" style={{ flex: 1, display: "flex", flexDirection: "column", minWidth: 0, overflow: "hidden" }}>
        
        {/* ── TOPBAR (Flexible and Responsive) ── */}
        <header 
          className="topbar" 
          style={{ 
            display: "flex", 
            justifyContent: "space-between", 
            alignItems: "center", 
            padding: "1rem 1.5rem", 
            background: "var(--bg-surface)", 
            borderBottom: "1px solid var(--border-color)",
            flexShrink: 0,
            gap: "1rem", // अगर स्क्रीन छोटी होगी तो टाइटल और बटन्स में गैप रहेगा
            flexWrap: "wrap" // अगर बहुत ज्यादा टाइट हो जाए तो बटन्स नीचे आ जाएंगे
          }}
        >
          <h1 
            style={{ 
              margin: 0, 
              fontSize: "1.5rem",
              whiteSpace: "nowrap",
              overflow: "hidden",
              textOverflow: "ellipsis",
              flex: 1, // बची हुई सारी जगह लेगा
              minWidth: "200px" // कम से कम 200px जगह तो रहेगी ही
            }}
          >
            Northern Railway (NR)
          </h1>
          
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', flexShrink: 0 }}>
            <button 
              onClick={() => window.open('/wallboard', '_blank')} 
              className="nav-item" 
              style={{ margin: 0, padding: '0.5rem 1rem', width: 'auto', cursor: 'pointer', background: 'var(--bg-surface)', border: '1px solid var(--border-color)', display: 'flex', gap: '6px', alignItems: "center", borderRadius: "8px", color: "white" }} 
              title="Open Wallboard"
            >
              <Monitor size={18} /> Wallboard
            </button>

            <button 
              onClick={toggleMute} 
              className="nav-item" 
              style={{ margin: 0, padding: '0.5rem', width: 'auto', cursor: 'pointer', background: 'var(--bg-surface)', border: '1px solid var(--border-color)', display: 'flex', alignItems: "center", borderRadius: "8px" }} 
              title={isMuted ? "Unmute Alarms" : "Mute Alarms"}
            >
              {isMuted ? <VolumeX size={18} color="var(--accent-red)" /> : <Volume2 size={18} color="var(--accent-green)" />}
            </button>

            <button 
              onClick={handleLogout} 
              className="nav-item" 
              style={{ margin: 0, padding: '0.5rem 1rem', width: 'auto', cursor: 'pointer', background: 'transparent', display: 'flex', gap: '6px', alignItems: "center", borderRadius: "8px", color: "var(--text-muted)" }}
            >
              <LogOut size={18} /> Logout
            </button>
          </div>
        </header>
        
        <div className="page-content" style={{ flex: 1, overflowY: "auto", padding: "1.5rem", background: "var(--bg-base)" }}>
          <Outlet />
        </div>
      </main>
    </div>
  );
}