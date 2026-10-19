import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../lib/api";
import { Radar, ShieldAlert, CheckCircle, XCircle, AlertTriangle, Monitor, Router, Network, Shield } from "lucide-react";

export default function DiscoveryCenter() {
  const queryClient = useQueryClient();
  const [showWarning, setShowWarning] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<"pending" | "rogue">("pending");

  const { data: results = [], isLoading } = useQuery({ queryKey: ["discoveryResults"], queryFn: () => api.get("/discovery/results").then(res => res.data) });
  const scanMutation = useMutation({ mutationFn: () => api.post("/discovery/scan"), onSuccess: () => queryClient.invalidateQueries({ queryKey: ["discoveryResults"] }) });
  const approveMutation = useMutation({ mutationFn: (id: string) => api.post(`/discovery/approve/${id}`), onSuccess: () => { setShowWarning(null); queryClient.invalidateQueries({ queryKey: ["discoveryResults"] }); } });
  const rejectMutation = useMutation({ mutationFn: (id: string) => api.delete(`/discovery/${id}`), onSuccess: () => queryClient.invalidateQueries({ queryKey: ["discoveryResults"] }) });

  const pendingDevices = results.filter((d: any) => !d.is_rogue);
  const rogueDevices = results.filter((d: any) => d.is_rogue);

  const getIcon = (type: string) => {
    if(type === 'router') return <Router size={18}/>;
    if(type === 'switch') return <Network size={18}/>;
    if(type === 'PC' || type === 'Unknown') return <Monitor size={18}/>;
    return <Shield size={18}/>;
  };

  return (
    <div style={{ padding: '2rem' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '2rem' }}>
        <h1 style={{ color: 'var(--accent-blue)' }}><Radar size={28} style={{ display: 'inline', verticalAlign: 'middle', marginRight: '10px' }} /> Network Auto-Discovery</h1>
        <button onClick={() => scanMutation.mutate()} className="btn" style={{ width: 'auto', background: 'var(--accent-blue)' }} disabled={scanMutation.isPending}>
          {scanMutation.isPending ? "Scanning..." : "Start Network Scan"}
        </button>
      </div>

      <div style={{ display: 'flex', gap: '1rem', marginBottom: '1.5rem' }}>
        <button onClick={() => setActiveTab("pending")} style={{ padding: '0.5rem 1rem', borderRadius: '8px', border: 'none', cursor: 'pointer', background: activeTab === 'pending' ? 'var(--accent-blue)' : 'var(--bg-surface)', color: 'white' }}>Pending ({pendingDevices.length})</button>
        <button onClick={() => setActiveTab("rogue")} style={{ padding: '0.5rem 1rem', borderRadius: '8px', border: 'none', cursor: 'pointer', background: activeTab === 'rogue' ? 'var(--accent-red)' : 'var(--bg-surface)', color: 'white' }}><ShieldAlert size={14} style={{ display: 'inline', marginRight: '4px' }} /> Rogue ({rogueDevices.length})</button>
      </div>

      <div className="data-card" style={{ padding: 0, overflow: 'hidden' }}>
        <table className="data-table">
          <thead><tr><th>IP Address</th><th>MAC Address</th><th>Hostname</th><th>Type</th><th>Location</th><th>Actions</th></tr></thead>
          <tbody>
            {(activeTab === "pending" ? pendingDevices : rogueDevices).map((d: any) => (
              <tr key={d.id}>
                <td style={{ fontFamily: 'monospace', fontWeight: 600 }}>{d.ip}</td>
                <td style={{ fontFamily: 'monospace', color: 'var(--text-muted)' }}>{d.mac || 'N/A'}</td>
                <td>{d.hostname || 'Unknown'}</td>
                <td style={{ display: 'flex', alignItems: 'center', gap: '6px', textTransform: 'capitalize' }}><span style={{ color: d.is_rogue ? 'var(--accent-red)' : 'var(--accent-blue)' }}>{getIcon(d.type)}</span> {d.type}</td>
                <td>{d.location}</td>
                <td style={{ display: 'flex', gap: '0.5rem' }}>
                  {activeTab === "pending" ? (
                    <>
                      <button onClick={() => setShowWarning(d.id)} className="btn" style={{ padding: '0.3rem 0.6rem', width: 'auto', background: 'var(--accent-green)' }}><CheckCircle size={14}/> Approve</button>
                      <button onClick={() => rejectMutation.mutate(d.id)} className="btn btn-danger" style={{ padding: '0.3rem 0.6rem', width: 'auto' }}><XCircle size={14}/> Ignore</button>
                    </>
                  ) : (
                    <button onClick={() => rejectMutation.mutate(d.id)} className="btn btn-danger" style={{ padding: '0.3rem 0.6rem', width: 'auto' }}><XCircle size={14}/> Block</button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {showWarning && (
        <div style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, background: 'rgba(0,0,0,0.85)', display: 'flex', justifyContent: 'center', alignItems: 'center', zIndex: 9999 }}>
          <div className="data-card" style={{ width: '500px', border: '2px solid var(--accent-amber)', textAlign: 'center', padding: '2rem' }}>
            <AlertTriangle size={48} color="var(--accent-amber)" style={{ margin: '0 auto 1rem' }} />
            <h2 style={{ color: 'var(--accent-amber)', marginBottom: '1rem' }}>⚠️ सुरक्षा चेतावनी</h2>
            <div style={{ background: 'var(--bg-base)', padding: '1rem', borderRadius: '8px', marginBottom: '1.5rem', borderLeft: '4px solid var(--accent-amber)', textAlign: 'left' }}>
              <p style={{ fontWeight: 'bold', marginBottom: '0.5rem' }}>क्या आपने इस डिवाइस को फिजिकली वेरिफाई कर लिया है?</p>
              <p style={{ fontSize: '0.9rem', color: 'var(--text-muted)', marginBottom: '1rem' }}>Have you physically verified this device?</p>
              <p style={{ fontSize: '0.85rem', color: 'var(--accent-red)' }}><strong>चेतावनी:</strong> अनजान डिवाइस अप्रूव करने से हैकर नेटवर्क में घुस सकता है।</p>
            </div>
            <div style={{ display: 'flex', gap: '1rem' }}>
              <button className="btn" style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-color)' }} onClick={() => setShowWarning(null)}>❌ रद्द करें</button>
              <button className="btn" style={{ background: 'var(--accent-green)' }} onClick={() => approveMutation.mutate(showWarning)}>✓ अप्रूव करें</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}