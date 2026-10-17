import { useQuery } from "@tanstack/react-query";
import { useParams, useNavigate } from "react-router-dom";
import { api } from "../lib/api";
import { ArrowLeft, Server } from "lucide-react";

export default function DeviceDetail() {
  const { deviceId } = useParams();
  const navigate = useNavigate();
  const { data, isLoading } = useQuery({ queryKey: ["deviceDetail", deviceId], queryFn: () => api.get(`/devices/${deviceId}`).then(res => res.data) });

  if (isLoading) return <p>Loading...</p>;
  if (!data) return <p>Device not found</p>;
  const { device, interfaces } = data;

  return (
    <div>
      <button onClick={() => navigate(-1)} className="nav-item" style={{ display: 'inline-flex', background: 'transparent', border: 'none', color: 'var(--accent-blue)', cursor: 'pointer', marginBottom: '1.5rem' }}><ArrowLeft size={20} /> Back</button>
      <div className="data-card" style={{ marginBottom: '2rem' }}>
        <h1><Server size={28} style={{ verticalAlign: 'middle', marginRight: '10px' }}/> {device.hostname}</h1>
        <p style={{ color: 'var(--text-muted)', marginTop: '0.5rem' }}>IP: {device.ip_address} | Status: {device.status.toUpperCase()}</p>
      </div>
      <h2>Interfaces</h2>
      <div className="data-card" style={{ padding: 0 }}>
        <table className="data-table">
          <thead><tr><th>Interface</th><th>IP</th><th>Status</th><th>In/Out</th></tr></thead>
          <tbody>
            {interfaces.map((intf: any) => (
              <tr key={intf.id}>
                <td>{intf.name}</td><td>{intf.ip_address}</td>
                <td><span className={`badge ${intf.status === 'up' ? 'badge-up' : 'badge-down'}`}>{intf.status}</span></td>
                <td>↓{intf.in_mbps} ↑{intf.out_mbps} Mbps</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
