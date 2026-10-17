import { useQuery } from "@tanstack/react-query";
import { useParams, useNavigate } from "react-router-dom";
import { api } from "../lib/api";
import { ArrowLeft, Server, Router, Network } from "lucide-react";

export default function StationDetail() {
  const { code } = useParams();
  const navigate = useNavigate();
  
  // API से सिर्फ उस स्टेशन के डिवाइसेस मांगें
  const { data: devices = [], isLoading } = useQuery({ 
    queryKey: ["stationDevices", code], 
    queryFn: () => api.get(`/devices/?station_code=${code}`).then(res => res.data) 
  });

  const getIcon = (cat: string) => {
    if(cat === 'router') return <Router size={18} />;
    if(cat === 'switch') return <Network size={18} />;
    return <Server size={18} />;
  }

  return (
    <div>
      <button onClick={() => navigate(-1)} className="nav-item" style={{ display: 'inline-flex', background: 'transparent', border: 'none', color: 'var(--accent-blue)', cursor: 'pointer', marginBottom: '1.5rem' }}>
        <ArrowLeft size={20} /> Back to Stations
      </button>
      
      <h1 style={{ marginBottom: '2rem' }}>Station {code} - Devices</h1>

      {isLoading ? <p>Loading devices...</p> : (
        <div className="data-card" style={{ padding: 0, overflow: 'hidden' }}>
          <table className="data-table">
            <thead>
              <tr>
                <th>Hostname</th>
                <th>IP Address</th>
                <th>Category</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {devices.length === 0 ? (
                <tr><td colSpan={4} style={{ textAlign: 'center', padding: '2rem' }}>No devices found for this station.</td></tr>
              ) : (
                devices.map((device: any) => (
                  <tr key={device.id} onClick={() => navigate(`/device/${device.id}`)} style={{ cursor: 'pointer' }}>
                    <td style={{ fontWeight: 600 }}>{device.hostname}</td>
                    <td style={{ fontFamily: 'monospace' }}>{device.ip_address}</td>
                    <td style={{ textTransform: 'capitalize', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                      {getIcon(device.category)} {device.category}
                    </td>
                    <td>
                      <span className={`badge ${device.status === 'up' ? 'badge-up' : 'badge-down'}`}>
                        {device.status}
                      </span>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}