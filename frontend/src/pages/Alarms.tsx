import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../lib/api";
import { AlertTriangle, CheckCircle, Clock, Server, MapPin, X, ShieldAlert } from "lucide-react";

export default function Alarms() {
  const queryClient = useQueryClient();
  const [filter, setFilter] = useState<"active" | "all">("active");
  const [selectedAlarm, setSelectedAlarm] = useState<any>(null);

  const { data: alarms = [], isLoading, isError } = useQuery({
    queryKey: ["alarms"],
    queryFn: () => api.get("/alarms/").then(res => res.data),
    refetchInterval: 10000, // हर 10 सेकंड में रिफ्रेश
  });

  const ackMutation = useMutation({
    mutationFn: (id: string) => api.patch(`/alarms/${id}/ack`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["alarms"] });
      setSelectedAlarm(null); // म्यूटेशन के बाद पैनल बंद करें
    }
  });

  // फ़िल्टर लॉजिक
  const filteredAlarms = alarms.filter((a: any) => {
    if (filter === "active") return a.status === "active";
    return true;
  });

  const getSeverityColor = (severity: string) => {
    switch (severity.toLowerCase()) {
      case "critical": return "var(--accent-red)";
      case "major": return "var(--accent-amber)";
      case "minor": return "var(--accent-blue)";
      default: return "var(--text-muted)";
    }
  };

  if (isLoading) return <p style={{ padding: '2rem' }}>Loading alarms...</p>;
  if (isError) return <p style={{ padding: '2rem', color: 'red' }}>Failed to load alarms.</p>;

  return (
    <div style={{ display: 'flex', height: '80vh', gap: '1rem' }}>
      
      {/* Left Side: Alarm Cards */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
        
        {/* Header & Filters */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
          <h1>Alarm Center <span style={{ fontSize: '1rem', color: 'var(--text-muted)' }}>({filteredAlarms.length} Alarms)</span></h1>
          <div style={{ display: 'flex', gap: '0.5rem', background: 'var(--bg-surface)', padding: '4px', borderRadius: '8px' }}>
            <button onClick={() => setFilter("active")} style={{ padding: '0.5rem 1rem', borderRadius: '6px', border: 'none', cursor: 'pointer', background: filter === 'active' ? 'var(--accent-blue)' : 'transparent', color: 'white', fontWeight: 600 }}>Active Only</button>
            <button onClick={() => setFilter("all")} style={{ padding: '0.5rem 1rem', borderRadius: '6px', border: 'none', cursor: 'pointer', background: filter === 'all' ? 'var(--accent-blue)' : 'transparent', color: 'white', fontWeight: 600 }}>All Alarms</button>
          </div>
        </div>

        {/* Cards Grid */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: '1rem', overflowY: 'auto', paddingRight: '0.5rem' }}>
          {filteredAlarms.map((alarm: any) => (
            <div 
              key={alarm.id} 
              onClick={() => setSelectedAlarm(alarm)}
              className={`alarm-card ${alarm.severity} ${alarm.status === 'active' ? 'pulse' : ''}`}
              style={{ 
                background: 'var(--bg-surface)', 
                borderRadius: '12px', 
                padding: '1.25rem', 
                borderLeft: `6px solid ${getSeverityColor(alarm.severity)}`,
                cursor: 'pointer',
                boxShadow: alarm.status === 'active' ? `0 0 15px ${getSeverityColor(alarm.severity)}40` : 'none',
                transition: 'all 0.2s'
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '0.75rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <AlertTriangle size={18} color={getSeverityColor(alarm.severity)} />
                  <span style={{ fontWeight: 600, color: getSeverityColor(alarm.severity), textTransform: 'uppercase' }}>{alarm.severity}</span>
                </div>
                <span className={`badge ${alarm.status === 'active' ? 'badge-down' : 'badge-up'}`} style={{ fontSize: '0.7rem' }}>
                  {alarm.status}
                </span>
              </div>
              
              <h3 style={{ margin: '0 0 0.5rem 0', fontSize: '1.1rem' }}>{alarm.message}</h3>
              
              <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)', display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}><Server size={14}/> {alarm.device_name} ({alarm.device_id.slice(0,4)})</div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}><MapPin size={14}/> {alarm.station_code} - {alarm.station_name}</div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}><Clock size={14}/> {new Date(alarm.first_seen).toLocaleTimeString()}</div>
              </div>
            </div>
          ))}
          {filteredAlarms.length === 0 && (
            <div style={{ gridColumn: '1 / -1', textAlign: 'center', padding: '3rem', color: 'var(--text-muted)' }}>
              <CheckCircle size={48} style={{ margin: '0 auto 1rem', color: 'var(--accent-green)' }} />
              <h2>No Active Alarms</h2>
              <p>All systems are operating normally.</p>
            </div>
          )}
        </div>
      </div>

      {/* Right Side: Side Drawer (Details & Actions) */}
      {selectedAlarm && (
        <div style={{ width: '400px', background: 'var(--bg-surface)', borderRadius: '12px', border: '1px solid var(--border-color)', padding: '1.5rem', display: 'flex', flexDirection: 'column', height: '100%' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
            <h2 style={{ margin: 0 }}>Alarm Details</h2>
            <button onClick={() => setSelectedAlarm(null)} style={{ background: 'transparent', border: 'none', color: 'white', cursor: 'pointer' }}><X size={24} /></button>
          </div>

          <div style={{ marginBottom: '1.5rem' }}>
            <span className={`badge ${selectedAlarm.status === 'active' ? 'badge-down' : 'badge-up'}`}>{selectedAlarm.status.toUpperCase()}</span>
            <h3 style={{ margin: '1rem 0 0.5rem', fontSize: '1.3rem', color: getSeverityColor(selectedAlarm.severity) }}>{selectedAlarm.severity.toUpperCase()} ALARM</h3>
            <p style={{ fontSize: '1.1rem', lineHeight: '1.5' }}>{selectedAlarm.message}</p>
          </div>

          <div style={{ background: 'var(--bg-base)', padding: '1rem', borderRadius: '8px', marginBottom: '1.5rem', fontSize: '0.9rem' }}>
            <p style={{ margin: '0 0 0.5rem', color: 'var(--text-muted)' }}><strong>Device:</strong> {selectedAlarm.device_name}</p>
            <p style={{ margin: '0 0 0.5rem', color: 'var(--text-muted)' }}><strong>Station:</strong> {selectedAlarm.station_code} ({selectedAlarm.station_name})</p>
            <p style={{ margin: '0 0 0.5rem', color: 'var(--text-muted)' }}><strong>First Seen:</strong> {new Date(selectedAlarm.first_seen).toLocaleString()}</p>
            {selectedAlarm.acked_by && <p style={{ margin: 0, color: 'var(--text-muted)' }}><strong>Acked By:</strong> {selectedAlarm.acked_by}</p>}
          </div>

          <div style={{ marginTop: 'auto' }}>
            {selectedAlarm.status === 'active' ? (
              <button 
                onClick={() => ackMutation.mutate(selectedAlarm.id)} 
                className="btn" 
                style={{ width: '100%', padding: '1rem', fontSize: '1.1rem', background: 'var(--accent-blue)', display: 'flex', justifyContent: 'center', gap: '10px' }}
                disabled={ackMutation.isPending}
              >
                <ShieldAlert size={20} /> {ackMutation.isPending ? "Acknowledging..." : "Acknowledge Alarm"}
              </button>
            ) : (
              <button className="btn" style={{ width: '100%', padding: '1rem', background: 'var(--bg-surface)', border: '1px solid var(--border-color)', cursor: 'not-allowed' }} disabled>
                <CheckCircle size={20} style={{ display: 'inline', marginRight: '8px' }} /> Already Acknowledged
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}