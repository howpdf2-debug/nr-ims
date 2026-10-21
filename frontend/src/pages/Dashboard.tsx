import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/api";
import { Building2, Server, AlertTriangle, ShieldCheck, Wrench, ArrowRight, Network } from "lucide-react";
import { useNavigate } from "react-router-dom";

export default function Dashboard() {
  const navigate = useNavigate();

  const { data: divisions = [], isLoading } = useQuery({
    queryKey: ["divisions"],
    queryFn: () => api.get("/dashboard/divisions").then(res => res.data),
    refetchInterval: 30000,
  });

  // KPIs are computed server-side in SQL (never from a paginated list, which was capped at 100 rows).
  const { data: summary } = useQuery({
    queryKey: ["dashboardSummary"],
    queryFn: () => api.get("/dashboard/summary").then(res => res.data),
    refetchInterval: 15000,
  });

  const totalDevices = summary?.total_devices ?? "—";
  const activeAlarms = summary?.active_alarms ?? "—";
  const availability = summary?.availability_pct == null ? "—" : `${summary.availability_pct}%`;
  const inMaintenance = summary?.maintenance_devices ?? "—";
  
  const ircaDiv = divisions.find((d: any) => d.division === "IRCA");
  const otherDivisions = divisions.filter((d: any) => d.division !== "IRCA");

  return (
    <div style={{ paddingBottom: '3rem' }}>
      <div className="kpi-grid">
        <div className="kpi-card" style={{ cursor: 'pointer' }} onClick={() => navigate('/topology')}>
          <div className="kpi-icon" style={{ background: 'rgba(59, 130, 246, 0.1)', color: 'var(--accent-blue)' }}><Server size={24} /></div>
          <div><div className="kpi-value">{totalDevices}</div><div className="kpi-label">Total Devices</div></div>
        </div>
        
        <div className="kpi-card" style={{ cursor: 'pointer' }} onClick={() => navigate('/actions')}>
          <div className="kpi-icon" style={{ background: 'rgba(239, 68, 68, 0.1)', color: 'var(--accent-red)' }}><AlertTriangle size={24} /></div>
          <div><div className="kpi-value">{activeAlarms}</div><div className="kpi-label">Active Incidents</div></div>
        </div>
        
        <div className="kpi-card">
          <div className="kpi-icon" style={{ background: 'rgba(16, 185, 129, 0.1)', color: 'var(--accent-green)' }}><ShieldCheck size={24} /></div>
          <div><div className="kpi-value">{availability}</div><div className="kpi-label">Device Availability</div></div>
        </div>
        
        <div className="kpi-card">
          <div className="kpi-icon" style={{ background: 'rgba(245, 158, 11, 0.1)', color: 'var(--accent-amber)' }}><Wrench size={24} /></div>
          <div><div className="kpi-value">{inMaintenance}</div><div className="kpi-label">In Maintenance</div></div>
        </div>
      </div>

      {ircaDiv && (
        <div style={{ marginBottom: '2.5rem' }}>
          <h2 style={{ marginBottom: '1rem', color: 'var(--accent-amber)' }}>Core Network (Tier 0)</h2>
          <div className="data-card" style={{ borderLeft: '4px solid var(--accent-amber)', display: 'flex', justifyContent: 'space-between', alignItems: 'center', cursor: 'pointer' }} onClick={() => navigate(`/station/IRCA`)}>
            <div>
              <h3 style={{ fontSize: '1.4rem', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '8px' }}><Network size={20}/> IRCA Central Hub</h3>
              <p style={{ color: 'var(--text-muted)', marginTop: '0.5rem' }}>All Core Routers and Central Servers are located here.</p>
            </div>
            <div style={{ textAlign: 'right' }}>
              <span className={`badge ${ircaDiv.status === 'healthy' ? 'badge-up' : 'badge-down'}`}>{ircaDiv.status === 'healthy' ? 'ALL OK' : 'CRITICAL'}</span>
              {/* Grammar Fix: Node vs Nodes */}
              <p style={{ marginTop: '0.5rem', fontSize: '0.9rem' }}>
                {ircaDiv.total_stations} Core Node{ircaDiv.total_stations === 1 ? '' : 's'}
              </p>
            </div>
          </div>
        </div>
      )}

      <h2>Divisional Network Health</h2>
      {isLoading ? <p>Loading divisions...</p> : (
        <div className="grid-layout">
          {otherDivisions.map((div: any) => (
            <div 
              key={div.division} 
              className="data-card" 
              onClick={() => navigate(`/division/${div.division}`)}
              style={{ cursor: 'pointer', borderLeft: `4px solid ${div.status === 'healthy' ? 'var(--accent-green)' : 'var(--accent-red)'}` }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
                <h3 style={{ fontSize: '1.4rem', fontWeight: 700 }}><Building2 size={20} style={{ display: 'inline', marginRight: '8px', verticalAlign: 'middle' }}/> {div.division} DIVISION</h3>
                <span className={`badge ${div.status === 'healthy' ? 'badge-up' : 'badge-down'}`}>{div.status === 'healthy' ? 'ALL OK' : 'CRITICAL'}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', color: 'var(--text-muted)', fontSize: '0.9rem' }}>
                <span>Stations: <strong>{div.total_stations}</strong></span>
                <span>Down Devices: <strong style={{ color: div.down_devices > 0 ? 'var(--accent-red)' : 'inherit' }}>{div.down_devices}</strong></span>
              </div>
              <div style={{ marginTop: '1rem', textAlign: 'right', fontSize: '0.85rem', color: 'var(--accent-blue)' }}>View Stations <ArrowRight size={14} style={{ verticalAlign: 'middle' }} /></div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}