import { useState } from "react";
import type { KeyboardEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import {
  AlertTriangle,
  CheckCircle,
  Clock,
  History,
  MapPin,
  Server,
  ShieldAlert,
  Volume2,
  VolumeX,
  X,
} from "lucide-react";
import { api, errorMessage } from "../lib/api";
import { getRole } from "../lib/auth";
import { eventLabel, severityColor } from "../lib/alarms";
import type { Alarm, AlarmEvent } from "../lib/alarms";
import { useAlarmsQuery } from "../hooks/useAlarmsQuery";
import { useAlarmSound } from "../hooks/useAlarmSound";
import AlarmStatusBadge from "../components/AlarmStatusBadge";

type Tab = "open" | "active" | "acknowledged" | "resolved";
const TABS: { key: Tab; label: string }[] = [
  { key: "open", label: "Open" },
  { key: "active", label: "Unacknowledged" },
  { key: "acknowledged", label: "Acknowledged" },
  { key: "resolved", label: "Resolved" },
];
const NO_ALARMS: Alarm[] = [];
const fmt = (iso: string | null) => (iso ? new Date(iso).toLocaleString() : "—");

export default function Alarms() {
  const [tab, setTab] = useState<Tab>("open");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const { isMuted, toggleMute, isAudioLocked } = useAlarmSound();

  // `open` (active + acknowledged) is always loaded: it feeds three of the four tabs and the counters.
  // Resolved history can be long, so it is only requested while its tab is visible.
  const { data: open = NO_ALARMS, isLoading, isError } = useAlarmsQuery("open");
  const { data: resolved, isLoading: resolvedLoading } = useAlarmsQuery("resolved", {
    enabled: tab === "resolved",
    limit: 200,
  });

  const counts: Record<Tab, number | null> = {
    open: open.length,
    active: open.filter((a) => a.status === "active").length,
    acknowledged: open.filter((a) => a.status === "acknowledged").length,
    resolved: resolved ? resolved.length : null,
  };
  const shown: Alarm[] =
    tab === "resolved" ? (resolved ?? NO_ALARMS) : tab === "open" ? open : open.filter((a) => a.status === tab);
  const selected = [...open, ...(resolved ?? NO_ALARMS)].find((a) => a.id === selectedId) ?? null;

  if (isLoading) return <p style={{ padding: "2rem" }}>Loading alarms...</p>;
  if (isError) return <p style={{ padding: "2rem", color: "var(--accent-red)" }}>Failed to load alarms.</p>;

  return (
    <div style={{ display: "flex", height: "80vh", gap: "1rem" }}>
      <div style={{ flex: 1, display: "flex", flexDirection: "column", minWidth: 0 }}>
        {/* Header */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1.5rem", flexWrap: "wrap", gap: "0.75rem" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "1rem" }}>
            <h1 style={{ margin: 0 }}>Alarm Center</h1>
            <span style={{ fontSize: "1rem", color: "var(--text-muted)" }}>({shown.length} shown)</span>
            <button
              onClick={toggleMute}
              className="btn"
              style={{ width: "auto", padding: "0.4rem 0.8rem", background: isMuted ? "var(--accent-red)" : "var(--bg-surface)", border: "1px solid var(--border-color)", display: "flex", gap: "6px", alignItems: "center", fontSize: "0.85rem" }}
              title={isMuted ? "Unmute Alarms" : "Mute Alarms"}
            >
              {isMuted ? <VolumeX size={16} /> : <Volume2 size={16} />}
              {isMuted ? "Muted" : "Sound ON"}
            </button>
          </div>

          <div role="tablist" aria-label="Alarm status" style={{ display: "flex", gap: "0.25rem", background: "var(--bg-surface)", padding: "4px", borderRadius: "8px" }}>
            {TABS.map(({ key, label }) => (
              <button
                key={key}
                role="tab"
                aria-selected={tab === key}
                onClick={() => setTab(key)}
                style={{ padding: "0.5rem 0.9rem", borderRadius: "6px", border: "none", cursor: "pointer", color: "white", background: tab === key ? "var(--accent-blue)" : "transparent" }}
              >
                {label}
                <span style={{ marginLeft: "6px", opacity: 0.75, fontSize: "0.8rem" }}>{counts[key] ?? "…"}</span>
              </button>
            ))}
          </div>
        </div>

        {notice && (
          <div role="status" style={{ background: "rgba(16, 185, 129, 0.1)", color: "var(--accent-green)", padding: "0.75rem 1rem", borderRadius: "8px", marginBottom: "1rem", border: "1px solid var(--accent-green)" }}>
            <CheckCircle size={16} style={{ verticalAlign: "-3px", marginRight: "8px" }} />
            {notice}
          </div>
        )}

        {/* Audio locked (browser autoplay policy) */}
        {isAudioLocked && !isMuted && (
          <div
            onClick={() => document.body.click()}
            style={{ background: "rgba(59, 130, 246, 0.1)", color: "#3b82f6", padding: "0.75rem 1rem", borderRadius: "8px", marginBottom: "1rem", border: "1px solid #3b82f6", display: "flex", alignItems: "center", gap: "10px", cursor: "pointer" }}
            title="Click anywhere to enable audio"
          >
            <Volume2 size={20} />
            <strong>Audio Locked:</strong> Browser requires a click to play sounds. Click here to enable.
          </div>
        )}

        {isMuted && (
          <div style={{ background: "rgba(245, 158, 11, 0.1)", color: "var(--accent-amber)", padding: "0.75rem 1rem", borderRadius: "8px", marginBottom: "1rem", border: "1px solid var(--accent-amber)", display: "flex", alignItems: "center", gap: "10px" }}>
            <VolumeX size={20} />
            <strong>Warning:</strong> Alarm sounds are currently muted. Please unmute to ensure you don&apos;t miss critical alerts.
          </div>
        )}

        {tab === "resolved" && resolvedLoading && <p style={{ color: "var(--text-muted)" }}>Loading resolved alarms...</p>}
        {!(tab === "resolved" && resolvedLoading) && shown.length === 0 && (
          <p style={{ color: "var(--text-muted)", padding: "2rem 0" }}>
            {tab === "resolved" ? "No resolved alarms." : "No alarms in this view. All clear."}
          </p>
        )}

        {/* Cards */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(320px, 1fr))", gap: "1rem", overflowY: "auto", alignContent: "start" }}>
          {shown.map((alarm) => {
            const color = severityColor(alarm.severity, alarm.is_suppressed);
            const select = () => setSelectedId(alarm.id);
            const onKey = (e: KeyboardEvent) => {
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                select();
              }
            };
            return (
              <div
                key={alarm.id}
                role="button"
                tabIndex={0}
                aria-label={`${alarm.severity} alarm on ${alarm.device_name}: ${alarm.message}`}
                onClick={select}
                onKeyDown={onKey}
                className={`alarm-card ${alarm.status === "active" && !alarm.is_suppressed ? "pulse" : ""}`}
                style={{ background: "var(--bg-surface)", borderRadius: "12px", padding: "1.25rem", borderLeft: `6px solid ${color}`, cursor: "pointer", opacity: alarm.is_suppressed || alarm.status === "resolved" ? 0.65 : 1, outline: selectedId === alarm.id ? "2px solid var(--accent-blue)" : "none" }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "0.75rem" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                    <AlertTriangle size={18} color={color} />
                    <span style={{ fontWeight: 600, color }}>{alarm.is_suppressed ? "SUPPRESSED" : alarm.severity.toUpperCase()}</span>
                  </div>
                  <AlarmStatusBadge status={alarm.status} occurrences={alarm.occurrence_count} />
                </div>
                <h3 style={{ margin: "0 0 0.5rem 0", fontSize: "1.1rem" }}>{alarm.message}</h3>
                {alarm.is_suppressed && (
                  <p style={{ fontSize: "0.8rem", color: "var(--accent-amber)", marginBottom: "0.5rem" }}>⚠ Root Cause: {alarm.root_cause}</p>
                )}
                <div style={{ fontSize: "0.85rem", color: "var(--text-muted)", display: "flex", flexDirection: "column", gap: "0.3rem" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "6px" }}><Server size={14} /> {alarm.device_name}</div>
                  <div style={{ display: "flex", alignItems: "center", gap: "6px" }}><MapPin size={14} /> {alarm.station_code}</div>
                  <div style={{ display: "flex", alignItems: "center", gap: "6px" }}><Clock size={14} /> {new Date(alarm.first_seen).toLocaleTimeString()}</div>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {selected && (
        <AlarmDrawer
          key={selected.id}
          alarm={selected}
          onClose={() => setSelectedId(null)}
          onResolved={() => {
            setSelectedId(null); // a resolved alarm leaves the "open" list the drawer reads from
            setNotice("Alarm resolved. It is now listed under the Resolved tab.");
            window.setTimeout(() => setNotice(null), 6000);
          }}
        />
      )}
    </div>
  );
}

interface DrawerProps {
  alarm: Alarm;
  onClose: () => void;
  onResolved: () => void;
}

/** Details + acknowledge/resolve (optional note) + full history for one alarm. */
function AlarmDrawer({ alarm, onClose, onResolved }: DrawerProps) {
  const queryClient = useQueryClient();
  const [note, setNote] = useState("");
  const canAct = getRole() !== "operator"; // server enforces; this only hides buttons that would answer 403
  const color = severityColor(alarm.severity, alarm.is_suppressed);

  const { data: history = [], isLoading: historyLoading, isError: historyError } = useQuery<AlarmEvent[]>({
    queryKey: ["alarmHistory", alarm.id],
    queryFn: () => api.get<AlarmEvent[]>(`/alarms/${alarm.id}/history`).then((res) => res.data),
  });

  const act = useMutation({
    mutationFn: (kind: "ack" | "resolve") => {
      const body = note.trim() ? { note: note.trim() } : {};
      return kind === "ack" ? api.patch(`/alarms/${alarm.id}/ack`, body) : api.post(`/alarms/${alarm.id}/resolve`, body);
    },
    onSuccess: (_res, kind) => {
      queryClient.invalidateQueries({ queryKey: ["alarms"] });
      queryClient.invalidateQueries({ queryKey: ["alarmHistory", alarm.id] });
      queryClient.invalidateQueries({ queryKey: ["dashboardSummary"] });
      setNote("");
      if (kind === "resolve") onResolved();
    },
    onError: (err: unknown) => alert(errorMessage(err, "Could not update the alarm")),
  });

  return (
    <aside aria-label="Alarm details" style={{ width: "400px", background: "var(--bg-surface)", borderRadius: "12px", padding: "1.5rem", display: "flex", flexDirection: "column", overflowY: "auto" }}>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "1rem" }}>
        <h2 style={{ margin: 0 }}>Details</h2>
        <button onClick={onClose} aria-label="Close details" style={{ background: "transparent", border: "none", color: "white", cursor: "pointer" }}>
          <X />
        </button>
      </div>

      <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", marginBottom: "0.75rem" }}>
        <span style={{ fontWeight: 700, color }}>{alarm.severity.toUpperCase()}</span>
        <AlarmStatusBadge status={alarm.status} occurrences={alarm.occurrence_count} />
      </div>
      <h3 style={{ margin: "0 0 1rem 0" }}>{alarm.message}</h3>

      {alarm.is_suppressed && (
        <div style={{ background: "rgba(245, 158, 11, 0.1)", border: "1px solid var(--accent-amber)", color: "var(--accent-amber)", padding: "0.75rem", borderRadius: "8px", marginBottom: "1rem", fontSize: "0.9rem" }}>
          <ShieldAlert size={16} style={{ verticalAlign: "-3px", marginRight: "6px" }} />
          Suppressed. Root cause: {alarm.root_cause}. Fix the upstream fault first.
        </div>
      )}

      <dl style={{ display: "grid", gridTemplateColumns: "auto 1fr", gap: "0.4rem 1rem", margin: "0 0 1rem 0", fontSize: "0.9rem" }}>
        <dt style={{ color: "var(--text-muted)" }}>Device</dt>
        <dd style={{ margin: 0 }}><Link to={`/device/${alarm.device_id}`} style={{ color: "var(--accent-blue)" }}>{alarm.device_name}</Link></dd>
        <dt style={{ color: "var(--text-muted)" }}>Station</dt>
        <dd style={{ margin: 0 }}>{alarm.station_name} ({alarm.station_code})</dd>
        <dt style={{ color: "var(--text-muted)" }}>First seen</dt>
        <dd style={{ margin: 0 }}>{fmt(alarm.first_seen)}</dd>
        <dt style={{ color: "var(--text-muted)" }}>Last seen</dt>
        <dd style={{ margin: 0 }}>{fmt(alarm.last_seen)}</dd>
        <dt style={{ color: "var(--text-muted)" }}>Reported</dt>
        <dd style={{ margin: 0 }}>{alarm.occurrence_count} time{alarm.occurrence_count === 1 ? "" : "s"}</dd>
        {alarm.acked_by && (<><dt style={{ color: "var(--text-muted)" }}>Acknowledged</dt><dd style={{ margin: 0 }}>{alarm.acked_by}<br />{fmt(alarm.acked_at)}{alarm.ack_note ? ` — “${alarm.ack_note}”` : ""}</dd></>)}
        {alarm.resolved_by && (<><dt style={{ color: "var(--text-muted)" }}>Resolved</dt><dd style={{ margin: 0 }}>{alarm.resolved_by}<br />{fmt(alarm.resolved_at)}{alarm.resolve_note ? ` — “${alarm.resolve_note}”` : ""}</dd></>)}
      </dl>

      {alarm.status !== "resolved" && (
        canAct ? (
          <div style={{ marginBottom: "1.25rem" }}>
            <label htmlFor="alarm-note" style={{ display: "block", fontSize: "0.85rem", color: "var(--text-muted)", marginBottom: "0.35rem" }}>
              Note (optional) <span style={{ float: "right" }}>{note.length}/500</span>
            </label>
            <textarea
              id="alarm-note"
              value={note}
              maxLength={500}
              rows={2}
              onChange={(e) => setNote(e.target.value)}
              placeholder="e.g. engineer dispatched / fibre spliced"
              style={{ width: "100%", boxSizing: "border-box", background: "var(--bg-main, #0f172a)", color: "white", border: "1px solid var(--border-color)", borderRadius: "8px", padding: "0.6rem", resize: "vertical" }}
            />
            <div style={{ display: "flex", gap: "0.75rem", marginTop: "0.75rem" }}>
              {alarm.status === "active" && (
                <button
                  className="btn"
                  disabled={act.isPending || alarm.is_suppressed}
                  onClick={() => act.mutate("ack")}
                  title={alarm.is_suppressed ? "Acknowledge the root-cause alarm instead" : "I am working on this"}
                  style={{ flex: 1, background: "var(--accent-amber)", opacity: alarm.is_suppressed ? 0.5 : 1 }}
                >
                  {alarm.is_suppressed ? "Suppressed" : "Acknowledge"}
                </button>
              )}
              <button className="btn" disabled={act.isPending} onClick={() => act.mutate("resolve")} title="The fault is fixed" style={{ flex: 1, background: "var(--accent-green)" }}>
                Resolve
              </button>
            </div>
          </div>
        ) : (
          <p style={{ color: "var(--text-muted)", fontSize: "0.85rem", marginBottom: "1.25rem" }}>
            Your role is read-only: it cannot acknowledge or resolve alarms.
          </p>
        )
      )}

      <h3 style={{ margin: "0 0 0.75rem 0", display: "flex", alignItems: "center", gap: "8px", fontSize: "1rem" }}>
        <History size={18} /> History
      </h3>
      {historyLoading && <p style={{ color: "var(--text-muted)" }}>Loading history...</p>}
      {historyError && <p style={{ color: "var(--accent-red)" }}>Could not load history.</p>}
      <ol style={{ listStyle: "none", margin: 0, padding: 0, display: "flex", flexDirection: "column", gap: "0.75rem" }}>
        {history.map((ev) => (
          <li key={ev.id} style={{ borderLeft: "2px solid var(--border-color)", paddingLeft: "0.75rem", fontSize: "0.85rem" }}>
            <div>
              <strong>{eventLabel(ev.event_type)}</strong>
              {ev.from_status && ev.from_status !== ev.to_status ? (
                <span style={{ color: "var(--text-muted)" }}> {ev.from_status} → {ev.to_status}</span>
              ) : null}
            </div>
            <div style={{ color: "var(--text-muted)" }}>{ev.actor ?? "system"} · {fmt(ev.created_at)}</div>
            {ev.note && <div style={{ marginTop: "0.2rem" }}>“{ev.note}”</div>}
          </li>
        ))}
      </ol>
    </aside>
  );
}
