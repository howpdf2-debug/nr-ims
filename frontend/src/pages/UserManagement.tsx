import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../lib/api";
import { Plus, Trash2, UserPlus } from "lucide-react";

export default function UserManagement() {
  const queryClient = useQueryClient();
  const [formData, setFormData] = useState({ email: "", password: "", role: "operator", scopes: "" });
  const [msg, setMsg] = useState("");

  const { data: users = [], isLoading } = useQuery({ queryKey: ["users"], queryFn: () => api.get("/users/").then(res => res.data) });
  const createMutation = useMutation({ mutationFn: (data: any) => api.post("/users/", data), onSuccess: () => { setMsg("User created! ✅"); setFormData({ email: "", password: "", role: "operator", scopes: "" }); queryClient.invalidateQueries({ queryKey: ["users"] }); }, onError: (err: any) => setMsg(err.response?.data?.detail || "Failed ❌") });
  const deleteMutation = useMutation({ mutationFn: (id: string) => api.delete(`/users/${id}`), onSuccess: () => queryClient.invalidateQueries({ queryKey: ["users"] }), onError: (err: any) => alert(err.response?.data?.detail) });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const scopeArray = formData.scopes.split(",").map(s => s.trim().toUpperCase()).filter(Boolean);
    createMutation.mutate({ ...formData, scopes: scopeArray });
  };

  return (
    <div style={{ display: 'flex', gap: '2rem', padding: '1rem' }}>
      <div className="data-card" style={{ width: '400px' }}>
        <h2><UserPlus size={20} style={{ display: 'inline', verticalAlign: 'middle', marginRight: '8px'}}/> Create User</h2>
        {msg && <div style={{ padding: '0.75rem', marginBottom: '1rem', borderRadius: '4px', background: msg.includes('✅') ? 'rgba(16, 185, 129, 0.1)' : 'rgba(239, 68, 68, 0.1)', color: msg.includes('✅') ? 'var(--accent-green)' : 'var(--accent-red)' }}>{msg}</div>}
        
        <form onSubmit={handleSubmit}>
          <div className="input-group"><label>Email</label><input type="email" value={formData.email} onChange={e => setFormData({...formData, email: e.target.value})} required /></div>
          <div className="input-group"><label>Password</label><input type="password" value={formData.password} onChange={e => setFormData({...formData, password: e.target.value})} required /></div>
          <div className="input-group"><label>Role</label><select value={formData.role} onChange={e => setFormData({...formData, role: e.target.value})} style={{ padding: '0.75rem', borderRadius: '4px', background: 'var(--bg-base)', color: 'white', border: '1px solid var(--border-color)' }}><option value="irca_admin">IRCA Admin</option><option value="divisional_admin">Divisional Admin</option><option value="tier1_incharge">Tier-1 Incharge</option><option value="operator">Operator</option></select></div>
          <div className="input-group"><label>Scopes (comma separated)</label><input value={formData.scopes} onChange={e => setFormData({...formData, scopes: e.target.value})} placeholder="e.g. LKO, MB or BSB or *" /><small>Use '*' for global access.</small></div>
          <button type="submit" className="btn" disabled={createMutation.isPending}>Save User</button>
        </form>
      </div>

      <div className="data-card" style={{ flex: 1, padding: 0, overflow: 'hidden' }}>
        {isLoading ? <p style={{ padding: '1rem' }}>Loading...</p> : (
          <table className="data-table">
            <thead><tr><th>Email</th><th>Role</th><th>Scopes</th><th>Status</th><th>Action</th></tr></thead>
            <tbody>
              {users.map((u: any) => (
                <tr key={u.id}>
                  <td style={{ fontWeight: 600 }}>{u.email}</td>
                  <td><span className="badge badge-up">{u.role.toUpperCase()}</span></td>
                  <td>{u.scopes.join(", ")}</td>
                  <td>{u.is_active ? 'Active' : 'Inactive'}</td>
                  <td><button onClick={() => { if(window.confirm("Delete this user?")) deleteMutation.mutate(u.id); }} className="btn btn-danger" style={{ padding: '4px 8px', width: 'auto' }}><Trash2 size={14}/></button></td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}