import { useState, useEffect } from "react";
import { useAlarmsQuery } from "../hooks/useAlarmsQuery";
import { useAlarmSound } from "../hooks/useAlarmSound";
import {
  Maximize,
  Minimize,
  Volume2,
  VolumeX,
  ShieldCheck,
  AlertTriangle,
  Server,
  MapPin,
} from "lucide-react";

export default function Wallboard() {
  const { data: alarms = [], isLoading, isError } = useAlarmsQuery();
  const { isMuted, toggleMute, isAudioLocked } = useAlarmSound();

  const [time, setTime] = useState(new Date());
  const [isFullscreen, setIsFullscreen] = useState(false);

  // ── Live Clock ──
  useEffect(() => {
    const timer = setInterval(() => setTime(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);

  // ── Fullscreen Handler ──
  const toggleFullscreen = () => {
    if (!document.fullscreenElement) {
      document.documentElement.requestFullscreen().catch((err) => {
        console.error("Error attempting to enable fullscreen:", err);
      });
      setIsFullscreen(true);
    } else {
      if (document.exitFullscreen) {
        document.exitFullscreen();
        setIsFullscreen(false);
      }
    }
  };

  // ── Filter ONLY Critical/Major Active Alarms ──
  const criticalAlarms = alarms.filter(
    (a: any) =>
      a.status === "active" &&
      !a.is_suppressed &&
      (a.severity === "critical" || a.severity === "major")
  );

  const formatTime = (date: Date) => {
    return date.toLocaleTimeString("en-US", {
      hour12: false,
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  };

  const formatDate = (date: Date) => {
    return date.toLocaleDateString("en-GB", {
      weekday: "long",
      day: "2-digit",
      month: "short",
      year: "numeric",
    });
  };

  // ── Global Error State (Backend Down) ──
  if (isError) {
    return (
      <div style={{ height: "100vh", background: "#450a0a", color: "white", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center" }}>
        <AlertTriangle size={100} color="#ef4444" style={{ marginBottom: "2rem" }} />
        <h1 style={{ fontSize: "4rem", margin: 0 }}>NETWORK DISCONNECTED</h1>
        <p style={{ fontSize: "1.5rem", opacity: 0.8 }}>Cannot reach NR-IMS Backend Server</p>
      </div>
    );
  }

  return (
    <div style={{ height: "100vh", background: "#050505", color: "white", display: "flex", flexDirection: "column", overflow: "hidden", fontFamily: "system-ui, sans-serif" }}>
      
      {/* ── TOP BAR ── */}
      <header style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "1.5rem 3rem", borderBottom: "2px solid #1f2937", background: "#0a0a0a" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "1rem" }}>
          <ShieldCheck size={48} color="#3b82f6" />
          <div>
            <h1 style={{ margin: 0, fontSize: "2.5rem", fontWeight: 800, letterSpacing: "2px" }}>NR-IMS NOC</h1>
            <p style={{ margin: 0, color: "#9ca3af", fontSize: "1.2rem", letterSpacing: "1px" }}>NORTHERN RAILWAY</p>
          </div>
        </div>

        {/* Live Clock & Controls */}
        <div style={{ display: "flex", alignItems: "center", gap: "3rem" }}>
          <div style={{ textAlign: "right" }}>
            <div style={{ fontSize: "3.5rem", fontWeight: "bold", fontFamily: "monospace", lineHeight: 1, color: "#f3f4f6" }}>
              {formatTime(time)}
            </div>
            <div style={{ fontSize: "1.2rem", color: "#9ca3af", marginTop: "0.5rem", letterSpacing: "1px" }}>
              {formatDate(time)}
            </div>
          </div>
          
          <div style={{ display: "flex", gap: "1rem" }}>
            <button onClick={toggleMute} style={{ background: isMuted ? "#7f1d1d" : "#1f2937", border: "none", padding: "1rem", borderRadius: "12px", cursor: "pointer", color: "white" }} title="Toggle Sound">
              {isMuted ? <VolumeX size={32} color="#f87171" /> : <Volume2 size={32} color="#4ade80" />}
            </button>
            <button onClick={toggleFullscreen} style={{ background: "#1f2937", border: "none", padding: "1rem", borderRadius: "12px", cursor: "pointer", color: "white" }} title="Toggle Fullscreen">
              {isFullscreen ? <Minimize size={32} /> : <Maximize size={32} />}
            </button>
          </div>
        </div>
      </header>

      {/* ── ALERTS SECTION ── */}
      <div style={{ padding: "2rem 3rem", flex: 1, display: "flex", flexDirection: "column", overflowY: "auto" }}>
        
        {/* Audio Locked Banner */}
        {isAudioLocked && !isMuted && (
          <div style={{ background: "#1e3a8a", color: "#bfdbfe", padding: "1rem 2rem", borderRadius: "12px", marginBottom: "2rem", fontSize: "1.5rem", display: "flex", alignItems: "center", gap: "1rem", cursor: "pointer" }} onClick={() => document.body.click()}>
            <Volume2 size={32} /> <strong>Action Required:</strong> Click anywhere to enable alarm sounds on this screen.
          </div>
        )}

        {/* Header / Counts */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1.5rem" }}>
          <h2 style={{ fontSize: "2rem", margin: 0, color: criticalAlarms.length > 0 ? "#f87171" : "#4ade80" }}>
            {criticalAlarms.length > 0 ? `ACTIVE CRITICAL INCIDENTS (${criticalAlarms.length})` : "SYSTEM OPERATIONAL"}
          </h2>
          <span style={{ fontSize: "1.2rem", color: "#6b7280" }}>Auto-refreshing...</span>
        </div>

        {/* Alarm Grid OR Empty State */}
        {isLoading ? (
          <div style={{ fontSize: "2rem", color: "#9ca3af", textAlign: "center", marginTop: "10vh" }}>Loading Telemetry Data...</div>
        ) : criticalAlarms.length === 0 ? (
          <div style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", color: "#4ade80", marginTop: "-5vh" }}>
            <ShieldCheck size={150} style={{ opacity: 0.2, marginBottom: "1rem" }} />
            <h1 style={{ fontSize: "4rem", margin: 0, letterSpacing: "2px" }}>ALL SYSTEMS OPERATIONAL</h1>
            <p style={{ fontSize: "1.5rem", color: "#6b7280" }}>No Critical or Major alarms detected in the network.</p>
          </div>
        ) : (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(500px, 1fr))", gap: "2rem" }}>
            {criticalAlarms.map((alarm: any) => (
              <div key={alarm.id} className="pulse" style={{ background: "#111827", borderRadius: "16px", padding: "2rem", borderLeft: "12px solid #ef4444", borderTop: "1px solid #374151", borderRight: "1px solid #374151", borderBottom: "1px solid #374151", boxShadow: "0 10px 30px rgba(239, 68, 68, 0.1)" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "1.5rem" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "1rem" }}>
                    <AlertTriangle size={36} color="#ef4444" />
                    <span style={{ fontSize: "1.5rem", fontWeight: "bold", color: "#ef4444", letterSpacing: "1px" }}>
                      {alarm.severity.toUpperCase()}
                    </span>
                  </div>
                  <span style={{ background: "#7f1d1d", color: "#fca5a5", padding: "0.5rem 1rem", borderRadius: "8px", fontSize: "1rem", fontWeight: "bold" }}>
                    ACTIVE
                  </span>
                </div>
                
                <h3 style={{ fontSize: "2.5rem", margin: "0 0 2rem 0", lineHeight: 1.2, fontWeight: 600 }}>
                  {alarm.message}
                </h3>
                
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem", background: "#1f2937", padding: "1.5rem", borderRadius: "12px" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", fontSize: "1.4rem", color: "#d1d5db" }}>
                    <Server size={24} color="#9ca3af" /> {alarm.device_name}
                  </div>
                  <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", fontSize: "1.4rem", color: "#d1d5db" }}>
                    <MapPin size={24} color="#9ca3af" /> {alarm.station_code} ({alarm.station_name})
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}