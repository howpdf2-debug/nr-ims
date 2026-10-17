import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/api";
import { Building2, Server, AlertTriangle, ShieldCheck, Activity, ArrowRight } from "lucide-react";
import { useNavigate } from "react-router-dom";

export default function Dashboard() {
  const navigate = useNavigate();

  const { data: divisions = [], isLoading: loadingDiv } = useQuery({
    queryKey: ["divisions"],
    queryFn: () => api.get("/dashboard/divisions").then(res => res.data),
    refetchInterval: 30000,
  });

  const { data: devices = [] } = useQuery({
    queryKey: ["allDevices"],
    queryFn: () => api.get("/devices/").then(res => res.data),
  });

  const { data: alarms = [] } = useQuery({
    queryKey: ["activeAlarms"],
    queryFn: () => api.get("/alarms/").then(res => res.data),
    refetchInterval: 15000,
  });

  const totalDevices = devices.length;
  const activeAlarms = alarms.length;

  return (
    <div>
      <div className="kpi-grid">
        <div className="kpi-card">
          <div className="kpi-icon" style={{ background: 'rgba(59, 130, 246, 0.1)', color: 'var(--accent-blue)' }}><Server size={24} /></div>
          <div><div className="kpi-value">{totalDevices}</div><div className="kpi-label">Total Devices</div></div>
        </div>
        <div className="kpi-card">
          <div className="kpi-icon" style={{ background: 'rgba(239, 68, 68, 0.1)', color: 'var(--accent-red)' }}><AlertTriangle size={24} /></div>
          <div><div className="kpi-value">{activeAlarms}</div><div className="kpi-label">Active Incidents</div></div>
        </div>
        <div className="kpi-card">
          <div className="kpi-icon" style={{ background: 'rgba(16, 185, 129, 0.1)', color: 'var(--accent-green)' }}><ShieldCheck size={24} /></div>
          <div><div className="kpi-value">98.5%</div><div className="kpi-label">Config Compliance</div></div>
        </div>
        <div className="kpi-card">
          <div className="kpi-icon" style={{ background: 'rgba(245, 158, 11, 0.1)', color: 'var(--accent-amber)' }}><Activity size={24} /></div>
          <div><div className="kpi-value">45%</div><div className="kpi-label">Traffic Utilization</div></div>
        </div>
      </div>

      <h2>Network Health by Division</h2>
      {loadingDiv ? <p>Loading divisions...</p> : (
        <div className="grid-layout">
          {divisions.map((div: any) => (
            <div 
              key={div.division} 
              className="data-card" 
              onClick={() => navigate(`/division/${div.division}`)}
              style={{ cursor: 'pointer', borderLeft: `4px solid ${div.status === 'healthy' ? 'var(--accent-green)' : 'var(--accent-red)'}` }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
                <h3 style={{ fontSize: '1.4rem', fontWeight: 700 }}>
                  <Building2 size={20} style={{ display: 'inline', marginRight: '8px', verticalAlign: 'middle' }}/> 
                  {div.division} DIVISION
                </h3>
                <span className={`badge ${div.status === 'healthy' ? 'badge-up' : 'badge-down'}`}>
                  {div.status === 'healthy' ? 'ALL OK' : 'CRITICAL'}
                </span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', color: 'var(--text-muted)', fontSize: '0.9rem' }}>
                <span>Stations: <strong>{div.total_stations}</strong></span>
                <span>Down Devices: <strong style={{ color: div.down_devices > 0 ? 'var(--accent-red)' : 'inherit' }}>{div.down_devices}</strong></span>
              </div>
              <div style={{ marginTop: '1rem', textAlign: 'right', fontSize: '0.85rem', color: 'var(--accent-blue)' }}>
                View Stations <ArrowRight size={14} style={{ verticalAlign: 'middle' }} />
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}