// Alarm API types and presentation helpers. Mirrors backend `AlarmListItem` / `AlarmEventRead`
// (backend/app/schemas/alarm.py); keep both in sync.

export type AlarmStatus = "active" | "acknowledged" | "resolved";
/** `open` = active + acknowledged (the fault is still there). Same vocabulary as `GET /alarms/?status=`. */
export type AlarmStatusFilter = AlarmStatus | "open" | "all";

export interface Alarm {
  id: string;
  device_id: string;
  device_name: string;
  station_code: string;
  station_name: string;
  severity: string;
  message: string;
  status: string;
  first_seen: string;
  last_seen: string;
  occurrence_count: number;
  is_suppressed: boolean;
  root_cause: string | null;
  acked_by: string | null;
  acked_at: string | null;
  ack_note: string | null;
  resolved_by: string | null;
  resolved_at: string | null;
  resolve_note: string | null;
}

export interface AlarmEvent {
  id: string;
  alarm_id: string;
  event_type: string;
  from_status: string | null;
  to_status: string;
  actor: string | null;
  note: string | null;
  created_at: string;
}

/** Badge colour per lifecycle state (CSS classes live in index.css). Unknown states fall back to amber. */
export function statusBadgeClass(status: string): string {
  switch (status) {
    case "active":
      return "badge-down"; // red: needs attention
    case "acknowledged":
      return "badge-warning"; // amber: someone owns it, fault still present
    case "resolved":
      return "badge-up"; // green: closed
    default:
      return "badge-warning";
  }
}

export function severityColor(severity: string, suppressed: boolean): string {
  if (suppressed) return "var(--text-muted)";
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
}

const EVENT_LABELS: Record<string, string> = {
  raised: "Raised",
  escalated: "Escalated",
  acknowledged: "Acknowledged",
  resolved: "Resolved",
};

export function eventLabel(eventType: string): string {
  return EVENT_LABELS[eventType] ?? eventType;
}
