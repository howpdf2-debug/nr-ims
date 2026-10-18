import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../lib/api";
import { PlusCircle, MapPin, AlertTriangle } from "lucide-react";

export default function StationManagement() {
  const queryClient = useQueryClient();
  const [formData, setFormData] = useState({ code: "", name: "", division: "LKO", tier: "Tier 1", station_type: "PRS" });
  const [msg, setMsg] = useState("");

  // 1. डेटाबेस से सभी स्टेशन्स फेच करें
  const { data: stations = [], isLoading, isError } = useQuery({
    queryKey: ["manageStations"],
    queryFn: () => api.get("/stations/").then(res => res.data),
  });

  // 2. नया स्टेशन जोड़ने का म्यूटेशन
  const mutation = useMutation({
    mutationFn: (newStation: any) => api.post("/stations/", newStation),
    onSuccess: () => {
      setMsg("Station added successfully! ✅");
      setFormData({ code: "", name: "", division: "LKO", tier: "Tier 1", station_type: "PRS" });
      queryClient.invalidateQueries({ queryKey: ["manageStations"] });
    },
    onError: (err: any) => {
      setMsg(err.response?.data?.detail || "Failed to add station ❌");
    }
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    mutation.mutate(formData);
  };

  if (isError) {
    return (
      <div className="data-card" style={{ textAlign: 'center', padding: '3rem' }}>
        <AlertTriangle size={48} color="var(--accent-red)" style={{ margin: '0 auto 1rem' }} />
        <h2>Failed to load stations</h2>
        <p style={{ color: 'var(--text-muted)' }}>There was an error communicating with the backend.</p>
      </div>
    );
  }

  return (
    <div>
      <h1 style={{ marginBottom: '2rem' }}>Station Management</h1>
      
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: '2rem' }}>
        {/* नया स्टेशन जोड़ने का फॉर्म */}
        <div className="data-card">
          <h2><PlusCircle size={20} style={{ display: 'inline', verticalAlign: 'middle', marginRight: '8px'}}/> Add New Station</h2>
          
          {msg && (
            <div style={{ padding: '0.75rem', marginBottom: '1rem', borderRadius: '4px', background: msg.includes('✅') ? 'rgba(16, 185, 129, 0.1)' : 'rgba(239, 68, 68, 0.1)', color: msg.includes('✅') ? 'var(--accent-green)' : 'var(--accent-red)' }}>
              {msg}
            </div>
          )}
          
          <form onSubmit={handleSubmit}>
            <div className="input-group">
              <label>Station Code (e.g. NDLS)</label>
              <input value={formData.code} onChange={e => setFormData({...formData, code: e.target.value.toUpperCase()})} required />
            </div>
            <div className="input-group">
              <label>Station Name</label>
              <input value={formData.name} onChange={e => setFormData({...formData, name: e.target.value})} required />
            </div>
            <div className="input-group">
              <label>Division</label>
              <select value={formData.division} onChange={e => setFormData({...formData, division: e.target.value})} style={{ padding: '0.75rem', borderRadius: '4px', background: 'var(--bg-base)', color: 'white', border: '1px solid var(--border-color)' }}>
                <option value="LKO">LKO</option>
                <option value="DLI">DLI</option>
                <option value="MB">MB</option>
                <option value="UMB">UMB</option>
                <option value="FZR">FZR</option>
                <option value="JAT">JAT</option>
                <option value="IRCA">IRCA</option>
              </select>
            </div>
            <div className="input-group">
              <label>Tier</label>
              <select value={formData.tier} onChange={e => setFormData({...formData, tier: e.target.value})} style={{ padding: '0.75rem', borderRadius: '4px', background: 'var(--bg-base)', color: 'white', border: '1px solid var(--border-color)' }}>
                <option value="Tier 1">Tier 1</option>
                <option value="Tier 2">Tier 2</option>
                <option value="Tier 3">Tier 3</option>
              </select>
            </div>
            <button type="submit" className="btn" disabled={mutation.isPending}>
              {mutation.isPending ? "Saving..." : "Save Station"}
            </button>
          </form>
        </div>

        {/* स्टेशन्स की लिस्ट */}
        <div className="data-card" style={{ padding: 0, overflow: 'hidden' }}>
          {isLoading ? <p style={{ padding: '1rem' }}>Loading stations...</p> : (
            <table className="data-table">
              <thead>
                <tr><th>Code</th><th>Name</th><th>Division</th><th>Tier</th></tr>
              </thead>
              <tbody>
                {stations.length === 0 ? (
                  <tr><td colSpan={4} style={{ textAlign: 'center', padding: '2rem' }}>No stations found.</td></tr>
                ) : (
                  stations.map((st: any) => (
                    <tr key={st.code}>
                      <td style={{ fontWeight: 600 }}><MapPin size={14} style={{ display: 'inline', marginRight: '4px' }}/>{st.code}</td>
                      <td>{st.name}</td>
                      <td>{st.division}</td>
                      <td>{st.tier}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
}