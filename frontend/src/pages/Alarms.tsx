import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../lib/api";
import {
  AlertTriangle,
  CheckCircle,
  Clock,
  Server,
  MapPin,
  X,
  ShieldAlert,
  Volume2,
  VolumeX,
} from "lucide-react";
import { useAlarmsQuery } from "../hooks/useAlarmsQuery";
import { useAlarmSound } from "../hooks/useAlarmSound";

export default function Alarms() {
  const queryClient = useQueryClient();
  const [filter, setFilter] = useState<"active" | "all">("active");
  const [selectedAlarm, setSelectedAlarm] = useState<any>(null);

  // ── Use Global Sound Hook (fixes duplicate polling & adds audio unlock) ──
  const { isMuted, toggleMute, isAudioLocked } = useAlarmSound();

  // ── Shared Query ──
  const { data: alarms = [], isLoading, isError } = useAlarmsQuery();

  const ackMutation = useMutation({
    mutationFn: (id: string) => api.patch(`/alarms/${id}/ack`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["alarms"] });
      setSelectedAlarm(null);
    },
  });

  const filteredAlarms = alarms.filter((a: any) =>
    filter === "active" ? a.status === "active" : true
  );

  const getSeverityColor = (severity: string, isSuppressed: boolean) => {
    if (isSuppressed) return "var(--text-muted)";
    switch (severity.toLowerCase()) {
      case "critical":
        return "var(--accent-red)";
      case "major":
        return "var(--accent-amber)";
      case "minor":
        return "var(--accent-blue)";
      default:
        return "var(--text-muted)";
    }
  };

  if (isLoading) return <p style={{ padding: "2rem" }}>Loading alarms...</p>;
  if (isError)
    return (
      <p style={{ padding: "2rem", color: "red" }}>Failed to load alarms.</p>
    );

  return (
    <div style={{ display: "flex", height: "80vh", gap: "1rem" }}>
      <div style={{ flex: 1, display: "flex", flexDirection: "column" }}>
        
        {/* Header Section */}
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            marginBottom: "1.5rem",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "1rem" }}>
            <h1 style={{ margin: 0 }}>Alarm Center</h1>
            <span style={{ fontSize: "1rem", color: "var(--text-muted)" }}>
              ({filteredAlarms.length} Alarms)
            </span>

            <button
              onClick={toggleMute}
              className="btn"
              style={{
                width: "auto",
                padding: "0.4rem 0.8rem",
                background: isMuted ? "var(--accent-red)" : "var(--bg-surface)",
                border: "1px solid var(--border-color)",
                display: "flex",
                gap: "6px",
                alignItems: "center",
                fontSize: "0.85rem",
              }}
              title={isMuted ? "Unmute Alarms" : "Mute Alarms"}
            >
              {isMuted ? <VolumeX size={16} /> : <Volume2 size={16} />}
              {isMuted ? "Muted" : "Sound ON"}
            </button>
          </div>

          <div
            style={{
              display: "flex",
              gap: "0.5rem",
              background: "var(--bg-surface)",
              padding: "4px",
              borderRadius: "8px",
            }}
          >
            <button
              onClick={() => setFilter("active")}
              style={{
                padding: "0.5rem 1rem",
                borderRadius: "6px",
                border: "none",
                cursor: "pointer",
                background:
                  filter === "active" ? "var(--accent-blue)" : "transparent",
                color: "white",
              }}
            >
              Active
            </button>
            <button
              onClick={() => setFilter("all")}
              style={{
                padding: "0.5rem 1rem",
                borderRadius: "6px",
                border: "none",
                cursor: "pointer",
                background:
                  filter === "all" ? "var(--accent-blue)" : "transparent",
                color: "white",
              }}
            >
              All
            </button>
          </div>
        </div>

        {/* 1. Audio Locked Warning (Browser Autoplay Policy) */}
        {isAudioLocked && !isMuted && (
          <div
            onClick={() => document.body.click()}
            style={{
              background: "rgba(59, 130, 246, 0.1)",
              color: "#3b82f6",
              padding: "0.75rem 1rem",
              borderRadius: "8px",
              marginBottom: "1rem",
              border: "1px solid #3b82f6",
              display: "flex",
              alignItems: "center",
              gap: "10px",
              cursor: "pointer",
            }}
            title="Click anywhere to enable audio"
          >
            <Volume2 size={20} />
            <strong>Audio Locked:</strong> Browser requires a click to play
            sounds. Click here to enable.
          </div>
        )}

        {/* 2. Muted Warning Banner */}
        {isMuted && (
          <div
            style={{
              background: "rgba(245, 158, 11, 0.1)",
              color: "var(--accent-amber)",
              padding: "0.75rem 1rem",
              borderRadius: "8px",
              marginBottom: "1rem",
              border: "1px solid var(--accent-amber)",
              display: "flex",
              alignItems: "center",
              gap: "10px",
            }}
          >
            <VolumeX size={20} />
            <strong>Warning:</strong> Alarm sounds are currently muted. Please
            unmute to ensure you don't miss critical alerts.
          </div>
        )}

        {/* Alarm Cards Grid */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fill, minmax(320px, 1fr))",
            gap: "1rem",
            overflowY: "auto",
          }}
        >
          {filteredAlarms.map((alarm: any) => {
            const color = getSeverityColor(alarm.severity, alarm.is_suppressed);
            return (
              <div
                key={alarm.id}
                onClick={() => setSelectedAlarm(alarm)}
                className={`alarm-card ${
                  alarm.status === "active" && !alarm.is_suppressed
                    ? "pulse"
                    : ""
                }`}
                style={{
                  background: "var(--bg-surface)",
                  borderRadius: "12px",
                  padding: "1.25rem",
                  borderLeft: `6px solid ${color}`,
                  cursor: "pointer",
                  opacity: alarm.is_suppressed ? 0.6 : 1,
                }}
              >
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    marginBottom: "0.75rem",
                  }}
                >
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "0.5rem",
                    }}
                  >
                    <AlertTriangle size={18} color={color} />
                    <span style={{ fontWeight: 600, color: color }}>
                      {alarm.is_suppressed
                        ? "SUPPRESSED"
                        : alarm.severity.toUpperCase()}
                    </span>
                  </div>
                  <span
                    className={`badge ${
                      alarm.status === "active" ? "badge-down" : "badge-up"
                    }`}
                    style={{ fontSize: "0.7rem" }}
                  >
                    {alarm.status}
                  </span>
                </div>
                <h3 style={{ margin: "0 0 0.5rem 0", fontSize: "1.1rem" }}>
                  {alarm.message}
                </h3>
                {alarm.is_suppressed && (
                  <p
                    style={{
                      fontSize: "0.8rem",
                      color: "var(--accent-amber)",
                      marginBottom: "0.5rem",
                    }}
                  >
                    ⚠ Root Cause: {alarm.root_cause}
                  </p>
                )}
                <div
                  style={{
                    fontSize: "0.85rem",
                    color: "var(--text-muted)",
                    display: "flex",
                    flexDirection: "column",
                    gap: "0.3rem",
                  }}
                >
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "6px",
                    }}
                  >
                    <Server size={14} /> {alarm.device_name}
                  </div>
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "6px",
                    }}
                  >
                    <MapPin size={14} /> {alarm.station_code}
                  </div>
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "6px",
                    }}
                  >
                    <Clock size={14} />{" "}
                    {new Date(alarm.first_seen).toLocaleTimeString()}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Details Side Panel */}
      {selectedAlarm && (
        <div
          style={{
            width: "400px",
            background: "var(--bg-surface)",
            borderRadius: "12px",
            padding: "1.5rem",
            display: "flex",
            flexDirection: "column",
          }}
        >
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              marginBottom: "1.5rem",
            }}
          >
            <h2 style={{ margin: 0 }}>Details</h2>
            <button
              onClick={() => setSelectedAlarm(null)}
              style={{
                background: "transparent",
                border: "none",
                color: "white",
                cursor: "pointer",
              }}
            >
              <X size={24} />
            </button>
          </div>
          <h3
            style={{
              color: getSeverityColor(
                selectedAlarm.severity,
                selectedAlarm.is_suppressed
              ),
            }}
          >
            {selectedAlarm.message}
          </h3>
          {selectedAlarm.is_suppressed && (
            <div
              style={{
                background: "rgba(245, 158, 11, 0.1)",
                padding: "1rem",
                borderRadius: "8px",
                marginTop: "1rem",
                color: "var(--accent-amber)",
              }}
            >
              <strong>Suppressed:</strong> {selectedAlarm.root_cause}
            </div>
          )}

          <div style={{ marginTop: "auto" }}>
            {selectedAlarm.status === "active" &&
            !selectedAlarm.is_suppressed ? (
              <button
                onClick={() => ackMutation.mutate(selectedAlarm.id)}
                disabled={ackMutation.isPending}
                className="btn"
                style={{
                  background: "var(--accent-blue)",
                  display: "flex",
                  justifyContent: "center",
                  gap: "8px",
                  opacity: ackMutation.isPending ? 0.6 : 1,
                }}
              >
                <ShieldAlert size={18} />
                {ackMutation.isPending ? "Acknowledging..." : "Acknowledge"}
              </button>
            ) : (
              <button
                className="btn"
                disabled
                style={{
                  background: "var(--bg-base)",
                  border: "1px solid var(--border-color)",
                }}
              >
                <CheckCircle size={18} />{" "}
                {selectedAlarm.is_suppressed ? "Suppressed" : "Acknowledged"}
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}