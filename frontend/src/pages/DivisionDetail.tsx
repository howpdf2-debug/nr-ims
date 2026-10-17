import { useQuery } from "@tanstack/react-query";
import { useParams, useNavigate } from "react-router-dom";
import { api } from "../lib/api";
import { ArrowLeft, MapPin } from "lucide-react";

export default function DivisionDetail() {
  const { divCode } = useParams();
  const navigate = useNavigate();
  
  const { data: stations = [], isLoading } = useQuery({ 
    queryKey: ["stations", divCode], 
    queryFn: () => api.get(`/dashboard/divisions/${divCode}/stations`).then(res => res.data) 
  });

  return (
    <div>
      <button onClick={() => navigate("/dashboard")} className="nav-item" style={{ display: 'inline-flex', background: 'transparent', border: 'none', color: 'var(--accent-blue)', cursor: 'pointer', marginBottom: '1.5rem' }}>
        <ArrowLeft size={20} /> Back to Dashboard
      </button>
      
      <h1 style={{ marginBottom: '2rem' }}>{divCode} Division - Stations</h1>
      
      {isLoading ? <p>Loading stations...</p> : (
        <div className="data-card" style={{ padding: 0, overflow: 'hidden' }}>
          <table className="data-table">
            <thead>
              <tr>
                <th>Station Code</th>
                <th>Station Name</th>
                <th>Tier</th>
                <th>Type</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {stations.map((st: any) => (
                <tr key={st.code} onClick={() => navigate(`/station/${st.code}`)} style={{ cursor: 'pointer' }}>
                  <td style={{ fontWeight: 600 }}>
                    <MapPin size={14} style={{ display: 'inline', marginRight: '4px' }}/>{st.code}
                  </td>
                  <td>{st.name}</td>
                  <td>{st.tier}</td>
                  <td>{st.type}</td>
                  <td>
                    <span className={`badge ${st.status === 'healthy' ? 'badge-up' : 'badge-down'}`}>
                      {st.status === 'healthy' ? 'ALL OK' : 'CRITICAL'}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}