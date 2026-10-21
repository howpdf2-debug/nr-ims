import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useParams, useNavigate } from "react-router-dom";
import { api, errorMessage } from "../lib/api";
import { ArrowLeft, Server, Network, Activity, Clock, Wrench } from "lucide-react";

interface Device {
  id: string;
  hostname: string;
  ip_address: string;
  category: string;
  status: string;
  station_code: string;
  is_maintenance: boolean;
}
interface Iface {
  id: string;
  name: string;
  ip_address: string | null;
  description: string | null;
  status: string;
  in_mbps: number;
  out_mbps: number;
  errors: number;
}
interface OspfNeighbor {
  neighbor_ip: string;
  state: string;
  interface: string;
}
interface DeviceDetailResponse {
  device: Device;
  interfaces: Iface[];
  ospf_neighbors: OspfNeighbor[];
}
interface AuditRow {
  id: string;
  created_at: string;
  action_type: string;
  performed_by: string;
  status: string;
}

const statusBadge = (s: string) => (s === "up" ? "badge-up" : s === "down" ? "badge-down" : "badge-warning");
const emptyCell = (cols: number, text: string) => (
  <tr><td colSpan={cols} style={{ textAlign: "center", padding: "2rem", color: "var(--text-muted)" }}>{text}</td></tr>
);

export default function DeviceDetail() {
  const { deviceId } = useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState("interfaces");

  const { data, isLoading, isError, error } = useQuery<DeviceDetailResponse>({
    queryKey: ["deviceDetail", deviceId],
    queryFn: () => api.get(`/devices/${deviceId}/detail`).then((res) => res.data),
  });

  const { data: auditHistory = [] } = useQuery<AuditRow[]>({
    queryKey: ["deviceAudit", deviceId],
    queryFn: () => api.get(`/audit/device/${deviceId}`).then((res) => res.data),
    enabled: activeTab === "audit",
  });

  const maintenanceMutation = useMutation({
    mutationFn: (isMaint: boolean) => api.put(`/actions/${deviceId}/maintenance`, { is_maintenance: isMaint }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["deviceDetail", deviceId] });
      queryClient.invalidateQueries({ queryKey: ["downDevices"] });
    },
    onError: (err: unknown) => alert(errorMessage(err, "Could not change maintenance mode")),
  });

  if (isLoading) return <p style={{ padding: "2rem" }}>Loading device telemetry...</p>;
  if (isError || !data) {
    return <p style={{ color: "var(--accent-red)", padding: "2rem" }}>{errorMessage(error, "Failed to load device.")}</p>;
  }

  const { device, interfaces = [], ospf_neighbors = [] } = data;

  return (
    <div>
      <button onClick={() => navigate(-1)} className="nav-item" style={{ display: "inline-flex", background: "transparent", border: "none", color: "var(--accent-blue)", cursor: "pointer", marginBottom: "1.5rem" }}>
        <ArrowLeft size={20} /> Back
      </button>

      <div className="data-card" style={{ marginBottom: "2rem", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "1rem" }}>
          <div style={{ padding: "1rem", background: device.status === "down" ? "rgba(239, 68, 68, 0.1)" : "rgba(59, 130, 246, 0.1)", borderRadius: "12px" }}>
            <Server size={32} color={device.status === "down" ? "var(--accent-red)" : "var(--accent-blue)"} />
          </div>
          <div>
            <h1 style={{ margin: 0 }}>{device.hostname}</h1>
            <p style={{ color: "var(--text-muted)", margin: "4px 0" }}>
              IP: {device.ip_address} | Category: {device.category.toUpperCase()} | Station: {device.station_code}
            </p>
            <span className={`badge ${device.is_maintenance ? "badge-warning" : statusBadge(device.status)}`}>
              {(device.is_maintenance ? "maintenance" : device.status).toUpperCase()}
            </span>
          </div>
        </div>

        <button
          onClick={() => maintenanceMutation.mutate(!device.is_maintenance)}
          disabled={maintenanceMutation.isPending}
          className="btn"
          style={{ width: "auto", background: device.is_maintenance ? "var(--accent-amber)" : "var(--bg-surface)", border: "1px solid var(--border-color)", display: "flex", gap: "8px" }}
        >
          <Wrench size={16} /> {device.is_maintenance ? "Exit Maintenance" : "Set Maintenance"}
        </button>
      </div>

      <div className="tabs" style={{ marginBottom: "1rem" }}>
        <div className={`tab ${activeTab === "interfaces" ? "active" : ""}`} onClick={() => setActiveTab("interfaces")} style={{ display: "flex", gap: "8px" }}><Network size={18} /> Interfaces</div>
        <div className={`tab ${activeTab === "ospf" ? "active" : ""}`} onClick={() => setActiveTab("ospf")} style={{ display: "flex", gap: "8px" }}><Activity size={18} /> OSPF</div>
        <div className={`tab ${activeTab === "audit" ? "active" : ""}`} onClick={() => setActiveTab("audit")} style={{ display: "flex", gap: "8px" }}><Clock size={18} /> History</div>
      </div>

      <div className="data-card" style={{ padding: 0, overflow: "hidden" }}>
        {activeTab === "interfaces" && (
          <table className="data-table">
            <thead><tr><th>Interface</th><th>IP Address</th><th>Description</th><th>Status</th><th>In (Mbps)</th><th>Out (Mbps)</th><th>Errors</th></tr></thead>
            <tbody>
              {interfaces.length === 0 ? emptyCell(7, "No interfaces recorded for this device.") : interfaces.map((intf) => (
                <tr key={intf.id}>
                  <td>{intf.name}</td><td>{intf.ip_address ?? "—"}</td><td>{intf.description ?? "—"}</td>
                  <td><span className={`badge ${statusBadge(intf.status)}`}>{intf.status}</span></td>
                  <td>{intf.in_mbps.toFixed(1)}</td><td>{intf.out_mbps.toFixed(1)}</td>
                  <td style={{ color: intf.errors > 0 ? "var(--accent-amber)" : "inherit" }}>{intf.errors}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        {activeTab === "ospf" && (
          <table className="data-table">
            <thead><tr><th>Neighbor IP</th><th>State</th><th>Interface</th></tr></thead>
            <tbody>
              {ospf_neighbors.length === 0 ? emptyCell(3, "No OSPF neighbours collected yet.") : ospf_neighbors.map((o, i) => (
                <tr key={i}><td>{o.neighbor_ip}</td><td><span className={`badge ${o.state === "FULL" ? "badge-up" : "badge-warning"}`}>{o.state}</span></td><td>{o.interface}</td></tr>
              ))}
            </tbody>
          </table>
        )}
        {activeTab === "audit" && (
          <table className="data-table">
            <thead><tr><th>Time</th><th>Action</th><th>Performed By</th><th>Status</th></tr></thead>
            <tbody>
              {auditHistory.length === 0 ? emptyCell(4, "No actions taken yet.") : auditHistory.map((h) => (
                <tr key={h.id}>
                  <td style={{ color: "var(--text-muted)" }}>{new Date(h.created_at).toLocaleString()}</td>
                  <td><span className="badge badge-warning">{h.action_type}</span></td><td>{h.performed_by}</td>
                  <td><span className={`badge ${h.status === "success" ? "badge-up" : "badge-down"}`}>{h.status}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
