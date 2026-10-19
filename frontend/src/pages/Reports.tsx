import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/api";
import ReactECharts from "echarts-for-react";
import { Download, Server, AlertTriangle, Activity, ShieldCheck } from "lucide-react";

export default function Reports() {
  const [isExporting, setIsExporting] = useState(false);

  const { data: reportData, isLoading } = useQuery({
    queryKey: ["reportsSummary"],
    queryFn: () => api.get("/reports/summary").then((res) => res.data),
    refetchInterval: 30000, // Auto-refresh every 30s
  });

  const handleExportCSV = async () => {
    setIsExporting(true);
    try {
      const response = await api.get("/reports/export/alarms", { responseType: "blob" });
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement("a");
      link.href = url;
      link.setAttribute("download", `alarms_report_${new Date().toISOString().split("T")[0]}.csv`);
      document.body.appendChild(link);
      link.click();
      link.remove();
    } catch (error) {
      console.error("Export failed", error);
      alert("Failed to export CSV");
    } finally {
      setIsExporting(false);
    }
  };

  if (isLoading || !reportData) return <p style={{ padding: "2rem" }}>Loading Reports...</p>;

  const { kpi, severity_distribution, top_stations } = reportData;

  // ── ECharts Configurations ──
  const pieOption = {
    tooltip: { trigger: "item" },
    legend: { top: "5%", left: "center", textStyle: { color: "#9ca3af" } },
    series: [
      {
        name: "Severity",
        type: "pie",
        radius: ["40%", "70%"],
        avoidLabelOverlap: false,
        itemStyle: { borderRadius: 10, borderColor: "#0f172a", borderWidth: 2 },
        label: { show: false, position: "center" },
        emphasis: { label: { show: true, fontSize: 16, fontWeight: "bold", color: "white" } },
        labelLine: { show: false },
        data: severity_distribution,
        color: ["#ef4444", "#f59e0b", "#3b82f6", "#6b7280"],
      },
    ],
  };

  const barOption = {
    tooltip: { trigger: "axis", axisPointer: { type: "shadow" } },
    grid: { left: "3%", right: "4%", bottom: "3%", containLabel: true },
    xAxis: { type: "value", splitLine: { lineStyle: { color: "#1f2937" } }, axisLabel: { color: "#9ca3af" } },
    yAxis: { type: "category", data: top_stations.map((s: any) => s.name), axisLabel: { color: "#d1d5db" } },
    series: [
      {
        name: "Alarms",
        type: "bar",
        data: top_stations.map((s: any) => s.count),
        itemStyle: { color: "#3b82f6", borderRadius: [0, 4, 4, 0] },
        barWidth: "50%",
      },
    ],
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div>
          <h1 style={{ margin: 0 }}>SLA & Reports</h1>
          <p style={{ margin: 0, color: "var(--text-muted)", fontSize: "0.9rem" }}>Network Performance & Analytics</p>
        </div>
        <button
          onClick={handleExportCSV}
          disabled={isExporting}
          className="btn"
          style={{ background: "var(--accent-blue)", display: "flex", gap: "8px", alignItems: "center", width: "auto" }}
        >
          <Download size={18} /> {isExporting ? "Exporting..." : "Export Alarms (CSV)"}
        </button>
      </div>

      {/* KPI Cards */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: "1rem" }}>
        <KPICard title="Network Uptime" value={`${kpi.uptime_pct}%`} icon={<ShieldCheck size={24} color="#4ade80" />} color="#4ade80" />
        <KPICard title="Total Devices" value={kpi.total_devices} icon={<Server size={24} color="#3b82f6" />} color="#3b82f6" />
        <KPICard title="Down Devices" value={kpi.down_devices} icon={<Activity size={24} color="#ef4444" />} color="#ef4444" />
        <KPICard title="Active Alarms" value={kpi.active_alarms} icon={<AlertTriangle size={24} color="#f59e0b" />} color="#f59e0b" />
      </div>

      {/* Charts Section */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1.5rem" }}>
        {/* Severity Pie Chart */}
        <div style={{ background: "var(--bg-surface)", padding: "1.5rem", borderRadius: "12px", border: "1px solid var(--border-color)" }}>
          <h3 style={{ margin: "0 0 1rem 0" }}>Alarms by Severity</h3>
          {severity_distribution.length > 0 ? (
            <ReactECharts option={pieOption} style={{ height: "300px" }} />
          ) : (
            <p style={{ color: "var(--text-muted)" }}>No alarm data available.</p>
          )}
        </div>

        {/* Top Stations Bar Chart */}
        <div style={{ background: "var(--bg-surface)", padding: "1.5rem", borderRadius: "12px", border: "1px solid var(--border-color)" }}>
          <h3 style={{ margin: "0 0 1rem 0" }}>Top 5 Problem Stations</h3>
          {top_stations.length > 0 ? (
            <ReactECharts option={barOption} style={{ height: "300px" }} />
          ) : (
            <p style={{ color: "var(--text-muted)" }}>No station data available.</p>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Reusable KPI Card Component ──
function KPICard({ title, value, icon, color }: { title: string; value: any; icon: any; color: string }) {
  return (
    <div style={{ background: "var(--bg-surface)", padding: "1.5rem", borderRadius: "12px", border: "1px solid var(--border-color)", display: "flex", alignItems: "center", gap: "1rem" }}>
      <div style={{ background: `${color}20`, padding: "1rem", borderRadius: "50%" }}>
        {icon}
      </div>
      <div>
        <p style={{ margin: 0, color: "var(--text-muted)", fontSize: "0.9rem", textTransform: "uppercase", letterSpacing: "1px" }}>{title}</p>
        <h2 style={{ margin: 0, fontSize: "1.8rem", fontWeight: 700 }}>{value}</h2>
      </div>
    </div>
  );
}