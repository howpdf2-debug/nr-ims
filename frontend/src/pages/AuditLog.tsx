import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/api";
import { ShieldCheck, Server, Clock } from "lucide-react";

export default function AuditLog() {
  const { data: logs = [], isLoading } = useQuery({
    queryKey: ["auditLogs"],
    queryFn: () => api.get("/audit/logs").then(res => res.data),
  });

  return (
    <div>
      <h1 style={{ marginBottom: '2rem', color: 'var(--accent-blue)' }}>
        <ShieldCheck size={28} style={{ display: 'inline', verticalAlign: 'middle', marginRight: '10px' }} /> 
        Forensic Audit Logs
      </h1>
      <p style={{ color: 'var(--text-muted)', marginBottom: '1.5rem' }}>Only visible to IRCA Admin. All remote actions are recorded here.</p>

      <div className="data-card" style={{ padding: 0, overflow: 'hidden' }}>
        {isLoading ? <p style={{ padding: '1rem' }}>Loading...</p> : (
          <table className="data-table">
            <thead>
              <tr><th>Time</th><th>User</th><th>Action</th><th>Device</th><th>Status</th></tr>
            </thead>
            <tbody>
              {logs.length === 0 ? (
                <tr><td colSpan={5} style={{ textAlign: 'center', padding: '2rem' }}>No audit logs found.</td></tr>
              ) : logs.map((log: any) => (
                <tr key={log.id}>
                  <td style={{ color: 'var(--text-muted)', fontSize: '0.9rem' }}><Clock size={14} style={{ display: 'inline', marginRight: '4px' }}/> {new Date(log.created_at).toLocaleString()}</td>
                  <td style={{ fontWeight: 600 }}>{log.performed_by}</td>
                  <td><span className="badge badge-warning">{log.action_type}</span></td>
                  <td><Server size={14} style={{ display: 'inline', marginRight: '4px' }}/> {log.device_hostname} ({log.device_ip})</td>
                  <td><span className={`badge ${log.status === 'success' ? 'badge-up' : 'badge-down'}`}>{log.status.toUpperCase()}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}